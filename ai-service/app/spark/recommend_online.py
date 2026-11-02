"""单用户实时推荐与相似职位（在线服务侧，不启动 Spark，也不依赖 numpy / pandas）。

分工：离线 Spark 任务（recommend.py / recommend_cf.py）计算全体学生的衰减评分、
用户余弦相似度与 Top-40 邻居，邻居写入 spark_user_neighbor，稀疏评分导出到 cf_model.pkl。
在线侧只做「查表 + 小规模加权求和」：

* 已在离线批次里有邻居的学生：直接读 spark_user_neighbor（is_latest=1）的邻居与相似度，
  预测 = Σ sim·r_v / Σ sim，r_v 取自离线导出的稀疏评分，不再重算相似度；
* 离线批次之后才产生行为的新学生：用其实时行为按同一公式（45 天半衰期、log1p、
  共现收缩、Top-40 正相关邻居）对离线评分做一次倒排索引余弦，只涉及与他有共同职位的学生；
* 没有行为：退化为内容分与热门分。

内容分按当前档案和技能现算，所以改简历/技能后刷新推荐立即生效。
相似职位按标签 Jaccard、方向和城市，有模型时再加一点共现。
"""

from __future__ import annotations

import logging
import math
import pickle
import threading
import time
from collections import defaultdict

