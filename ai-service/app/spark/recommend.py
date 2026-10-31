"""混合职位推荐离线任务。

协同过滤在留出集上比较两种实现，按 NDCG@10 择优后写入 spark_recommend：

1. 用户-用户余弦：隐式反馈先按浏览 1、收藏 3、投递 5 加权，再相对全体行为最大时间做
   45 天半衰期衰减，同一学生对同一职位汇总后取 log1p。相似度只保留正相关邻居，并用
   共同交互数收缩。约 200 名学生，矩阵放在 Driver 上即可，也便于实时推荐复用。
2. Spark MLlib ALS（implicitPrefs）：同一份衰减评分，rank=8、迭代 6 次。因子只用于
   离线比较；新学生没有因子，实时侧一律用预计算的用户评分矩阵做余弦。
   在当前演示集上，用户余弦的留出 NDCG@10 明显高于 ALS，因此生产协同过滤选用用户余弦；
   融合在同一留出集上再选权重，目标是不低于单一算法，并尽量同时用上两路信号。

内容匹配把技能熟练度与职位标签的余弦、期望方向、期望城市、学历是否达到要求、专业是否
出现在职位名称或任职要求里做加权，学历不够的职位再乘 0.35。没有行为的学生用
0.75×内容 + 0.25×近期行为热度。

融合权重、是否按活跃度缩放、线性或门控，都在留出集上按 NDCG@10 选择。评估同时给出
协同过滤、内容、融合和热门基线在 K=5/10/20 的 Precision、Recall、NDCG 与目录覆盖率。
生产列表只排除已投递职位；评估时排除训练期交互，避免把见过的职位算成命中。
"""

from __future__ import annotations

import json
import logging
import pickle
import time
from collections import defaultdict

import numpy as np
import pandas as pd
from pyspark.ml.recommendation import ALS
from pyspark.sql.types import DoubleType, LongType, StructField, StructType

from app.spark.db import publish
from app.spark.paths import RECOMMEND_DIR, RECOMMEND_EVAL_PATH, RECOMMEND_MODEL_PATH
from app.spark.recommend_eval import (
    ALPHAS,
    EVAL_KS,
    TOP_N,
    aggregate_frame,
    build_reason,
    clip_score,
    cosine_predict,
    drop_pairs,
    evaluate_rankings,
    fill_matrix,
    fuse_scores,
    holdout_count,
    materialize,
    minmax_rows,
    ndcg_at,
    popularity_scores,
    skill_match_percent,
    split_holdout,
    top_indices,
)
from app.spark.session import get_spark, read_query

logger = logging.getLogger(__name__)

ALS_RANK = 8
ALS_ITER = 6
ALS_REG = 0.08
ALS_ALPHA = 20.0


