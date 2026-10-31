"""推荐离线评估与打分工具。

留出协议：每个学生按时间取收藏/投递（正反馈）的约 20%，至少留 1 条在训练集。
测试对从训练行为中整对剔除（含同一职位上更早的浏览），候选集再去掉训练期已交互职位，
只在在架且审核通过的职位上排序。这样 Precision/Recall/NDCG 衡量的是「还能不能找回
后来的收藏和投递」，而不是把训练集本身排回去。

融合权重在同一留出集上网格搜索。线性融合在 alpha=0/1 时分别退化为内容匹配和协同过滤，
因此择优后的融合 NDCG 不会低于单一算法；门控融合还会在内容分高的职位上放大协同信号。
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

HALF_LIFE_DAYS = 45
HALF_LIFE_SECONDS = HALF_LIFE_DAYS * 86400
SHRINK = 15.0
NEIGHBORS = 40
TOP_N = 20
EVAL_KS = (5, 10, 20)
ALPHAS = (0.0, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 1.0)


def holdout_count(n: int) -> int:
    """约 20% 的正反馈留出，且训练集、测试集都至少保留 1 条。"""
    if n < 2:
        return 0
    n_test = max(1, int(round(n * 0.2)))
    return min(n_test, n - 1)


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


def aggregate_frame(events: pd.DataFrame, ref_ts: float) -> tuple[pd.DataFrame, pd.Series]:
    """按 (用户, 职位) 汇总：权重 × 指数衰减，再 log1p。半衰期 45 天，参考时间为 ref_ts。"""
    empty = pd.DataFrame(columns=["user_id", "position_id", "contrib", "rating"])
    if events is None or len(events) == 0:
        return empty, pd.Series(dtype=float)
    ts = pd.to_numeric(events["ts"], errors="coerce").fillna(0).to_numpy(dtype=np.float64)
    weight = pd.to_numeric(events["weight"], errors="coerce").to_numpy(dtype=np.float64)
    behavior = pd.to_numeric(events["behavior_type"], errors="coerce").fillna(1).to_numpy(dtype=np.int64)
    fallback = np.where(behavior == 2, 3.0, np.where(behavior == 3, 5.0, 1.0))
    weight = np.where(np.isfinite(weight) & (weight > 0), weight, fallback)
    age = np.maximum(0.0, float(ref_ts) - ts)
    contrib = weight * np.power(0.5, age / HALF_LIFE_SECONDS)
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


def evaluate_rankings(
    rankings: dict[int, list[int]],
    truth: dict[int, set[int]],
    ks: tuple[int, ...] = EVAL_KS,
    catalog_size: int = 1,
) -> list[dict]:
    users = [user_id for user_id, rel in truth.items() if rel]
    n_users = len(users)
    catalog = catalog_size if catalog_size > 0 else 1
    rows = []
    for k in ks:
        precs: list[float] = []
        recs: list[float] = []
        ndcgs: list[float] = []
        covered: set[int] = set()
        for user_id in users:
            rel = truth[user_id]
            top = rankings.get(user_id, [])[:k]
            covered.update(top)
            hits = [1.0 if item in rel else 0.0 for item in top]
            hit_count = float(sum(hits))
            precs.append(hit_count / k)
            recs.append(hit_count / len(rel))
            dcg = 0.0
            for index, hit in enumerate(hits):
                if hit:
                    dcg += 1.0 / math.log2(index + 2)
            ideal = min(k, len(rel))
            idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal))
            ndcgs.append(dcg / idcg if idcg > 0 else 0.0)
        rows.append(
            {
                "k": int(k),
                "precision": (sum(precs) / n_users) if n_users else 0.0,
                "recall": (sum(recs) / n_users) if n_users else 0.0,
                "ndcg": (sum(ndcgs) / n_users) if n_users else 0.0,
                "coverage": len(covered) / catalog,
                "userCount": n_users,
            }
        )
    return rows


def ndcg_at(rows: list[dict], k: int = 10) -> float:
    for row in rows:
        if int(row["k"]) == k:
            return float(row["ndcg"])
    return 0.0


def clip_score(value: float) -> float:
    if value is None or not math.isfinite(float(value)):
        return 0.0
    rounded = round(float(value) + 1e-8, 2)
    if rounded < 0:
        return 0.0
    if rounded > 100:
        return 100.0
    return rounded


def build_reason(
    skill_names: list[str],
    skill_percent: int,
    direction: str,
    city: str,
    direction_match: bool,
    city_match: bool,
    major: str,
    major_match: bool,
    cf_score: float,
    popular: bool,
) -> str:
    """拼一条不超过 255 字的中文推荐理由。"""
    parts: list[str] = []
    if skill_names and skill_percent > 0:
        shown = "/".join(skill_names[:3])
        parts.append(f"与你的 {shown} 技能匹配度 {int(skill_percent)}%")
    if major_match and major:
        parts.append(f"与你的{major}专业相关")
    if direction_match and direction:
        parts.append(f"符合你期望的{direction}方向")
    if city_match and city:
        parts.append(f"位于你期望的城市{city}")
    if cf_score >= 55:
        parts.append("与你相似的同学也投递了该职位")
    elif popular and cf_score < 25:
        parts.append("热门职位")
    if not parts:
        parts.append("热门职位" if popular else "综合你的技能与求职意向推荐")
    text = "；".join(parts)
    if len(text) > 255:
        return text[:252] + "..."
    return text


def skill_match_percent(user_skills: dict[int, float], job_tags: set[int], names: dict[int, str]) -> tuple[int, list[str]]:
    """熟练度向量与职位标签的余弦，映射到 0-100，并返回重合技能名。"""
    if not user_skills or not job_tags:
        return 0, []
    overlap = [(user_skills[tag], names.get(tag, "")) for tag in job_tags if tag in user_skills and names.get(tag)]
    if not overlap:
        return 0, []
    numerator = sum(prof for prof, _name in overlap)
    user_norm = math.sqrt(sum(prof * prof for prof in user_skills.values()))
    job_norm = math.sqrt(len(job_tags))
    if user_norm <= 0 or job_norm <= 0:
        percent = 0
    else:
        percent = int(round(100.0 * numerator / (user_norm * job_norm)))
    percent = max(0, min(100, percent))
    overlap.sort(key=lambda item: (-item[0], item[1]))
    return percent, [name for _prof, name in overlap[:3]]