from app.spark.db import connect
from app.spark.paths import RECOMMEND_MODEL_PATH
from app.spark.recommend_eval import (
    HALF_LIFE_DAYS,
    NEIGHBORS,
    SHRINK,
    build_reason,
    clip_score,
    skill_match_percent,
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_catalog = {"at": 0.0, "data": None}
_model = {"mtime": None, "data": None}
CATALOG_TTL = 120.0


def invalidate_caches() -> None:
    with _lock:
        _catalog["at"] = 0.0
        _catalog["data"] = None
        _model["mtime"] = None
        _model["data"] = None


def load_model():
    """读取离线导出的稀疏模型，并建好倒排索引与范数。旧版（稠密矩阵）模型不再兼容，返回 None。"""
    path = RECOMMEND_MODEL_PATH
    if not path.is_file():
        return None
    mtime = path.stat().st_mtime
    with _lock:
        if _model["data"] is not None and _model["mtime"] == mtime:
            return _model["data"]
    try:
        with path.open("rb") as handle:
            data = pickle.load(handle)
    except Exception:
        logger.exception("读取推荐模型失败")
        return None
    if not isinstance(data, dict) or int(data.get("version") or 0) < 2 or not isinstance(data.get("ratings"), dict):
        logger.warning("推荐模型版本过旧，请重新运行 Spark 推荐任务")
        return None
    ratings: dict[int, dict[int, float]] = {
        int(user): {int(item): float(value) for item, value in row.items() if float(value) > 0}
        for user, row in data["ratings"].items()
    }
    by_item: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for user, row in ratings.items():
        for item, value in row.items():
            by_item[item].append((user, value))
    data["ratings"] = ratings
    data["byItem"] = dict(by_item)
    data["norms"] = {user: math.sqrt(sum(v * v for v in row.values())) for user, row in ratings.items()}
    data["popularity"] = {int(k): float(v) for k, v in (data.get("popularity") or {}).items()}
    with _lock:
        _model["data"] = data
        _model["mtime"] = mtime
    return data


def load_catalog(force: bool = False) -> dict:
    now = time.time()
    with _lock:
        cached = _catalog["data"]
        loaded_at = _catalog["at"]
    if cached is not None and not force and now - loaded_at < CATALOG_TTL:
        return cached
    data = _query_catalog()
    with _lock:
        _catalog["data"] = data
        _catalog["at"] = time.time()
    return data


def decayed_ratings(events: list[dict], ref_ts: float, half_life_days: float = HALF_LIFE_DAYS) -> dict[int, float]:
    """与离线 recommend_cf.implicit_ratings 同一公式：权重 × 0.5^(age/半衰期)，按职位求和后 log1p。"""
    sums: dict[int, float] = defaultdict(float)
    for row in events:
        weight = row.get("weight")
        behavior = int(row.get("behavior_type") or 1)
        if weight is None or not math.isfinite(float(weight)) or float(weight) <= 0:
            weight = 3.0 if behavior == 2 else 5.0 if behavior == 3 else 1.0
        age = max(0.0, float(ref_ts) - float(row.get("ts") or 0.0))
        sums[int(row["position_id"])] += float(weight) * math.pow(0.5, age / (float(half_life_days) * 86400.0))
    return {item: math.log1p(total) for item, total in sums.items() if math.log1p(total) > 0}


def neighbors_from_table(user_id: int, batch_no: str | None) -> list[tuple[int, float]]:
    """读取离线 Spark 写入的邻居（只取与当前模型同一批次的生效行）。"""
    conn = connect()
    try:
        with conn.cursor() as cur:
            sql = (
                "SELECT neighbor_id, similarity FROM spark_user_neighbor "
                "WHERE user_id = %s AND is_latest = 1 AND deleted = 0"
            )
            args: list = [int(user_id)]
            if batch_no:
                sql += " AND batch_no = %s"
                args.append(batch_no)
            cur.execute(sql + " ORDER BY rank_no", args)
            rows = cur.fetchall()
    except Exception:
        logger.exception("读取 spark_user_neighbor 失败")
        return []
    finally:
        conn.close()
    return [(int(row["neighbor_id"]), float(row["similarity"])) for row in rows if float(row["similarity"]) > 0]


def neighbors_on_the_fly(user_vec: dict[int, float], model: dict, self_id: int | None = None) -> list[tuple[int, float]]:
    """新学生的近邻：倒排索引只遍历与其有共同职位的学生，公式同离线 Spark。"""
    user_norm = math.sqrt(sum(v * v for v in user_vec.values()))
    if user_norm < 1e-8:
        return []
    dots: dict[int, float] = defaultdict(float)
    overlap: dict[int, int] = defaultdict(int)
    for item, value in user_vec.items():
        for other, other_value in model["byItem"].get(item, ()):
            if other == self_id:
                continue
            dots[other] += value * other_value
            overlap[other] += 1
    sims = []
    for other, dot in dots.items():
        norm = model["norms"].get(other, 0.0)
        if norm <= 1e-8:
            continue
        co = overlap[other]
        sim = dot / (norm * user_norm) * (co / (co + SHRINK))
        if sim > 0:
            sims.append((other, sim))
    sims.sort(key=lambda item: (-item[1], item[0]))
    return sims[:NEIGHBORS]


def predict_from_neighbors(neighbors: list[tuple[int, float]], model: dict) -> dict[int, float]:
    denom = sum(sim for _other, sim in neighbors)
    if denom <= 1e-12:
        return {}
    scores: dict[int, float] = defaultdict(float)
    for other, sim in neighbors:
        for item, value in model["ratings"].get(other, {}).items():
            scores[item] += sim * value
    return {item: value / denom for item, value in scores.items()}


def _minmax(values: list[float], banned: list[bool]) -> list[float]:
    """单行 min-max 到 0-100，口径同离线（全 0 → 0，平坦且大于 0 → 100，屏蔽位 0）。"""
    live = [v for v, b in zip(values, banned) if not b]
    if not live:
        return [0.0] * len(values)
    lo, hi = min(live), max(live)
    out = []
    for value, blocked in zip(values, banned):
        if blocked or hi <= 1e-8:
            out.append(0.0)
        elif hi - lo > 1e-6:
            out.append(max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0)))
        else:
            out.append(100.0)
    return out