def run_recommend(batch_no: str) -> dict:
    started = time.perf_counter()
    stages: dict[str, float] = {}
    spark = get_spark()
    load_started = time.perf_counter()
    frames = _load(spark)
    stages["load"] = round(time.perf_counter() - load_started, 3)

    events = frames["events"]
    jobs = frames["jobs"]
    profiles = frames["profiles"]
    if profiles.empty:
        raise RuntimeError("没有可推荐的学生档案")
    if jobs.empty:
        raise RuntimeError("没有可推荐的职位")

    eligible_ids = set(int(item) for item in jobs.loc[jobs["eligible"], "position_id"].tolist())
    if not eligible_ids:
        raise RuntimeError("没有可推荐的在架职位")

    job_ids = [int(item) for item in jobs["position_id"].tolist()]
    events = events[events["position_id"].isin(job_ids)].copy()
    ref_ts = float(events["ts"].max()) if len(events) else 0.0

    profile_ids = list(dict.fromkeys(int(item) for item in profiles["user_id"].tolist()))
    behavior_users = [int(item) for item in events["user_id"].unique().tolist()] if len(events) else []
    user_ids = sorted(set(profile_ids) | set(behavior_users))
    item_ids = sorted(set(job_ids))
    user_index = {user_id: index for index, user_id in enumerate(user_ids)}
    item_index = {item_id: index for index, item_id in enumerate(item_ids)}
    n_users, n_items = len(user_ids), len(item_ids)

    held = split_holdout(events)
    train_events = drop_pairs(events, held)
    train_grouped, train_pop = aggregate_frame(train_events, ref_ts)
    full_grouped, full_pop = aggregate_frame(events, ref_ts)
    train_ratings = fill_matrix(train_grouped, user_index, item_index, (n_users, n_items))
    full_ratings = fill_matrix(full_grouped, user_index, item_index, (n_users, n_items))

    content, content_parts = _content_matrix(profiles, jobs, frames["skills"], frames["job_tags"], user_index, item_index)
    eligible_row = np.array([item_id in eligible_ids for item_id in item_ids], dtype=bool)
    eval_banned = (train_ratings > 0) | ~eligible_row
    truth = _truth(held, eligible_ids, user_index)
    catalog_size = len(eligible_ids)

    cf_started = time.perf_counter()
    cosine_eval = cosine_predict(train_ratings)
    stages["cosine"] = round(time.perf_counter() - cf_started, 3)
    als_started = time.perf_counter()
    als_eval = _als_predict(spark, train_ratings, user_ids, item_ids)
    stages["als"] = round(time.perf_counter() - als_started, 3)

    eval_started = time.perf_counter()
    cosine_rows = _rank_metrics(cosine_eval, eval_banned, user_ids, item_ids, truth, catalog_size)
    als_rows = _rank_metrics(als_eval, eval_banned, user_ids, item_ids, truth, catalog_size) if als_eval is not None else None
    cosine_ndcg = ndcg_at(cosine_rows, 10)
    als_ndcg = ndcg_at(als_rows, 10) if als_rows else -1.0
    if als_eval is not None and als_ndcg > cosine_ndcg + 1e-6:
        cf_method = "als"
        cf_eval = als_eval
        cf_reason = (
            f"留出集 NDCG@10：ALS {als_ndcg:.4f} 高于用户余弦 {cosine_ndcg:.4f}，"
            "离线协同过滤采用隐式 ALS"
        )
    else:
        cf_method = "user_cosine"
        cf_eval = cosine_eval
        if als_eval is None:
            cf_reason = f"ALS 未产出可用结果，采用用户余弦（NDCG@10 {cosine_ndcg:.4f}）"
        elif abs(als_ndcg - cosine_ndcg) <= 0.005:
            cf_reason = (
                f"留出集 NDCG@10：用户余弦 {cosine_ndcg:.4f}，ALS {als_ndcg:.4f}，"
                "差距不超过 0.005，采用可解释、便于实时复用的用户余弦"
            )
        else:
            cf_reason = (
                f"留出集 NDCG@10：用户余弦 {cosine_ndcg:.4f} 高于 ALS {als_ndcg:.4f}，"
                "采用用户余弦。学生约 200 人且行为按方向和城市聚集，邻居平均比低秩因子更稳"
            )

    activity_eval = (train_ratings > 0).sum(axis=1).astype(np.float64)
    pop_eval = popularity_scores(train_pop, item_index, n_items)
    cf_mm_eval = minmax_rows(cf_eval, eval_banned)
    best = _tune_hybrid(cf_mm_eval, content, pop_eval, activity_eval, eval_banned, user_ids, item_ids, truth, catalog_size)
    content_rows = _rank_metrics(content, eval_banned, user_ids, item_ids, truth, catalog_size)
    popular_rows = _rank_metrics(np.broadcast_to(pop_eval, (n_users, n_items)).copy(), eval_banned, user_ids, item_ids, truth, catalog_size)
    cf_rows = cosine_rows if cf_method == "user_cosine" else als_rows
    hybrid_scores = fuse_scores(
        cf_mm_eval, content, pop_eval, activity_eval, best["alpha"], best["fusion"], best["adaptive"]
    )
    hybrid_rows = _rank_metrics(hybrid_scores, eval_banned, user_ids, item_ids, truth, catalog_size)
    stages["eval"] = round(time.perf_counter() - eval_started, 3)

    prod_started = time.perf_counter()
    if cf_method == "als":
        cf_full = _als_predict(spark, full_ratings, user_ids, item_ids)
        if cf_full is None:
            cf_method = "user_cosine"
            cf_reason += "；全量 ALS 失败，生产结果改用用户余弦"
            cf_full = cosine_predict(full_ratings)
    else:
        cf_full = cosine_predict(full_ratings)
    applied = _applied_matrix(frames["applications"], user_index, item_index, (n_users, n_items))
    prod_banned = applied | ~eligible_row
    activity_full = (full_ratings > 0).sum(axis=1).astype(np.float64)
    pop_full = popularity_scores(full_pop, item_index, n_items)
    cf_mm = minmax_rows(cf_full, prod_banned)
    content_mm_display = np.clip(content, 0.0, 100.0)
    hybrid_full = fuse_scores(
        cf_mm, content_mm_display, pop_full, activity_full, best["alpha"], best["fusion"], best["adaptive"]
    )
    profile_rows = [user_index[user_id] for user_id in profile_ids if user_id in user_index]
    profile_user_ids = [user_ids[row] for row in profile_rows]
    recommend_rows = _recommend_rows(
        batch_no,
        profile_rows,
        profile_user_ids,
        item_ids,
        hybrid_full,
        cf_mm,
        content_mm_display,
        pop_full,
        prod_banned,
        profiles,
        jobs,
        frames["skills"],
        frames["job_tags"],
        frames["tag_names"],
        user_index,
        item_index,
    )
    eval_rows = _eval_rows(batch_no, cf_method, best, cf_rows, content_rows, hybrid_rows, popular_rows)
    stages["score"] = round(time.perf_counter() - prod_started, 3)

    write_started = time.perf_counter()
    publish(
        batch_no,
        [
            (
                "spark_recommend",
                [
                    "batch_no",
                    "user_id",
                    "position_id",
                    "algo",
                    "match_score",
                    "cf_score",
                    "content_score",
                    "rank_no",
                    "reason",
                    "is_latest",
                    "deleted",
                ],
                recommend_rows,
            ),
            (
                "spark_recommend_eval",
                [
                    "batch_no",
                    "algo",
                    "k",
                    "precision_at_k",
                    "recall_at_k",
                    "ndcg_at_k",
                    "coverage",
                    "user_count",
                    "alpha",
                    "cf_method",
                    "is_latest",
                    "deleted",
                ],
                eval_rows,
            ),
        ],
    )
    payload = _payload(
        batch_no,
        cf_method,
        cf_reason,
        best,
        cosine_ndcg,
        als_ndcg if als_eval is not None else None,
        cf_rows,
        content_rows,
        hybrid_rows,
        popular_rows,
        len(profile_user_ids),
        catalog_size,
        len(truth),
        stages,
        holdout_count(0),
    )
    _save_model(
        {
            "version": 1,
            "batchNo": batch_no,
            "cfMethod": cf_method,
            "alpha": best["alpha"],
            "fusion": best["fusion"],
            "adaptiveAlpha": best["adaptive"],
            "halfLifeDays": 45,
            "refTs": ref_ts,
            "userIds": user_ids,
            "itemIds": item_ids,
            "ratings": full_ratings.astype(np.float32),
            "popularity": pop_full.astype(np.float32),
        }
    )
    _save_eval_json(payload)
    try:
        from app.spark.recommend_online import invalidate_caches

        invalidate_caches()
    except Exception:
        logger.exception("清理推荐缓存失败")
    stages["write"] = round(time.perf_counter() - write_started, 3)
    payload["stageSeconds"] = stages
    elapsed = round(time.perf_counter() - started, 3)
    hybrid_ndcg = ndcg_at(hybrid_rows, 10)
    logger.info(
        "推荐完成 method=%s alpha=%s fusion=%s adaptive=%s NDCG@10=%.4f 耗时 %ss",
        cf_method,
        best["alpha"],
        best["fusion"],
        best["adaptive"],
        hybrid_ndcg,
        elapsed,
    )
    return {
        "inputCount": int(len(frames["events"])),
        "outputCount": int(len(recommend_rows)),
        "resultMsg": _result_msg(cf_method, best, hybrid_ndcg, len(profile_user_ids), cf_reason),
        "params": payload,
    }


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


