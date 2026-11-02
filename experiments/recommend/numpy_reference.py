"""推荐算法的 numpy / pandas 参考实现（仅供实验与等价性校验，生产不再调用）。

内容与提交 d8dc465 时 ai-service/app/spark/recommend.py、recommend_eval.py 中的矩阵实现一致：
数据用 Spark JDBC 读出后 toPandas，用户×职位评分矩阵放在 Driver 内存里，用 numpy 计算
用户余弦、内容分、min-max、融合与 Top-K。生产离线任务已改为 Spark DataFrame 实现
（ai-service/app/spark/recommend_cf.py），本文件用于：

1. experiments/recommend/run_recommend_ablation.py 的消融实验（多种子、多协议的大量网格）；
2. experiments/recommend/verify_spark_cf.py 对比 Spark 实现与本参考实现的数值差异。
"""

from __future__ import annotations

import logging
import time
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from pyspark.ml.recommendation import ALS
from pyspark.sql.types import DoubleType, LongType, StructField, StructType

AI_ROOT = Path(__file__).resolve().parents[2] / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.spark.recommend_eval import (  # noqa: E402
    ALPHAS,
    EVAL_KS,
    HALF_LIFE_DAYS,
    HALF_LIFE_SECONDS,
    NEIGHBORS,
    SHRINK,
    TOP_N,
    build_reason,
    clip_score,
    evaluate_rankings,
    holdout_count,
    ndcg_at,
    skill_match_percent,
)
from app.spark.session import read_query  # noqa: E402

logger = logging.getLogger(__name__)

ALS_RANK = 8
ALS_ITER = 6
ALS_REG = 0.08
ALS_ALPHA = 20.0
EDU_PENALTY = 0.35


def split_holdout(events: pd.DataFrame) -> set[tuple[int, int]]:
    """按学生、按时间留出最后约 20% 的收藏/投递职位。返回 (user_id, position_id)。"""
    if events.empty:
        return set()
    positive = events[events["behavior_type"].isin([2, 3])]
    if positive.empty:
        return set()
    last = (
        positive.groupby(["user_id", "position_id"], as_index=False)["ts"]
        .max()
        .sort_values(["user_id", "ts", "position_id"])
    )
    held: set[tuple[int, int]] = set()
    for user_id, group in last.groupby("user_id", sort=False):
        n_test = holdout_count(len(group))
        if n_test <= 0:
            continue
        for position_id in group.tail(n_test)["position_id"].tolist():
            held.add((int(user_id), int(position_id)))
    return held


def drop_pairs(events: pd.DataFrame, pairs: set[tuple[int, int]]) -> pd.DataFrame:
    if events.empty or not pairs:
        return events
    keys = list(zip(events["user_id"].astype(int), events["position_id"].astype(int)))
    mask = [key not in pairs for key in keys]
    return events.loc[mask].copy()


def aggregate_frame(
    events: pd.DataFrame, ref_ts: float, half_life_days: float | None = HALF_LIFE_DAYS
) -> tuple[pd.DataFrame, pd.Series]:
    """按 (用户, 职位) 汇总：权重 × 指数衰减，再 log1p。默认半衰期 45 天，参考时间为 ref_ts。

    half_life_days=None 表示不做时间衰减（消融实验用）。"""
    empty = pd.DataFrame(columns=["user_id", "position_id", "contrib", "rating"])
    if events is None or len(events) == 0:
        return empty, pd.Series(dtype=float)
    ts = pd.to_numeric(events["ts"], errors="coerce").fillna(0).to_numpy(dtype=np.float64)
    weight = pd.to_numeric(events["weight"], errors="coerce").to_numpy(dtype=np.float64)
    behavior = pd.to_numeric(events["behavior_type"], errors="coerce").fillna(1).to_numpy(dtype=np.int64)
    fallback = np.where(behavior == 2, 3.0, np.where(behavior == 3, 5.0, 1.0))
    weight = np.where(np.isfinite(weight) & (weight > 0), weight, fallback)
    age = np.maximum(0.0, float(ref_ts) - ts)
    if half_life_days is None or half_life_days <= 0:
        contrib = weight.copy()
    else:
        contrib = weight * np.power(0.5, age / (float(half_life_days) * 86400.0))
    frame = pd.DataFrame(
        {
            "user_id": pd.to_numeric(events["user_id"], errors="coerce").fillna(0).astype(np.int64),
            "position_id": pd.to_numeric(events["position_id"], errors="coerce").fillna(0).astype(np.int64),
            "contrib": contrib,
        }
    )
    grouped = frame.groupby(["user_id", "position_id"], as_index=False)["contrib"].sum()
    grouped["rating"] = np.log1p(grouped["contrib"].to_numpy(dtype=np.float64))
    item_pop = frame.groupby("position_id")["contrib"].sum()
    return grouped, item_pop