def _fuse(cf_mm: float, content: float, popularity: float, activity: float, cold: bool, alpha: float, fusion: str, adaptive: bool) -> float:
    if cold:
        mixed = 0.75 * content + 0.25 * popularity
    else:
        alpha_u = alpha * (0.25 + 0.75 * max(0.0, min(1.0, activity / 8.0))) if adaptive else alpha
        if fusion == "gated":
            mixed = content * ((1.0 - alpha_u) + alpha_u * (cf_mm / 100.0))
        else:
            mixed = alpha_u * cf_mm + (1.0 - alpha_u) * content
    return max(0.0, min(100.0, mixed))


def recommend_for_user(user_id: int, top_k: int = 10) -> dict:
    top_k = max(1, min(int(top_k), 50))
    catalog = load_catalog()
    model = load_model()
    profile = _profile(user_id)
    skills = _skills(user_id)
    events = _events(user_id)
    applied = _applied(user_id)
    jobs = list(catalog["jobs"].values())
    if not jobs:
        return _empty(user_id, model)

    item_ids = [int(job["id"]) for job in jobs]
    major = str((profile or {}).get("major") or "")
    direction = str((profile or {}).get("expectDirection") or "")
    city = str((profile or {}).get("expectCity") or "")
    education = int((profile or {}).get("education") or 0)
    content = [_content_one(skills, major, direction, city, education, job, catalog["tagNames"]) for job in jobs]

    ref_ts = float(model["refTs"]) if model and model.get("refTs") is not None else 0.0
    if events:
        ref_ts = max(ref_ts, max(float(row["ts"]) for row in events))
    ratings = decayed_ratings(events, ref_ts) if events else {}
    activity = float(len(ratings))
    cf_source = "none"
    raw_scores: dict[int, float] = {}
    if model and ratings:
        neighbors = neighbors_from_table(user_id, model.get("batchNo"))
        cf_source = "spark_neighbor_table"
        if not neighbors:
            neighbors = neighbors_on_the_fly(ratings, model, self_id=int(user_id))
            cf_source = "on_the_fly"
        raw_scores = predict_from_neighbors(neighbors, model)
    cf = [float(raw_scores.get(position_id, 0.0)) for position_id in item_ids]

    pop_map = (model or {}).get("popularity") or {}
    popularity = [float(pop_map.get(position_id, 0.0)) for position_id in item_ids]
    if max(popularity, default=0.0) <= 0:
        counts = [float(job["applyCount"]) for job in jobs]
        peak = max(counts, default=0.0)
        popularity = [0.0] * len(jobs) if peak <= 0 else [100.0 * math.log1p(c) / math.log1p(peak) for c in counts]

    banned = [position_id in applied for position_id in item_ids]
    cf_mm = _minmax(cf, banned)
    alpha = float(model["alpha"]) if model and model.get("alpha") is not None else 0.45
    fusion = model.get("fusion") if model else "gated"
    adaptive = bool(model.get("adaptiveAlpha")) if model else True
    if fusion not in ("linear", "gated"):
        fusion = "gated"
    cold = activity <= 0 or max(cf_mm, default=0.0) <= 0
    hybrid = [
        -1.0 if banned[i] else _fuse(cf_mm[i], content[i], popularity[i], activity, cold, alpha, fusion, adaptive)
        for i in range(len(jobs))
    ]
    order = sorted(range(len(jobs)), key=lambda i: (-hybrid[i], i))
    items = []
    for position_index in order:
        if hybrid[position_index] < 0:
            continue
        if len(items) >= top_k:
            break
        job = jobs[position_index]
        percent, names = skill_match_percent(skills, set(job["tags"]), catalog["tagNames"])
        text = f"{job['title']} {job.get('requirement') or ''}"[:500]
        reason = build_reason(
            names,
            percent,
            direction,
            city,
            bool(direction and direction == job["techDirection"]),
            bool(city and city == job["city"]),
            major,
            bool(len(major) >= 2 and major in text),
            float(cf_mm[position_index]),
            float(popularity[position_index]) >= 70,
        )
        items.append(
            {
                "positionId": job["id"],
                "title": job["title"],
                "companyName": job["companyName"],
                "city": job["city"],
                "province": job["province"],
                "salaryMin": job["salaryMin"],
                "salaryMax": job["salaryMax"],
                "salaryMonths": job["salaryMonths"],
                "education": job["education"],
                "techDirection": job["techDirection"],
                "tagNames": [catalog["tagNames"].get(tag, "") for tag in job["tags"] if catalog["tagNames"].get(tag)],
                "matchScore": clip_score(hybrid[position_index] if hybrid[position_index] >= 0 else 0),
                "cfScore": clip_score(cf_mm[position_index]),
                "contentScore": clip_score(content[position_index]),
                "rankNo": len(items) + 1,
                "reason": reason,
            }
        )
    return {
        "userId": int(user_id),
        "source": "realtime",
        "strategy": "hybrid" if model else "content_popular",
        "cfMethod": (model or {}).get("cfMethod") or "user_cosine",
        "cfSource": cf_source,
        "coldStart": bool(cold),
        "halfLifeDays": HALF_LIFE_DAYS,
        "items": items,
    }