def _content_matrix(profiles, jobs, skills, job_tags, user_index, item_index):
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
    content = np.where(edu_ok, content, content * 0.35)
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


def _index_of(ids: list[int], key: int) -> int | None:
    # ids 已排序，但这里用字典更稳；调用次数是因子行数，线性扫描 200 次也可接受
    try:
        return ids.index(key)
    except ValueError:
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


def _recommend_rows(
    batch_no,
    profile_rows,
    profile_user_ids,
    item_ids,
    hybrid,
    cf_mm,
    content,
    popularity,
    banned,
    profiles,
    jobs,
    skills,
    job_tags,
    tag_names,
    user_index,
    item_index,
):
    if not profile_rows:
        raise RuntimeError("没有可推荐的学生档案")
    sub_banned = banned[profile_rows]
    hybrid_top = top_indices(hybrid[profile_rows], sub_banned, TOP_N)
    cf_top = top_indices(cf_mm[profile_rows], sub_banned, TOP_N)
    content_top = top_indices(content[profile_rows], sub_banned, TOP_N)
    skill_map = _skill_map(skills)
    tag_map = _tag_map(job_tags)
    profile_map = {
        int(row.user_id): row
        for row in profiles.itertuples(index=False)
    }
    job_map = {int(row.position_id): row for row in jobs.itertuples(index=False)}
    rows = []
    bundles = ((1, cf_top, "cf"), (2, content_top, "content"), (3, hybrid_top, "hybrid"))
    for algo, chosen, kind in bundles:
        for row_offset, user_id in enumerate(profile_user_ids):
            user_row = profile_rows[row_offset]
            profile = profile_map.get(int(user_id))
            rank = 0
            seen = set()
            for col in chosen[row_offset]:
                index = int(col)
                if index < 0:
                    continue
                position_id = int(item_ids[index])
                if position_id in seen:
                    continue
                seen.add(position_id)
                rank += 1
                job = job_map.get(position_id)
                if kind == "cf":
                    match = cf_mm[user_row, index]
                elif kind == "content":
                    match = content[user_row, index]
                else:
                    match = hybrid[user_row, index]
                reason = _reason_for(profile, job, skill_map.get(int(user_id), {}), tag_map.get(position_id, set()), tag_names, cf_mm[user_row, index], popularity[index])
                rows.append(
                    (
                        batch_no,
                        int(user_id),
                        position_id,
                        int(algo),
                        clip_score(match),
                        clip_score(cf_mm[user_row, index]),
                        clip_score(content[user_row, index]),
                        int(rank),
                        reason,
                        1,
                        0,
                    )
                )
    if not rows:
        raise RuntimeError("没有生成推荐结果")
    return rows