def fill_matrix(grouped: pd.DataFrame, user_index: dict[int, int], item_index: dict[int, int], shape: tuple[int, int]) -> np.ndarray:
    matrix = np.zeros(shape, dtype=np.float64)
    if grouped is None or len(grouped) == 0:
        return matrix
    for user_id, position_id, rating in zip(grouped["user_id"], grouped["position_id"], grouped["rating"]):
        row = user_index.get(int(user_id))
        col = item_index.get(int(position_id))
        if row is None or col is None:
            continue
        matrix[row, col] = float(rating)
    return matrix


def popularity_scores(item_pop: pd.Series, item_index: dict[int, int], n_items: int) -> np.ndarray:
    raw = np.zeros(n_items, dtype=np.float64)
    if item_pop is None or len(item_pop) == 0:
        return raw
    for position_id, value in item_pop.items():
        col = item_index.get(int(position_id))
        if col is not None:
            raw[col] = float(value)
    peak = float(raw.max()) if n_items else 0.0
    if peak <= 0:
        return raw
    return 100.0 * np.log1p(raw) / math.log1p(peak)


def cosine_predict(ratings: np.ndarray, shrink: float = SHRINK, neighbors: int = NEIGHBORS) -> np.ndarray:
    """用户余弦协同过滤。只保留正相关的前若干邻居，并用共同交互数做收缩，避免只重合 1 个职位就相似度为 1。"""
    n_users, n_items = ratings.shape
    if n_users == 0 or n_items == 0:
        return np.zeros_like(ratings, dtype=np.float64)
    binary = (ratings > 0).astype(np.float64)
    norms = np.linalg.norm(ratings, axis=1)
    safe = np.maximum(norms, 1e-12)
    normed = ratings / safe[:, None]
    sim = normed @ normed.T
    np.fill_diagonal(sim, 0.0)
    overlap = binary @ binary.T
    sim *= overlap / (overlap + shrink)
    inactive = norms <= 1e-8
    sim[inactive, :] = 0.0
    sim[:, inactive] = 0.0
    sim = np.clip(sim, 0.0, None)
    if n_users > 1 and neighbors > 0:
        k = min(neighbors, n_users - 1)
        top = np.argpartition(-sim, kth=k - 1, axis=1)[:, :k]
        mask = np.zeros_like(sim, dtype=bool)
        mask[np.arange(n_users)[:, None], top] = True
        sim = np.where(mask, sim, 0.0)
    denom = np.maximum(sim.sum(axis=1, keepdims=True), 1e-12)
    pred = (sim @ ratings) / denom
    pred[inactive] = 0.0
    return pred


def cosine_one(
    user_vec: np.ndarray,
    ratings: np.ndarray,
    self_index: int | None = None,
    shrink: float = SHRINK,
    neighbors: int = NEIGHBORS,
) -> np.ndarray:
    """单个用户对预计算用户-职位矩阵做余弦，公式与 cosine_predict 一致。"""
    n_items = ratings.shape[1] if ratings.ndim == 2 else 0
    if ratings.size == 0 or n_items == 0:
        return np.zeros(n_items, dtype=np.float64)
    norms = np.linalg.norm(ratings, axis=1)
    user_norm = float(np.linalg.norm(user_vec))
    if user_norm < 1e-8:
        return np.zeros(n_items, dtype=np.float64)
    sims = (ratings @ user_vec) / (np.maximum(norms, 1e-12) * user_norm)
    overlap = (ratings > 0).astype(np.float64) @ (user_vec > 0).astype(np.float64)
    sims = np.clip(sims, 0.0, None) * (overlap / (overlap + shrink))
    sims[norms <= 1e-8] = 0.0
    if self_index is not None and 0 <= self_index < len(sims):
        sims[self_index] = 0.0
    n_users = len(sims)
    if neighbors > 0 and n_users > 1:
        k = min(neighbors, n_users - 1)
        top = np.argpartition(-sims, kth=k - 1)[:k]
        mask = np.zeros(n_users, dtype=bool)
        mask[top] = True
        sims = np.where(mask, sims, 0.0)
    denom = float(sims.sum())
    if denom <= 1e-12:
        return np.zeros(n_items, dtype=np.float64)
    return (sims @ ratings) / denom


