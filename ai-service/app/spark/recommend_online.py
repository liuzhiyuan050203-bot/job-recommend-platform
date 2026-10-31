"""单用户实时推荐与相似职位。

离线批次把全体学生的衰减评分矩阵存成 pickle。实时侧不再启动 Spark：
已有学生或新学生都用这份矩阵做用户余弦，内容分按当前档案和技能现算。
没有行为时退化为内容分与热门分。相似职位按标签 Jaccard、方向和城市，
有模型时再加一点共现。
"""

from __future__ import annotations

import logging
import pickle
import threading
import time
from collections import defaultdict

import numpy as np
import pandas as pd

from app.spark.db import connect
from app.spark.paths import RECOMMEND_MODEL_PATH
from app.spark.recommend_eval import (
    HALF_LIFE_DAYS,
    aggregate_frame,
    build_reason,
    clip_score,
    cosine_one,
    fuse_scores,
    minmax_rows,
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
    n_items = len(item_ids)
    content = np.zeros(n_items, dtype=np.float64)
    major = str((profile or {}).get("major") or "")
    direction = str((profile or {}).get("expectDirection") or "")
    city = str((profile or {}).get("expectCity") or "")
    education = int((profile or {}).get("education") or 0)
    for index, job in enumerate(jobs):
        content[index] = _content_one(skills, major, direction, city, education, job, catalog["tagNames"])

    cf = np.zeros(n_items, dtype=np.float64)
    activity = 0.0
    ref_ts = float(model["refTs"]) if model and model.get("refTs") is not None else 0.0
    if events:
        ref_ts = max(ref_ts, max(float(row["ts"]) for row in events))
    ratings = {}
    if events:
        frame = pd.DataFrame(events)
        grouped, _pop = aggregate_frame(frame, ref_ts or float(frame["ts"].max()))
        activity = float(len(grouped))
        ratings = {int(pid): float(val) for pid, val in zip(grouped["position_id"], grouped["rating"])}
    if model and ratings:
        model_items = [int(item) for item in model["itemIds"]]
        model_index = {item: index for index, item in enumerate(model_items)}
        user_vec = np.zeros(len(model_items), dtype=np.float64)
        for position_id, rating in ratings.items():
            col = model_index.get(int(position_id))
            if col is not None:
                user_vec[col] = rating
        matrix = np.asarray(model["ratings"], dtype=np.float64)
        self_index = None
        model_users = [int(item) for item in model["userIds"]]
        if int(user_id) in model_users:
            self_index = model_users.index(int(user_id))
        raw = cosine_one(user_vec, matrix, self_index=self_index)
        for index, position_id in enumerate(item_ids):
            col = model_index.get(int(position_id))
            if col is not None:
                cf[index] = float(raw[col])

    popularity = np.zeros(n_items, dtype=np.float64)
    if model and model.get("popularity") is not None:
        model_items = [int(item) for item in model["itemIds"]]
        model_index = {item: index for index, item in enumerate(model_items)}
        pop_vector = np.asarray(model["popularity"], dtype=np.float64)
        for index, position_id in enumerate(item_ids):
            col = model_index.get(int(position_id))
            if col is not None:
                popularity[index] = float(pop_vector[col])
    if float(popularity.max()) <= 0:
        apply_counts = np.array([job["applyCount"] for job in jobs], dtype=np.float64)
        peak = float(apply_counts.max()) if n_items else 0.0
        popularity = np.zeros(n_items) if peak <= 0 else 100.0 * np.log1p(apply_counts) / np.log1p(peak)

    banned = np.zeros((1, n_items), dtype=bool)
    for index, position_id in enumerate(item_ids):
        if position_id in applied:
            banned[0, index] = True
    cf_mm = minmax_rows(cf.reshape(1, -1), banned)[0]
    alpha = float(model["alpha"]) if model and model.get("alpha") is not None else 0.45
    fusion = model.get("fusion") if model else "gated"
    adaptive = bool(model.get("adaptiveAlpha")) if model else True
    if fusion not in ("linear", "gated"):
        fusion = "gated"
    hybrid = fuse_scores(
        cf_mm.reshape(1, -1),
        content.reshape(1, -1),
        popularity.reshape(1, -1),
        np.array([activity], dtype=np.float64),
        alpha,
        fusion,
        adaptive,
    )[0]
    hybrid = hybrid.copy()
    hybrid[banned[0]] = -1.0
    order = np.argsort(-hybrid)
    items = []
    cold = activity <= 0 or cf_mm.size == 0 or float(np.max(cf_mm)) <= 0
    for position_index in order:
        if hybrid[position_index] < 0:
            continue
        if len(items) >= top_k:
            break
        job = jobs[int(position_index)]
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
    model = load_model()
    if not model or model.get("ratings") is None:
        return None
    item_ids = [int(item) for item in model["itemIds"]]
    if job_id not in item_ids:
        return None
    matrix = np.asarray(model["ratings"], dtype=np.float64)
    column = matrix[:, item_ids.index(job_id)]
    touched = (column > 0).astype(np.float64)
    if float(touched.sum()) <= 0:
        return None
    counts = matrix.T @ touched
    peak = float(counts.max()) if len(counts) else 0.0
    if peak <= 0:
        return None
    return {item_ids[index]: float(counts[index] / peak) for index in range(len(item_ids))}


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