def similar_jobs(job_id: int, top_k: int = 6) -> dict:
    from app.core.response import AppException

    top_k = max(1, min(int(top_k), 50))
    catalog = load_catalog()
    anchor = catalog["jobs"].get(int(job_id))
    if anchor is None:
        catalog = load_catalog(force=True)
        anchor = catalog["jobs"].get(int(job_id))
    if anchor is None:
        raise AppException("职位不存在或已下架", code=404)
    anchor_tags = set(anchor["tags"])
    co_norm = _cooccurrence(int(job_id))
    scored = []
    for job in catalog["jobs"].values():
        if job["id"] == anchor["id"]:
            continue
        other_tags = set(job["tags"])
        union = anchor_tags | other_tags
        jaccard = (len(anchor_tags & other_tags) / len(union)) if union else 0.0
        same_dir = 1.0 if job["techDirection"] and job["techDirection"] == anchor["techDirection"] else 0.0
        same_city = 1.0 if job["city"] and job["city"] == anchor["city"] else 0.0
        score = 0.65 * jaccard + 0.20 * same_dir + 0.15 * same_city
        if co_norm is not None:
            score = 0.85 * score + 0.15 * float(co_norm.get(job["id"], 0.0))
        parts = []
        if jaccard > 0:
            parts.append("技能标签重合")
        if same_dir:
            parts.append(f"同为{job['techDirection']}")
        if same_city:
            parts.append(f"同在{job['city']}")
        if not parts:
            parts.append("综合相似")
        scored.append((score, job, "，".join(parts)))
    scored.sort(key=lambda item: (-item[0], -item[1]["applyCount"], item[1]["id"]))
    top = scored[:top_k]
    peak = top[0][0] if top else 0.0
    items = []
    for score, job, reason in top:
        similarity = 0.0 if peak <= 0 else round(100.0 * score / peak, 2)
        items.append(
            {
                "positionId": job["id"],
                "title": job["title"],
                "companyName": job["companyName"],
                "city": job["city"],
                "province": job["province"],
                "salaryMin": job["salaryMin"],
                "salaryMax": job["salaryMax"],
                "salaryMonths": job["salaryMonths"],
                "education": job["education"],
                "techDirection": job["techDirection"],
                "tagNames": [catalog["tagNames"].get(tag, "") for tag in job["tags"] if catalog["tagNames"].get(tag)],
                "similarity": similarity,
                "reason": reason,
            }
        )
    return {"jobId": int(job_id), "items": items}