def minmax_rows(scores: np.ndarray, banned: np.ndarray | None = None) -> np.ndarray:
    """按行把未屏蔽职位缩放到 0-100。全 0 的行保持 0，避免把「没有协同信号」标成 50。"""
    work = np.array(scores, dtype=np.float64, copy=True)
    if banned is not None:
        work[banned] = np.nan
    with np.errstate(all="ignore"):
        lo = np.nanmin(work, axis=1)
        hi = np.nanmax(work, axis=1)
    span = hi - lo
    span_safe = np.where(np.isfinite(span) & (span > 1e-6), span, 1.0)
    scaled = (work - lo[:, None]) / span_safe[:, None] * 100.0
    valid = np.isfinite(lo) & np.isfinite(hi)
    zero = valid & (hi <= 1e-8)
    flat = valid & ~zero & ~(span > 1e-6)
    scaled[zero] = 0.0
    if np.any(flat):
        scaled[flat] = np.where(np.isnan(work[flat]), 0.0, 100.0)
    scaled = np.nan_to_num(scaled, nan=0.0, posinf=100.0, neginf=0.0)
    if banned is not None:
        scaled[banned] = 0.0
    return np.clip(scaled, 0.0, 100.0)


def fuse_scores(
    cf_mm: np.ndarray,
    content: np.ndarray,
    popularity: np.ndarray,
    activity: np.ndarray,
    alpha: float,
    mode: str,
    adaptive: bool,
) -> np.ndarray:
    """线性融合或门控融合。没有行为或协同过滤无信号的学生改用内容分与热门分。"""
    pop = popularity
    if pop.ndim == 1:
        pop = np.broadcast_to(pop, content.shape).copy()
    alpha_u = np.full(content.shape[0], float(alpha), dtype=np.float64)
    if adaptive:
        ramp = np.clip(activity / 8.0, 0.0, 1.0)
        alpha_u = float(alpha) * (0.25 + 0.75 * ramp)
    alpha_col = alpha_u[:, None]
    if mode == "gated":
        mixed = content * ((1.0 - alpha_col) + alpha_col * (cf_mm / 100.0))
    else:
        mixed = alpha_col * cf_mm + (1.0 - alpha_col) * content
    # 没有行为、或行为全落在无人共同交互的职位上（协同过滤分整行为 0）时，按冷启动处理
    no_cf = np.max(cf_mm, axis=1) <= 0 if cf_mm.shape[1] > 0 else np.ones(cf_mm.shape[0], dtype=bool)
    cold = (activity <= 0) | no_cf
    if np.any(cold):
        mixed[cold] = 0.75 * content[cold] + 0.25 * pop[cold]
    return np.clip(mixed, 0.0, 100.0)


def top_indices(scores: np.ndarray, banned: np.ndarray | None, k: int) -> np.ndarray:
    """每行取前 k 个下标，不足或被屏蔽的位置为 -1。同分时偏向更靠前的列，保证可重复。"""
    n_rows, n_cols = scores.shape
    if n_rows == 0 or n_cols == 0 or k <= 0:
        return np.zeros((n_rows, 0), dtype=np.int32)
    k = min(k, n_cols)
    work = np.array(scores, dtype=np.float64, copy=True)
    work -= np.arange(n_cols, dtype=np.float64) * 1e-9
    if banned is not None:
        work[banned] = -1e18
    part = np.argpartition(-work, kth=k - 1, axis=1)[:, :k]
    rows = np.arange(n_rows)[:, None]
    part_scores = work[rows, part]
    order = np.argsort(-part_scores, axis=1)
    chosen = part[rows, order]
    chosen_scores = part_scores[rows, order]
    chosen = np.where(chosen_scores > -1e17, chosen, -1)
    return chosen.astype(np.int32)