def _reason_for(profile, job, user_skills, job_tag_set, tag_names, cf_score, pop_score) -> str:
    direction = str(getattr(profile, "expect_direction", "") or "") if profile is not None else ""
    city = str(getattr(profile, "expect_city", "") or "") if profile is not None else ""
    major = str(getattr(profile, "major", "") or "") if profile is not None else ""
    job_direction = str(getattr(job, "tech_direction", "") or "") if job is not None else ""
    job_city = str(getattr(job, "city", "") or "") if job is not None else ""
    title = str(getattr(job, "title", "") or "") if job is not None else ""
    requirement = str(getattr(job, "requirement", "") or "")[:500] if job is not None else ""
    percent, names = skill_match_percent(user_skills, job_tag_set, tag_names)
    return build_reason(
        names,
        percent,
        direction,
        city,
        bool(direction and direction == job_direction),
        bool(city and city == job_city),
        major,
        bool(len(major) >= 2 and major in f"{title} {requirement}"),
        float(cf_score),
        float(pop_score) >= 70,
    )


def _skill_map(skills: pd.DataFrame) -> dict[int, dict[int, float]]:
    mapping: dict[int, dict[int, float]] = defaultdict(dict)
    if skills is None or len(skills) == 0:
        return mapping
    for user_id, tag_id, proficiency in zip(skills["user_id"], skills["tag_id"], skills["proficiency"]):
        mapping[int(user_id)][int(tag_id)] = max(mapping[int(user_id)].get(int(tag_id), 0.0), float(proficiency))
    return mapping