def latest_evaluation() -> dict:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT batch_no, algo, k, precision_at_k, recall_at_k, ndcg_at_k,
                       coverage, user_count, alpha, cf_method
                FROM spark_recommend_eval
                WHERE deleted = 0 AND is_latest = 1
                ORDER BY FIELD(algo, 'cf', 'content', 'hybrid', 'popular'), k
                """
            )
            metric_rows = cur.fetchall()
            cur.execute(
                """
                SELECT batch_no, params_json
                FROM spark_task_log
                WHERE deleted = 0 AND task_code = 'recommend' AND status = 1
                ORDER BY id DESC
                LIMIT 1
                """
            )
            task = cur.fetchone()
    finally:
        conn.close()
    params = {}
    if task and task.get("params_json"):
        import json

        raw = task["params_json"]
        if isinstance(raw, str):
            try:
                params = json.loads(raw)
            except json.JSONDecodeError:
                params = {}
        elif isinstance(raw, dict):
            params = raw
    metrics = []
    batch_no = None
    cf_method = params.get("cfMethod")
    alpha = params.get("alpha")
    for row in metric_rows:
        batch_no = row["batch_no"]
        cf_method = row["cf_method"] or cf_method
        if row["algo"] == "hybrid" and row["alpha"] is not None:
            alpha = float(row["alpha"])
        metrics.append(
            {
                "algo": row["algo"],
                "k": int(row["k"]),
                "precisionAtK": float(row["precision_at_k"]),
                "recallAtK": float(row["recall_at_k"]),
                "ndcgAtK": float(row["ndcg_at_k"]),
                "coverage": float(row["coverage"]),
                "userCount": int(row["user_count"]),
            }
        )
    return {
        "batchNo": batch_no or params.get("batchNo"),
        "cfMethod": cf_method,
        "alpha": None if alpha is None else float(alpha),
        "fusion": params.get("fusion"),
        "adaptiveAlpha": params.get("adaptiveAlpha"),
        "halfLifeDays": params.get("halfLifeDays") or HALF_LIFE_DAYS,
        "summary": params.get("cfChoiceReason"),
        "cosineNdcg10": params.get("cosineNdcg10"),
        "alsNdcg10": params.get("alsNdcg10"),
        "metrics": metrics,
    }


def skill_radar(user_id: int) -> dict:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.direction AS direction, AVG(s.proficiency) AS proficiency
                FROM stu_skill s
                INNER JOIN skill_tag t ON t.id = s.tag_id AND t.deleted = 0
                WHERE s.user_id = %s AND s.deleted = 0
                GROUP BY t.direction
                ORDER BY proficiency DESC, t.direction
                """,
                (int(user_id),),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    dimensions = []
    for row in rows:
        score = round(float(row["proficiency"]) / 5.0 * 100.0, 1)
        dimensions.append({"name": row["direction"], "score": score, "max": 100})
    return {"studentId": int(user_id), "dimensions": dimensions}


def _empty(user_id: int, model) -> dict:
    return {
        "userId": int(user_id),
        "source": "realtime",
        "strategy": "hybrid" if model else "content_popular",
        "cfMethod": (model or {}).get("cfMethod") or "user_cosine",
        "coldStart": True,
        "halfLifeDays": HALF_LIFE_DAYS,
        "items": [],
    }


def _content_one(skills, major, direction, city, education, job, tag_names) -> float:
    percent, _names = skill_match_percent(skills, set(job["tags"]), tag_names)
    direction_match = 1.0 if direction and direction == job["techDirection"] else 0.0
    city_match = 1.0 if city and city == job["city"] else 0.0
    edu_ok = job["education"] == 0 or (education > 0 and job["education"] <= education)
    text = f"{job['title']} {job.get('requirement') or ''}"[:500]
    major_hit = 1.0 if len(major) >= 2 and major in text else 0.0
    score = 100.0 * (0.50 * (percent / 100.0) + 0.20 * direction_match + 0.16 * city_match + 0.08 * (1.0 if edu_ok else 0.0) + 0.06 * major_hit)
    if not edu_ok:
        score *= 0.35
    return float(max(0.0, min(100.0, score)))