def materialize(user_ids: list[int], item_ids: list[int], chosen: np.ndarray) -> dict[int, list[int]]:
    rankings: dict[int, list[int]] = {}
    for row, user_id in enumerate(user_ids):
        items: list[int] = []
        if chosen.shape[1] == 0:
            rankings[int(user_id)] = items
            continue
        for col in chosen[row]:
            index = int(col)
            if index < 0:
                continue
            items.append(int(item_ids[index]))
        rankings[int(user_id)] = items
    return rankings


def _load(spark) -> dict[str, pd.DataFrame]:
    events = _sql(
        spark,
        """
        SELECT user_id, behavior_type, target_id AS position_id, weight,
               UNIX_TIMESTAMP(create_time) AS ts
        FROM user_behavior_log
        WHERE deleted = 0 AND target_type = 1 AND behavior_type IN (1, 2, 3)
        """,
    )
    jobs = _sql(
        spark,
        """
        SELECT p.id AS position_id, p.title, p.tech_direction, p.city, p.province,
               p.education, p.salary_min, p.salary_max, p.salary_months,
               IFNULL(p.requirement, '') AS requirement, p.shelf_status, p.audit_status,
               p.apply_count,
               IF(c.short_name IS NOT NULL AND c.short_name <> '', c.short_name, c.company_name) AS company_name,
               c.audit_status AS company_audit, c.deleted AS company_deleted
        FROM job_position p
        INNER JOIN ent_company c ON c.id = p.company_id
        WHERE p.deleted = 0
        """,
    )
    profiles = _sql(
        spark,
        """
        SELECT user_id, IFNULL(major, '') AS major, education,
               IFNULL(expect_city, '') AS expect_city,
               IFNULL(expect_direction, '') AS expect_direction
        FROM stu_profile
        WHERE deleted = 0
        """,
    )
    skills = _sql(
        spark,
        """
        SELECT s.user_id, s.tag_id, s.proficiency, t.name AS tag_name
        FROM stu_skill s
        INNER JOIN skill_tag t ON t.id = s.tag_id AND t.deleted = 0
        WHERE s.deleted = 0
        """,
    )
    job_tags = _sql(
        spark,
        """
        SELECT position_id, tag_id
        FROM job_position_tag
        WHERE deleted = 0
        """,
    )
    applications = _sql(
        spark,
        """
        SELECT user_id, position_id
        FROM job_application
        WHERE deleted = 0
        """,
    )
    tag_names = _sql(
        spark,
        """
        SELECT id AS tag_id, name AS tag_name
        FROM skill_tag
        WHERE deleted = 0
        """,
    )
    for frame in (events, jobs, profiles, skills, job_tags, applications):
        _coerce_ids(frame)
    if len(events):
        events["behavior_type"] = pd.to_numeric(events["behavior_type"], errors="coerce").fillna(1).astype(int)
        events["weight"] = pd.to_numeric(events["weight"], errors="coerce")
        events["ts"] = pd.to_numeric(events["ts"], errors="coerce").fillna(0)
    if len(jobs):
        for column in ("education", "salary_min", "salary_max", "salary_months", "shelf_status", "audit_status", "apply_count", "company_audit", "company_deleted"):
            jobs[column] = pd.to_numeric(jobs[column], errors="coerce").fillna(0).astype(int)
        for column in ("title", "tech_direction", "city", "province", "requirement", "company_name"):
            jobs[column] = jobs[column].fillna("").astype(str)
        jobs["eligible"] = (
            (jobs["shelf_status"] == 1)
            & (jobs["audit_status"] == 1)
            & (jobs["company_audit"] == 1)
            & (jobs["company_deleted"] == 0)
        )
    if len(profiles):
        profiles["education"] = pd.to_numeric(profiles["education"], errors="coerce").fillna(2).astype(int)
        for column in ("major", "expect_city", "expect_direction"):
            profiles[column] = profiles[column].fillna("").astype(str)
    if len(skills):
        skills["tag_id"] = pd.to_numeric(skills["tag_id"], errors="coerce").fillna(0).astype(np.int64)
        skills["proficiency"] = pd.to_numeric(skills["proficiency"], errors="coerce").fillna(1).astype(float)
        skills["tag_name"] = skills["tag_name"].fillna("").astype(str)
    if len(job_tags):
        job_tags["tag_id"] = pd.to_numeric(job_tags["tag_id"], errors="coerce").fillna(0).astype(np.int64)
    names = {}
    if len(tag_names):
        for tag_id, tag_name in zip(tag_names["tag_id"], tag_names["tag_name"]):
            names[int(tag_id)] = str(tag_name)
    if len(skills):
        for tag_id, tag_name in zip(skills["tag_id"], skills["tag_name"]):
            names.setdefault(int(tag_id), str(tag_name))
    return {
        "events": events,
        "jobs": jobs,
        "profiles": profiles,
        "skills": skills,
        "job_tags": job_tags,
        "applications": applications,
        "tag_names": names,
    }