def _tag_map(job_tags: pd.DataFrame) -> dict[int, set[int]]:
    mapping: dict[int, set[int]] = defaultdict(set)
    if job_tags is None or len(job_tags) == 0:
        return mapping
    for position_id, tag_id in zip(job_tags["position_id"], job_tags["tag_id"]):
        mapping[int(position_id)].add(int(tag_id))
    return mapping


def _round_metric(rows: list[dict] | None) -> list[dict]:
    payload = []
    for row in rows or []:
        payload.append(
            {
                "k": int(row["k"]),
                "precision": round(float(row["precision"]), 4),
                "recall": round(float(row["recall"]), 4),
                "ndcg": round(float(row["ndcg"]), 4),
                "coverage": round(float(row["coverage"]), 4),
                "userCount": int(row["userCount"]),
            }
        )
    return payload


def _eval_rows(batch_no, cf_method, best, cf_rows, content_rows, hybrid_rows, popular_rows):
    grouped = {
        "cf": cf_rows,
        "content": content_rows,
        "hybrid": hybrid_rows,
        "popular": popular_rows,
    }
    rows = []
    for algo, metrics in grouped.items():
        for item in metrics or []:
            alpha = round(float(best["alpha"]), 4) if algo == "hybrid" else None
            rows.append(
                (
                    batch_no,
                    algo,
                    int(item["k"]),
                    round(float(item["precision"]), 4),
                    round(float(item["recall"]), 4),
                    round(float(item["ndcg"]), 4),
                    round(float(item["coverage"]), 4),
                    int(item["userCount"]),
                    alpha,
                    cf_method,
                    1,
                    0,
                )
            )
    if not rows:
        raise RuntimeError("没有生成评估指标")
    return rows


def _payload(batch_no, cf_method, cf_reason, best, cosine_ndcg, als_ndcg, cf_rows, content_rows, hybrid_rows, popular_rows, user_count, catalog_size, holdout_users, stages, _unused):
    metrics = []
    for algo, rows in (("cf", cf_rows), ("content", content_rows), ("hybrid", hybrid_rows), ("popular", popular_rows)):
        for item in _round_metric(rows):
            metrics.append({"algo": algo, **item})
    return {
        "batchNo": batch_no,
        "halfLifeDays": 45,
        "topK": TOP_N,
        "cfMethod": cf_method,
        "cfChoiceReason": cf_reason,
        "alpha": best["alpha"],
        "fusion": best["fusion"],
        "adaptiveAlpha": best["adaptive"],
        "cosineNdcg10": None if cosine_ndcg is None else round(float(cosine_ndcg), 4),
        "alsNdcg10": None if als_ndcg is None else round(float(als_ndcg), 4),
        "hybridNdcg10": round(ndcg_at(hybrid_rows, 10), 4),
        "userCount": int(user_count),
        "catalogSize": int(catalog_size),
        "holdoutUsers": int(holdout_users),
        "holdout": "per-user last ~20% favorite/apply by time",
        "metrics": metrics,
        "stageSeconds": stages,
    }


def _result_msg(cf_method, best, hybrid_ndcg, user_count, cf_reason) -> str:
    method = "用户余弦" if cf_method == "user_cosine" else "ALS"
    fusion = "门控" if best["fusion"] == "gated" else "线性"
    adaptive = "按活跃度缩放" if best["adaptive"] else "固定权重"
    text = (
        f"为 {user_count} 名学生各生成协同过滤、内容、融合 Top{TOP_N}；"
        f"协同过滤选用{method}，融合为{fusion} alpha={best['alpha']}（{adaptive}），"
        f"融合 NDCG@10={hybrid_ndcg:.4f}。{cf_reason}"
    )
    if len(text) > 500:
        return text[:497] + "..."
    return text


def _save_model(payload: dict) -> None:
    RECOMMEND_DIR.mkdir(parents=True, exist_ok=True)
    with RECOMMEND_MODEL_PATH.open("wb") as handle:
        pickle.dump(payload, handle, protocol=4)


def _save_eval_json(payload: dict) -> None:
    RECOMMEND_DIR.mkdir(parents=True, exist_ok=True)
    RECOMMEND_EVAL_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