def _cooccurrence(job_id: int) -> dict[int, float] | None:
    """看过/收藏/投递过该职位的学生，对其他职位的评分之和，按最大值归一。"""
    model = load_model()
    if not model:
        return None
    touched = [user for user, _value in model["byItem"].get(int(job_id), ())]
    if not touched:
        return None
    counts: dict[int, float] = defaultdict(float)
    for user in touched:
        for item, value in model["ratings"].get(user, {}).items():
            counts[item] += value
    peak = max(counts.values(), default=0.0)
    if peak <= 0:
        return None
    return {item: value / peak for item, value in counts.items()}


def _query_catalog() -> dict:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.title, p.tech_direction, p.city, p.province, p.education,
                       p.salary_min, p.salary_max, p.salary_months, IFNULL(p.requirement, '') AS requirement,
                       p.apply_count,
                       IF(c.short_name IS NOT NULL AND c.short_name <> '', c.short_name, c.company_name) AS company_name
                FROM job_position p
                INNER JOIN ent_company c ON c.id = p.company_id
                WHERE p.deleted = 0 AND p.shelf_status = 1 AND p.audit_status = 1
                  AND c.deleted = 0 AND c.audit_status = 1
                """
            )
            job_rows = cur.fetchall()
            cur.execute(
                """
                SELECT t.position_id, t.tag_id, s.name AS tag_name
                FROM job_position_tag t
                INNER JOIN skill_tag s ON s.id = t.tag_id AND s.deleted = 0
                WHERE t.deleted = 0
                """
            )
            tag_rows = cur.fetchall()
    finally:
        conn.close()
    tag_names = {}
    tags = defaultdict(list)
    for row in tag_rows:
        tag_id = int(row["tag_id"])
        tag_names[tag_id] = row["tag_name"]
        tags[int(row["position_id"])].append(tag_id)
    jobs = {}
    for row in job_rows:
        job_id = int(row["id"])
        jobs[job_id] = {
            "id": job_id,
            "title": row["title"],
            "companyName": row["company_name"],
            "city": row["city"] or "",
            "province": row["province"] or "",
            "education": int(row["education"] or 0),
            "salaryMin": int(row["salary_min"] or 0),
            "salaryMax": int(row["salary_max"] or 0),
            "salaryMonths": int(row["salary_months"] or 12),
            "requirement": row["requirement"] or "",
            "applyCount": int(row["apply_count"] or 0),
            "techDirection": row["tech_direction"] or "",
            "tags": tags.get(job_id, []),
        }
    return {"jobs": jobs, "tagNames": tag_names}


def _profile(user_id: int) -> dict | None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT major, education, expect_city, expect_direction
                FROM stu_profile
                WHERE user_id = %s AND deleted = 0
                LIMIT 1
                """,
                (int(user_id),),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "major": row["major"] or "",
        "education": int(row["education"] or 0),
        "expectCity": row["expect_city"] or "",
        "expectDirection": row["expect_direction"] or "",
    }


def _skills(user_id: int) -> dict[int, float]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tag_id, proficiency
                FROM stu_skill
                WHERE user_id = %s AND deleted = 0
                """,
                (int(user_id),),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return {int(row["tag_id"]): float(row["proficiency"]) for row in rows}


def _events(user_id: int) -> list[dict]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT target_id AS position_id, behavior_type, weight, UNIX_TIMESTAMP(create_time) AS ts
                FROM user_behavior_log
                WHERE user_id = %s AND deleted = 0 AND target_type = 1 AND behavior_type IN (1, 2, 3)
                """,
                (int(user_id),),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    events = []
    for row in rows:
        events.append(
            {
                "user_id": int(user_id),
                "position_id": int(row["position_id"]),
                "behavior_type": int(row["behavior_type"]),
                "weight": float(row["weight"] or 1),
                "ts": float(row["ts"] or 0),
            }
        )
    return events


def _applied(user_id: int) -> set[int]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT position_id
                FROM job_application
                WHERE user_id = %s AND deleted = 0
                """,
                (int(user_id),),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return {int(row["position_id"]) for row in rows}