def _sql(spark, sql: str) -> pd.DataFrame:
    frame = read_query(spark, sql).toPandas()
    frame.columns = [str(column).lower() for column in frame.columns]
    return frame


def _coerce_ids(frame: pd.DataFrame) -> None:
    for column in ("user_id", "position_id"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype(np.int64)


def _content_matrix(profiles, jobs, skills, job_tags, user_index, item_index, edu_penalty: float = EDU_PENALTY):
    n_users = len(user_index)
    n_items = len(item_index)
    tag_ids = sorted(
        set(int(item) for item in skills["tag_id"].tolist() if len(skills))
        | set(int(item) for item in job_tags["tag_id"].tolist() if len(job_tags))
    )
    tag_index = {tag_id: index for index, tag_id in enumerate(tag_ids)}
    user_tag = np.zeros((n_users, max(len(tag_ids), 1)), dtype=np.float64)
    job_tag = np.zeros((n_items, max(len(tag_ids), 1)), dtype=np.float64)
    if len(skills) and tag_ids:
        for user_id, tag_id, proficiency in zip(skills["user_id"], skills["tag_id"], skills["proficiency"]):
            row = user_index.get(int(user_id))
            col = tag_index.get(int(tag_id))
            if row is not None and col is not None:
                user_tag[row, col] = max(user_tag[row, col], float(proficiency))
    if len(job_tags) and tag_ids:
        for position_id, tag_id in zip(job_tags["position_id"], job_tags["tag_id"]):
            row = item_index.get(int(position_id))
            col = tag_index.get(int(tag_id))
            if row is not None and col is not None:
                job_tag[row, col] = 1.0
    user_norm = np.linalg.norm(user_tag, axis=1, keepdims=True)
    job_norm = np.linalg.norm(job_tag, axis=1, keepdims=True)
    tag_cos = (user_tag / np.maximum(user_norm, 1e-12)) @ (job_tag / np.maximum(job_norm, 1e-12)).T
    tag_cos = np.clip(tag_cos, 0.0, 1.0)

    directions = [""] * n_users
    cities = [""] * n_users
    majors = [""] * n_users
    educations = np.full(n_users, 2, dtype=np.int64)
    for row in profiles.itertuples(index=False):
        index = user_index.get(int(row.user_id))
        if index is None:
            continue
        directions[index] = str(row.expect_direction or "")
        cities[index] = str(row.expect_city or "")
        majors[index] = str(row.major or "")
        educations[index] = int(row.education)
    job_directions = [""] * n_items
    job_cities = [""] * n_items
    job_edu = np.zeros(n_items, dtype=np.int64)
    job_text = [""] * n_items
    for row in jobs.itertuples(index=False):
        index = item_index.get(int(row.position_id))
        if index is None:
            continue
        job_directions[index] = str(row.tech_direction or "")
        job_cities[index] = str(row.city or "")
        job_edu[index] = int(row.education)
        requirement = str(row.requirement or "")[:500]
        job_text[index] = f"{row.title or ''} {requirement}"

    dir_match = np.zeros((n_users, n_items), dtype=np.float64)
    city_match = np.zeros((n_users, n_items), dtype=np.float64)
    by_dir: dict[str, list[int]] = defaultdict(list)
    by_city: dict[str, list[int]] = defaultdict(list)
    for index, name in enumerate(job_directions):
        if name:
            by_dir[name].append(index)
    for index, name in enumerate(job_cities):
        if name:
            by_city[name].append(index)
    for index, name in enumerate(directions):
        for col in by_dir.get(name, ()):
            dir_match[index, col] = 1.0
    for index, name in enumerate(cities):
        for col in by_city.get(name, ()):
            city_match[index, col] = 1.0
    edu_ok = (job_edu[None, :] == 0) | (job_edu[None, :] <= educations[:, None])
    major_hit = np.zeros((n_users, n_items), dtype=np.float64)
    for index, major in enumerate(majors):
        if len(major) < 2:
            continue
        hits = [col for col, text in enumerate(job_text) if major in text]
        if hits:
            major_hit[index, hits] = 1.0
    edu_score = edu_ok.astype(np.float64)
    content = 100.0 * (
        0.50 * tag_cos + 0.20 * dir_match + 0.16 * city_match + 0.08 * edu_score + 0.06 * major_hit
    )
    content = np.where(edu_ok, content, content * float(edu_penalty))
    content = np.clip(content, 0.0, 100.0)
    return content, {
        "directions": directions,
        "cities": cities,
        "majors": majors,
        "dir_match": dir_match,
        "city_match": city_match,
        "major_hit": major_hit,
    }


def _truth(held: set[tuple[int, int]], eligible_ids: set[int], user_index: dict[int, int]) -> dict[int, set[int]]:
    truth: dict[int, set[int]] = defaultdict(set)
    for user_id, position_id in held:
        if user_id not in user_index or position_id not in eligible_ids:
            continue
        truth[user_id].add(position_id)
    return {user_id: items for user_id, items in truth.items() if items}


def _applied_matrix(applications: pd.DataFrame, user_index, item_index, shape) -> np.ndarray:
    banned = np.zeros(shape, dtype=bool)
    if applications is None or len(applications) == 0:
        return banned
    for user_id, position_id in zip(applications["user_id"], applications["position_id"]):
        row = user_index.get(int(user_id))
        col = item_index.get(int(position_id))
        if row is not None and col is not None:
            banned[row, col] = True
    return banned


def _als_predict(spark, ratings: np.ndarray, user_ids: list[int], item_ids: list[int]) -> np.ndarray | None:
    rows, cols = np.nonzero(ratings > 0)
    if len(rows) < 20:
        logger.warning("评分过少，跳过 ALS")
        return None
    try:
        frame = spark.createDataFrame(
            [
                (int(user_ids[int(row)]), int(item_ids[int(col)]), float(ratings[int(row), int(col)]))
                for row, col in zip(rows, cols)
            ],
            schema=StructType(
                [
                    StructField("user_id", LongType(), False),
                    StructField("position_id", LongType(), False),
                    StructField("rating", DoubleType(), False),
                ]
            ),
        )
        model = ALS(
            userCol="user_id",
            itemCol="position_id",
            ratingCol="rating",
            implicitPrefs=True,
            rank=ALS_RANK,
            maxIter=ALS_ITER,
            regParam=ALS_REG,
            alpha=ALS_ALPHA,
            coldStartStrategy="drop",
            nonnegative=False,
            seed=42,
            checkpointInterval=20,
        ).fit(frame)
        user_factors = model.userFactors.toPandas()
        item_factors = model.itemFactors.toPandas()
        rank = ALS_RANK
        user_matrix = np.zeros((len(user_ids), rank), dtype=np.float64)
        item_matrix = np.zeros((len(item_ids), rank), dtype=np.float64)
        for _, record in user_factors.iterrows():
            vector = _vector(record["features"], rank)
            index = _index_of(user_ids, int(record["id"]))
            if index is not None:
                user_matrix[index, : len(vector)] = vector
        for _, record in item_factors.iterrows():
            vector = _vector(record["features"], rank)
            index = _index_of(item_ids, int(record["id"]))
            if index is not None:
                item_matrix[index, : len(vector)] = vector
        scores = user_matrix @ item_matrix.T
        return np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)
    except Exception:
        logger.exception("ALS 训练失败，回退用户余弦")
        return None


def _vector(value, rank: int) -> np.ndarray:
    if hasattr(value, "toArray"):
        array = np.asarray(value.toArray(), dtype=np.float64)
    else:
        array = np.asarray(list(value), dtype=np.float64)
    if len(array) >= rank:
        return array[:rank]
    padded = np.zeros(rank, dtype=np.float64)
    padded[: len(array)] = array
    return padded


def _index_of(ids: list[int], key: int) -> int | None:
    # ids 已排序，但这里用字典更稳；调用次数是因子行数，线性扫描 200 次也可接受
    try:
        return ids.index(key)
    except ValueError:
        return None


def _rank_metrics(scores, banned, user_ids, item_ids, truth, catalog_size) -> list[dict]:
    if scores is None:
        return []
    chosen = top_indices(scores, banned, max(EVAL_KS))
    rankings = materialize(user_ids, item_ids, chosen)
    return evaluate_rankings(rankings, truth, EVAL_KS, catalog_size)


def _tune_hybrid(cf_mm, content, popularity, activity, banned, user_ids, item_ids, truth, catalog_size) -> dict:
    best = {"alpha": 0.45, "fusion": "linear", "adaptive": True, "ndcg": -1.0}
    for fusion in ("linear", "gated"):
        for adaptive in (False, True):
            for alpha in ALPHAS:
                scores = fuse_scores(cf_mm, content, popularity, activity, alpha, fusion, adaptive)
                rows = _rank_metrics(scores, banned, user_ids, item_ids, truth, catalog_size)
                score = ndcg_at(rows, 10)
                if score > best["ndcg"] + 1e-9:
                    best = {"alpha": float(alpha), "fusion": fusion, "adaptive": adaptive, "ndcg": score}
                elif abs(score - best["ndcg"]) <= 1e-9:
                    best_blend = 0.15 <= best["alpha"] <= 0.85
                    cand_blend = 0.15 <= alpha <= 0.85
                    if cand_blend and not best_blend:
                        best = {"alpha": float(alpha), "fusion": fusion, "adaptive": adaptive, "ndcg": score}
    return best


def cosine_similarity_matrix(ratings: np.ndarray, shrink: float = SHRINK, neighbors: int = NEIGHBORS) -> np.ndarray:
    """cosine_predict 内部的邻居相似度矩阵（收缩、正相关、Top-N 掩码之后），用于等价性校验。"""
    n_users = ratings.shape[0]
    binary = (ratings > 0).astype(np.float64)
    norms = np.linalg.norm(ratings, axis=1)
    normed = ratings / np.maximum(norms, 1e-12)[:, None]
    sim = normed @ normed.T
    np.fill_diagonal(sim, 0.0)
    overlap = binary @ binary.T
    sim *= overlap / (overlap + shrink)
    inactive = norms <= 1e-8
    sim[inactive, :] = 0.0
    sim[:, inactive] = 0.0
    sim = np.clip(sim, 0.0, None)
    if n_users > 1 and neighbors > 0:
        k = min(neighbors, n_users - 1)
        top = np.argpartition(-sim, kth=k - 1, axis=1)[:, :k]
        mask = np.zeros_like(sim, dtype=bool)
        mask[np.arange(n_users)[:, None], top] = True
        sim = np.where(mask, sim, 0.0)
    return sim


def reference_run(spark) -> dict:
    """d8dc465 版 run_recommend 的计算部分（不写库），返回评估指标、相似度与生产 Top-N 列表。"""
    frames = _load(spark)
    events, jobs, profiles = frames["events"], frames["jobs"], frames["profiles"]
    eligible_ids = set(int(i) for i in jobs.loc[jobs["eligible"], "position_id"].tolist())
    job_ids = [int(i) for i in jobs["position_id"].tolist()]
    events = events[events["position_id"].isin(job_ids)].copy()
    ref_ts = float(events["ts"].max()) if len(events) else 0.0
    profile_ids = list(dict.fromkeys(int(i) for i in profiles["user_id"].tolist()))
    behavior_users = [int(i) for i in events["user_id"].unique().tolist()] if len(events) else []
    user_ids = sorted(set(profile_ids) | set(behavior_users))
    item_ids = sorted(set(job_ids))
    user_index = {u: i for i, u in enumerate(user_ids)}
    item_index = {p: i for i, p in enumerate(item_ids)}
    shape = (len(user_ids), len(item_ids))
    held = split_holdout(events)
    train_events = drop_pairs(events, held)
    train_grouped, train_pop = aggregate_frame(train_events, ref_ts)
    full_grouped, full_pop = aggregate_frame(events, ref_ts)
    train_ratings = fill_matrix(train_grouped, user_index, item_index, shape)
    full_ratings = fill_matrix(full_grouped, user_index, item_index, shape)
    content, _ = _content_matrix(profiles, jobs, frames["skills"], frames["job_tags"], user_index, item_index)
    eligible_row = np.array([i in eligible_ids for i in item_ids], dtype=bool)
    eval_banned = (train_ratings > 0) | ~eligible_row
    truth = _truth(held, eligible_ids, user_index)
    catalog = len(eligible_ids)
    t0 = time.perf_counter()
    cosine_eval = cosine_predict(train_ratings)
    cosine_seconds = time.perf_counter() - t0
    cosine_rows = _rank_metrics(cosine_eval, eval_banned, user_ids, item_ids, truth, catalog)
    activity_eval = (train_ratings > 0).sum(axis=1).astype(np.float64)
    pop_eval = popularity_scores(train_pop, item_index, shape[1])
    cf_mm_eval = minmax_rows(cosine_eval, eval_banned)
    best = _tune_hybrid(cf_mm_eval, content, pop_eval, activity_eval, eval_banned, user_ids, item_ids, truth, catalog)
    hybrid_rows = _rank_metrics(
        fuse_scores(cf_mm_eval, content, pop_eval, activity_eval, best["alpha"], best["fusion"], best["adaptive"]),
        eval_banned, user_ids, item_ids, truth, catalog,
    )
    content_rows = _rank_metrics(content, eval_banned, user_ids, item_ids, truth, catalog)
    popular_rows = _rank_metrics(np.broadcast_to(pop_eval, shape).copy(), eval_banned, user_ids, item_ids, truth, catalog)
    t0 = time.perf_counter()
    cf_full = cosine_predict(full_ratings)
    full_seconds = time.perf_counter() - t0
    sim_full = cosine_similarity_matrix(full_ratings)
    applied = _applied_matrix(frames["applications"], user_index, item_index, shape)
    prod_banned = applied | ~eligible_row
    activity_full = (full_ratings > 0).sum(axis=1).astype(np.float64)
    pop_full = popularity_scores(full_pop, item_index, shape[1])
    cf_mm = minmax_rows(cf_full, prod_banned)
    content_disp = np.clip(content, 0.0, 100.0)
    hybrid_full = fuse_scores(cf_mm, content_disp, pop_full, activity_full, best["alpha"], best["fusion"], best["adaptive"])
    rows = [user_index[u] for u in profile_ids if u in user_index]
    lists = {}
    for algo, scores in ((1, cf_mm), (2, content_disp), (3, hybrid_full)):
        chosen = top_indices(scores[rows], prod_banned[rows], TOP_N)
        for offset, row in enumerate(rows):
            items = [(int(item_ids[c]), float(scores[row, c])) for c in chosen[offset] if c >= 0]
            lists[(algo, int(user_ids[row]))] = items
    return {
        "user_ids": user_ids,
        "item_ids": item_ids,
        "sim_full": sim_full,
        "cf_full": cf_full,
        "full_ratings": full_ratings,
        "best": best,
        "cosine_rows": cosine_rows,
        "hybrid_rows": hybrid_rows,
        "content_rows": content_rows,
        "popular_rows": popular_rows,
        "lists": lists,
        "holdout_users": len(truth),
        "numpy_cosine_seconds": {"train": cosine_seconds, "full": full_seconds},
    }
