"""混合职位推荐离线任务（全部计算在 Spark DataFrame 上完成）。

协同过滤在留出集上比较两种实现，按 NDCG@10 择优后写入 spark_recommend：

1. 用户-用户余弦（recommend_cf.py）：隐式反馈先按浏览 1、收藏 3、投递 5 加权，再相对全体行为
   最大时间做 45 天半衰期衰减，同一学生对同一职位汇总后取 log1p，得到稀疏评分 DataFrame。
   评分表按职位自连接，一次聚合得到点积与共同交互数，相似度 = 余弦 × co/(co+15)，
   只保留正相关的前 40 个邻居（Window + row_number），邻居相似度 × 邻居评分 join 聚合得到预测。
   全量评分上的邻居表写入 spark_user_neighbor，供实时推荐直接复用。
2. Spark MLlib ALS（implicitPrefs）：同一份衰减评分。默认 rank=8、迭代 6 次仅作快速对照；
   消融实验在验证集上网格搜索 rank∈{8,32,64}×reg×alpha 后，调参 ALS 的 NDCG@10 可逼近
   用户余弦，但仍略低，且新学生没有因子。生产协同过滤因此选用用户余弦（可解释、冷启动友好）；
   ALS 保留在离线任务中作对照与论文消融。

内容匹配把技能熟练度与职位标签的余弦、期望方向（自由填写先归一，同方向 1、相近方向 0.5）、期望城市、学历是否达到要求、专业是否
出现在职位名称或任职要求里做加权，学历不够的职位再乘 0.35；与期望方向冲突的职位，内容分、协同分、
热度分统一乘 0.5（相近方向 0.9），避免「相似同学也看过」把跨方向岗位顶到前面。没有行为的学生用
0.75×内容 + 0.25×近期行为热度。以上都是 Spark 列表达式，在「学生 × 在架职位」候选集上计算。

融合权重、是否按活跃度缩放、线性或门控（2×2×10=40 组）与候选集 crossJoin 后一次性在 Spark
里排序、计算 NDCG@10，按原规则择优。评估同时给出协同过滤、内容、融合和热门基线在 K=5/10/20 的
Precision、Recall、NDCG 与目录覆盖率。生产列表只排除已投递职位；评估时排除训练期交互。

Driver 只收集：标量（最大时间戳、职位数）、40×3 行评估指标、最终 Top-K 推荐行（写库）、
以及供实时服务使用的稀疏评分导出。原 numpy 实现见 experiments/recommend/numpy_reference.py。
"""

from __future__ import annotations

import json
import logging
import pickle
import time

from pyspark.ml.recommendation import ALS
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from app.spark import recommend_cf as CF
from app.spark.db import publish, write_dataframe
from app.spark.paths import RECOMMEND_DIR, RECOMMEND_EVAL_PATH, RECOMMEND_MODEL_PATH
from app.spark.recommend_eval import (
    ALPHAS,
    EVAL_KS,
    HALF_LIFE_DAYS,
    NEIGHBORS,
    SHRINK,
    TOP_N,
    build_reason,
    clip_score,
    holdout_count,
    ndcg_at,
)
from app.spark.session import get_spark, read_query

logger = logging.getLogger(__name__)

ALS_RANK = 8
ALS_ITER = 6
ALS_REG = 0.08
ALS_ALPHA = 20.0
# 学历不达标职位的内容分乘子（消融实验可传 1.0 关闭）
EDU_PENALTY = CF.EDU_PENALTY
NEIGHBOR_TABLE = "spark_user_neighbor"
SHUFFLE_PARTS = 8


def run_recommend(batch_no: str) -> dict:
    started = time.perf_counter()
    stages: dict[str, float] = {}
    spark = get_spark()
    cached: list[DataFrame] = []

    def keep(frame: DataFrame) -> DataFrame:
        frame = frame.cache()
        cached.append(frame)
        return frame

    try:
        return _run(spark, batch_no, started, stages, keep)
    finally:
        for frame in cached:
            try:
                frame.unpersist()
            except Exception:  # pragma: no cover
                pass


def _run(spark, batch_no, started, stages, keep) -> dict:
    load_started = time.perf_counter()
    frames = {name: keep(frame) for name, frame in _load(spark).items()}
    jobs = frames["jobs"]
    profiles = frames["profiles"]
    n_profiles = profiles.count()
    n_jobs = jobs.count()
    if n_profiles == 0:
        raise RuntimeError("没有可推荐的学生档案")
    if n_jobs == 0:
        raise RuntimeError("没有可推荐的职位")
    eligible = keep(jobs.where(F.col("eligible")).select("position_id"))
    catalog_size = eligible.count()
    if catalog_size == 0:
        raise RuntimeError("没有可推荐的在架职位")

    events = keep(frames["events"].join(jobs.select("position_id"), "position_id", "left_semi"))
    input_count = frames["events"].count()
    ref_row = events.agg(F.max(F.coalesce(F.col("ts").cast("double"), F.lit(0.0))).alias("ref")).first()
    ref_ts = float(ref_row["ref"]) if ref_row and ref_row["ref"] is not None else 0.0

    users_dim = keep(_users_dim(profiles, events))
    items_dim = keep(_items_dim(jobs))
    user_tags = keep(CF.user_tag_vectors(frames["skills"]))
    stages["load"] = round(time.perf_counter() - load_started, 3)

    # ------------------------------------------------------------ 留出评估
    cf_started = time.perf_counter()
    held = keep(CF.split_holdout(events))
    train_events = events.join(held, ["user_id", "position_id"], "left_anti")
    train_ratings, train_pop_raw = CF.implicit_ratings(train_events, ref_ts)
    train_ratings = keep(train_ratings)
    truth = keep(held.join(eligible, "position_id", "left_semi"))
    truth_users = truth.select("user_id").distinct()
    holdout_users = truth_users.count()

    eval_cands = _candidates(truth_users, eligible, train_ratings.where(F.col("rating") > 0).select("user_id", "position_id"))
    tag_cos = CF.tag_cosine(user_tags, frames["job_tags"])
    eval_base = _enrich(eval_cands, users_dim, items_dim, tag_cos, CF.popularity_scores(train_pop_raw), CF.activity(train_ratings))
    # 按学生哈希分区后缓存：之后按学生（以及 cfg×学生）开窗、min-max 都不必再 shuffle
    eval_base = keep(eval_base.repartition(SHUFFLE_PARTS, "user_id"))
    eval_base.count()

    neighbors_eval = CF.user_cosine_neighbors(train_ratings, SHRINK, NEIGHBORS)
    cosine_pred = CF.cosine_predictions(train_ratings, neighbors_eval)
    cosine_frame = keep(CF.with_cf_minmax(_attach_cf(eval_base, cosine_pred).repartition(SHUFFLE_PARTS, "user_id")))
    cosine_rows = _metrics(spark, cosine_frame, "cf_raw", truth, catalog_size)
    stages["cosine"] = round(time.perf_counter() - cf_started, 3)

    als_started = time.perf_counter()
    als_pred = _als_predict(train_ratings, eval_base.select("user_id", "position_id"))
    als_frame = None
    als_rows = None
    if als_pred is not None:
        als_frame = keep(CF.with_cf_minmax(_attach_cf(eval_base, als_pred).repartition(SHUFFLE_PARTS, "user_id")))
        als_rows = _metrics(spark, als_frame, "cf_raw", truth, catalog_size)
    stages["als"] = round(time.perf_counter() - als_started, 3)

    eval_started = time.perf_counter()
    cosine_ndcg = ndcg_at(cosine_rows, 10)
    als_ndcg = ndcg_at(als_rows, 10) if als_rows else -1.0
    cf_method, cf_reason = _choose_cf(cosine_ndcg, als_ndcg, als_rows is not None)
    cf_frame = als_frame if cf_method == "als" else cosine_frame
    cf_rows = als_rows if cf_method == "als" else cosine_rows

    grid_rows = _grid_metrics(spark, cf_frame, truth, catalog_size)
    best = _select_best(grid_rows)
    hybrid_rows = [_strip(row) for row in grid_rows if row["cfg_id"] == best["cfg_id"]]
    content_rows = _metrics(spark, eval_base, "content", truth, catalog_size)
    popular_rows = _metrics(spark, eval_base, "popularity", truth, catalog_size)
    stages["eval"] = round(time.perf_counter() - eval_started, 3)

    # ------------------------------------------------------------ 全量生产打分
    prod_started = time.perf_counter()
    full_ratings, full_pop_raw = CF.implicit_ratings(events, ref_ts)
    full_ratings = keep(full_ratings)
    full_pop = keep(CF.popularity_scores(full_pop_raw))
    neighbors_full = keep(CF.user_cosine_neighbors(full_ratings, SHRINK, NEIGHBORS))
    neighbor_count = neighbors_full.count()
    if cf_method == "als":
        full_pred = _als_predict(full_ratings, None, users=profiles.select("user_id").distinct(), items=eligible)
        if full_pred is None:
            cf_method = "user_cosine"
            cf_reason += "；全量 ALS 失败，生产结果改用用户余弦"
    if cf_method != "als":
        full_pred = CF.cosine_predictions(full_ratings, neighbors_full)

    prod_users = profiles.select("user_id").distinct()
    applied = frames["applications"].select("user_id", "position_id").distinct()
    prod_cands = _candidates(prod_users, eligible, applied)
    prod_base = _enrich(prod_cands, users_dim, items_dim, tag_cos, full_pop, CF.activity(full_ratings))
    prod = CF.with_cf_minmax(_attach_cf(prod_base, full_pred).repartition(SHUFFLE_PARTS, "user_id"))
    prod = keep(prod.withColumn("hybrid", CF.fused_expr(best["alpha"], best["fusion"], best["adaptive"])))
    profile_user_count = prod.select("user_id").distinct().count()
    top_rows = _top_rows(prod, user_tags, frames["job_tags"], frames["tag_names"])
    recommend_rows = _recommend_rows(batch_no, top_rows)
    eval_rows = _eval_rows(batch_no, cf_method, best, cf_rows, content_rows, hybrid_rows, popular_rows)
    stages["score"] = round(time.perf_counter() - prod_started, 3)

    write_started = time.perf_counter()
    write_dataframe(
        neighbors_full.select(
            F.lit(batch_no).alias("batch_no"),
            "user_id",
            "neighbor_id",
            F.col("similarity").cast("double").alias("similarity"),
            F.col("cosine").cast("double").alias("cosine"),
            F.col("co_count").cast("int").alias("co_count"),
            F.col("rank_no").cast("int").alias("rank_no"),
            F.lit(0).alias("is_latest"),
            F.lit(0).alias("deleted"),
        ),
        NEIGHBOR_TABLE,
    )
    publish(
        batch_no,
        [
            (
                "spark_recommend",
                ["batch_no", "user_id", "position_id", "algo", "match_score", "cf_score", "content_score", "rank_no", "reason", "is_latest", "deleted"],
                recommend_rows,
            ),
            (
                "spark_recommend_eval",
                ["batch_no", "algo", "k", "precision_at_k", "recall_at_k", "ndcg_at_k", "coverage", "user_count", "alpha", "cf_method", "is_latest", "deleted"],
                eval_rows,
            ),
        ],
        activate_tables=[NEIGHBOR_TABLE],
    )
    model_ratings = _sparse_ratings(full_ratings)
    model_pop = {int(row["position_id"]): float(row["popularity"]) for row in full_pop.toLocalIterator()}
    payload = _payload(
        batch_no, cf_method, cf_reason, best, cosine_ndcg, als_ndcg if als_rows is not None else None,
        cf_rows, content_rows, hybrid_rows, popular_rows, profile_user_count, catalog_size, holdout_users, stages,
    )
    payload["engine"] = "spark"
    payload["cfImpl"] = "Spark DataFrame：评分按职位自连接求点积与共现数，Window 取前 40 邻居"
    payload["neighborRows"] = int(neighbor_count)
    _save_model(
        {
            "version": 2,
            "batchNo": batch_no,
            "cfMethod": cf_method,
            "alpha": best["alpha"],
            "fusion": best["fusion"],
            "adaptiveAlpha": best["adaptive"],
            "halfLifeDays": HALF_LIFE_DAYS,
            "shrink": SHRINK,
            "neighbors": NEIGHBORS,
            "refTs": ref_ts,
            "ratings": model_ratings,
            "popularity": model_pop,
        }
    )
    try:
        from app.spark.recommend_online import invalidate_caches

        invalidate_caches()
    except Exception:
        logger.exception("清理推荐缓存失败")
    stages["write"] = round(time.perf_counter() - write_started, 3)
    payload["stageSeconds"] = stages
    _save_eval_json(payload)
    elapsed = round(time.perf_counter() - started, 3)
    hybrid_ndcg = ndcg_at(hybrid_rows, 10)
    logger.info(
        "推荐完成 method=%s alpha=%s fusion=%s adaptive=%s NDCG@10=%.4f 耗时 %ss",
        cf_method, best["alpha"], best["fusion"], best["adaptive"], hybrid_ndcg, elapsed,
    )
    return {
        "inputCount": int(input_count),
        "outputCount": int(len(recommend_rows)),
        "resultMsg": _result_msg(cf_method, best, hybrid_ndcg, profile_user_count, cf_reason),
        "params": payload,
    }


# --------------------------------------------------------------------------- 读取


def _load(spark) -> dict[str, DataFrame]:
    events = _sql(
        spark,
        """
        SELECT user_id, behavior_type, target_id AS position_id, weight,
               UNIX_TIMESTAMP(create_time) AS ts
        FROM user_behavior_log
        WHERE deleted = 0 AND target_type = 1 AND behavior_type IN (1, 2, 3)
        """,
    ).select(
        F.col("user_id").cast("long").alias("user_id"),
        F.coalesce(F.col("behavior_type").cast("int"), F.lit(1)).alias("behavior_type"),
        F.col("position_id").cast("long").alias("position_id"),
        F.col("weight").cast("double").alias("weight"),
        F.coalesce(F.col("ts").cast("double"), F.lit(0.0)).alias("ts"),
    )
    jobs = _sql(
        spark,
        """
        SELECT p.id AS position_id, p.title, p.tech_direction, p.city, p.province,
               p.education, IFNULL(p.requirement, '') AS requirement, p.shelf_status, p.audit_status,
               c.audit_status AS company_audit, c.deleted AS company_deleted
        FROM job_position p
        INNER JOIN ent_company c ON c.id = p.company_id
        WHERE p.deleted = 0
        """,
    )
    num = lambda name: F.coalesce(F.col(name).cast("int"), F.lit(0))  # noqa: E731
    txt = lambda name: F.coalesce(F.col(name).cast("string"), F.lit(""))  # noqa: E731
    jobs = jobs.select(
        F.col("position_id").cast("long").alias("position_id"),
        txt("title").alias("title"),
        txt("tech_direction").alias("tech_direction"),
        txt("city").alias("city"),
        num("education").alias("education"),
        txt("requirement").alias("requirement"),
        ((num("shelf_status") == 1) & (num("audit_status") == 1) & (num("company_audit") == 1) & (num("company_deleted") == 0)).alias("eligible"),
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
    ).select(
        F.col("user_id").cast("long").alias("user_id"),
        txt("major").alias("major"),
        F.coalesce(F.col("education").cast("int"), F.lit(2)).alias("education"),
        txt("expect_city").alias("expect_city"),
        txt("expect_direction").alias("expect_direction"),
    )
    skills = _sql(
        spark,
        """
        SELECT s.user_id, s.tag_id, s.proficiency
        FROM stu_skill s
        INNER JOIN skill_tag t ON t.id = s.tag_id AND t.deleted = 0
        WHERE s.deleted = 0
        """,
    ).select(
        F.col("user_id").cast("long").alias("user_id"),
        F.coalesce(F.col("tag_id").cast("long"), F.lit(0)).alias("tag_id"),
        F.coalesce(F.col("proficiency").cast("double"), F.lit(1.0)).alias("proficiency"),
    )
    job_tags = _sql(spark, "SELECT position_id, tag_id FROM job_position_tag WHERE deleted = 0").select(
        F.col("position_id").cast("long").alias("position_id"),
        F.coalesce(F.col("tag_id").cast("long"), F.lit(0)).alias("tag_id"),
    )
    applications = _sql(spark, "SELECT user_id, position_id FROM job_application WHERE deleted = 0").select(
        F.col("user_id").cast("long").alias("user_id"),
        F.col("position_id").cast("long").alias("position_id"),
    )
    tag_names = _sql(spark, "SELECT id AS tag_id, name AS tag_name FROM skill_tag WHERE deleted = 0").select(
        F.col("tag_id").cast("long").alias("tag_id"),
        txt("tag_name").alias("tag_name"),
    )
    return {
        "events": events,
        "jobs": jobs,
        "profiles": profiles,
        "skills": skills,
        "job_tags": job_tags,
        "applications": applications,
        "tag_names": tag_names,
    }


def _sql(spark, sql: str) -> DataFrame:
    frame = read_query(spark, sql)
    return frame.toDF(*[str(column).lower() for column in frame.columns])


def _users_dim(profiles: DataFrame, events: DataFrame) -> DataFrame:
    """学生全集 = 有档案的学生 ∪ 有行为的学生；无档案者学历按 2（本科）处理。"""
    profile_one = profiles.dropDuplicates(["user_id"])
    users = profiles.select("user_id").union(events.select("user_id")).distinct()
    return users.join(profile_one, "user_id", "left").select(
        "user_id",
        F.coalesce("education", F.lit(2)).alias("u_edu"),
        F.coalesce("expect_direction", F.lit("")).alias("u_dir"),
        F.coalesce("expect_city", F.lit("")).alias("u_city"),
        F.coalesce("major", F.lit("")).alias("u_major"),
    )


def _items_dim(jobs: DataFrame) -> DataFrame:
    # item_idx 是按 position_id 升序的下标，用于和原实现一致的同分打破规则；职位表只有几千行
    order = Window.orderBy("position_id")
    return jobs.select(
        "position_id",
        (F.row_number().over(order) - 1).alias("item_idx"),
        F.col("education").alias("j_edu"),
        F.col("tech_direction").alias("j_dir"),
        F.col("city").alias("j_city"),
        F.concat_ws(" ", F.col("title"), F.substring(F.col("requirement"), 1, 500)).alias("j_text"),
    )


# --------------------------------------------------------------------------- 候选集与打分


def _candidates(users: DataFrame, eligible: DataFrame, banned: DataFrame) -> DataFrame:
    return users.crossJoin(eligible).join(banned, ["user_id", "position_id"], "left_anti")


def _enrich(cands, users_dim, items_dim, tag_cos, popularity, activity) -> DataFrame:
    frame = (
        cands.join(F.broadcast(items_dim), "position_id")
        .join(users_dim, "user_id")
        .join(F.broadcast(popularity), "position_id", "left")
        .join(activity, "user_id", "left")
        .fillna({"popularity": 0.0, "activity": 0.0})
    )
    return CF.with_content(frame, tag_cos, EDU_PENALTY)


def _attach_cf(base: DataFrame, pred: DataFrame) -> DataFrame:
    return base.join(pred.select("user_id", "position_id", "cf_raw"), ["user_id", "position_id"], "left").fillna({"cf_raw": 0.0})


def _metrics(spark, frame: DataFrame, score_col: str, truth: DataFrame, catalog_size: int) -> list[dict]:
    ranked = CF.top_k(frame, score_col, max(EVAL_KS), ["user_id"]).select("user_id", "position_id", "rank_no")
    return CF.evaluate(spark, ranked, truth, EVAL_KS, catalog_size, [])


def _grid_metrics(spark, cf_frame: DataFrame, truth: DataFrame, catalog_size: int) -> list[dict]:
    params = []
    cfg_id = 0
    for fusion in ("linear", "gated"):
        for adaptive in (False, True):
            for alpha in ALPHAS:
                params.append((cfg_id, fusion, adaptive, float(alpha)))
                cfg_id += 1
    grid = spark.createDataFrame(params, ["cfg_id", "fusion", "adaptive", "alpha"])
    scored = cf_frame.select("user_id", "position_id", "item_idx", "cf_mm", "cf_hi", "content", "popularity", "activity", "dir_factor").crossJoin(F.broadcast(grid))
    scored = scored.withColumn("hybrid", CF.fused_expr(F.col("alpha"), F.col("fusion"), F.col("adaptive")))
    ranked = CF.top_k(scored, "hybrid", max(EVAL_KS), ["cfg_id", "user_id"]).select("cfg_id", "user_id", "position_id", "rank_no")
    rows = CF.evaluate(spark, ranked, truth, EVAL_KS, catalog_size, ["cfg_id"])
    lookup = {item[0]: item for item in params}
    for row in rows:
        _, fusion, adaptive, alpha = lookup[int(row["cfg_id"])]
        row.update({"fusion": fusion, "adaptive": adaptive, "alpha": alpha})
    return rows


def _select_best(grid_rows: list[dict]) -> dict:
    """与原 _tune_hybrid 相同的遍历顺序与并列规则。"""
    ndcg10 = {int(row["cfg_id"]): row for row in grid_rows if int(row["k"]) == 10}
    best = {"alpha": 0.45, "fusion": "linear", "adaptive": True, "ndcg": -1.0, "cfg_id": -1}
    for cfg_id in sorted(ndcg10):
        row = ndcg10[cfg_id]
        alpha, score = float(row["alpha"]), float(row["ndcg"])
        cand = {"alpha": alpha, "fusion": row["fusion"], "adaptive": bool(row["adaptive"]), "ndcg": score, "cfg_id": cfg_id}
        if score > best["ndcg"] + 1e-9:
            best = cand
        elif abs(score - best["ndcg"]) <= 1e-9:
            if 0.15 <= alpha <= 0.85 and not (0.15 <= best["alpha"] <= 0.85):
                best = cand
    return best


def _strip(row: dict) -> dict:
    return {key: row[key] for key in ("k", "precision", "recall", "ndcg", "coverage", "userCount")}


def _choose_cf(cosine_ndcg: float, als_ndcg: float, has_als: bool) -> tuple[str, str]:
    if has_als and als_ndcg > cosine_ndcg + 1e-6:
        return "als", f"留出集 NDCG@10：ALS {als_ndcg:.4f} 高于用户余弦 {cosine_ndcg:.4f}，离线协同过滤采用隐式 ALS"
    if not has_als:
        return "user_cosine", f"ALS 未产出可用结果，采用用户余弦（NDCG@10 {cosine_ndcg:.4f}）"
    if abs(als_ndcg - cosine_ndcg) <= 0.005:
        return "user_cosine", (
            f"留出集 NDCG@10：用户余弦 {cosine_ndcg:.4f}，ALS {als_ndcg:.4f}，"
            "差距不超过 0.005，采用可解释、便于实时复用的用户余弦"
        )
    return "user_cosine", (
        f"留出集 NDCG@10：用户余弦 {cosine_ndcg:.4f} 高于 ALS {als_ndcg:.4f}，"
        "采用用户余弦。学生约 200 人且行为按方向和城市聚集，邻居平均比低秩因子更稳"
    )


def _als_predict(ratings: DataFrame, pairs: DataFrame | None, users: DataFrame | None = None, items: DataFrame | None = None):
    """隐式 ALS，返回 [user_id, position_id, cf_raw]；没有因子的学生/职位记 0（与原实现一致）。"""
    train = ratings.where(F.col("rating") > 0).select(
        F.col("user_id").cast("int").alias("user_id"),
        F.col("position_id").cast("int").alias("position_id"),
        F.col("rating").cast("float").alias("rating"),
    )
    if train.count() < 20:
        logger.warning("评分过少，跳过 ALS")
        return None
    if pairs is None:
        pairs = users.crossJoin(items)
    try:
        model = ALS(
            userCol="user_id", itemCol="position_id", ratingCol="rating", implicitPrefs=True,
            rank=ALS_RANK, maxIter=ALS_ITER, regParam=ALS_REG, alpha=ALS_ALPHA,
            coldStartStrategy="nan", nonnegative=False, seed=42, checkpointInterval=20,
        ).fit(train)
        scored = model.transform(
            pairs.select(F.col("user_id").cast("int").alias("user_id"), F.col("position_id").cast("int").alias("position_id"))
        )
        prediction = F.col("prediction").cast("double")
        return scored.select(
            F.col("user_id").cast("long").alias("user_id"),
            F.col("position_id").cast("long").alias("position_id"),
            F.when(prediction.isNull() | F.isnan(prediction), F.lit(0.0)).otherwise(prediction).alias("cf_raw"),
        )
    except Exception:
        logger.exception("ALS 训练失败，回退用户余弦")
        return None


# --------------------------------------------------------------------------- 结果行


def _top_rows(prod: DataFrame, user_tags, job_tags, tag_names) -> list:
    """三种算法各取 Top-N（Spark Window），附上技能重合后收集到 Driver（每人至多 3×20 行）。"""
    cols = ["user_id", "position_id", "cf_mm", "content", "hybrid", "popularity", "dir_rel", "j_dir", "city_match", "major_hit", "u_dir", "u_city", "u_major"]
    parts = []
    for algo, score_col in ((1, "cf_mm"), (2, "content"), (3, "hybrid")):
        ranked = CF.top_k(prod, score_col, TOP_N, ["user_id"])
        parts.append(ranked.select(*cols, "rank_no", F.lit(algo).alias("algo"), F.col(score_col).alias("match")))
    top = parts[0].unionByName(parts[1]).unionByName(parts[2])
    overlap = CF.skill_overlap(top, user_tags, job_tags, tag_names)
    top = top.join(overlap, ["user_id", "position_id"], "left")
    return top.orderBy("algo", "user_id", "rank_no").collect()


def _recommend_rows(batch_no: str, top_rows: list) -> list[tuple]:
    rows = []
    for row in top_rows:
        reason = build_reason(
            hit_skills=list(row["skill_names"] or []),
            missing_skills=list(row["missing_names"] or []),
            hit_count=int(row["hit_count"] or 0),
            job_tag_count=int(row["job_tag_count"] or 0),
            relation=row["dir_rel"] or "none",
            user_direction=row["u_dir"] or "",
            job_direction=row["j_dir"] or "",
            city=row["u_city"] or "",
            city_match=bool(row["city_match"]),
            major=row["u_major"] or "",
            major_match=bool(row["major_hit"]),
            cf_score=float(row["cf_mm"]),
            popular=float(row["popularity"]) >= 70,
            variant=int(row["rank_no"]) + int(row["user_id"]),
        )
        rows.append(
            (
                batch_no,
                int(row["user_id"]),
                int(row["position_id"]),
                int(row["algo"]),
                clip_score(row["match"]),
                clip_score(row["cf_mm"]),
                clip_score(row["content"]),
                int(row["rank_no"]),
                reason,
                1,
                0,
            )
        )
    if not rows:
        raise RuntimeError("没有生成推荐结果")
    return rows


def _sparse_ratings(ratings: DataFrame) -> dict[int, dict[int, float]]:
    """供实时服务的稀疏评分导出（非零项，约等于行为对数），不是稠密矩阵。"""
    mapping: dict[int, dict[int, float]] = {}
    for row in ratings.where(F.col("rating") > 0).select("user_id", "position_id", "rating").toLocalIterator():
        mapping.setdefault(int(row["user_id"]), {})[int(row["position_id"])] = float(row["rating"])
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
    grouped = {"cf": cf_rows, "content": content_rows, "hybrid": hybrid_rows, "popular": popular_rows}
    rows = []
    for algo, metrics in grouped.items():
        for item in metrics or []:
            alpha = round(float(best["alpha"]), 4) if algo == "hybrid" else None
            rows.append(
                (
                    batch_no, algo, int(item["k"]),
                    round(float(item["precision"]), 4), round(float(item["recall"]), 4),
                    round(float(item["ndcg"]), 4), round(float(item["coverage"]), 4),
                    int(item["userCount"]), alpha, cf_method, 1, 0,
                )
            )
    if not rows:
        raise RuntimeError("没有生成评估指标")
    return rows


def _payload(batch_no, cf_method, cf_reason, best, cosine_ndcg, als_ndcg, cf_rows, content_rows, hybrid_rows, popular_rows, user_count, catalog_size, holdout_users, stages):
    metrics = []
    for algo, rows in (("cf", cf_rows), ("content", content_rows), ("hybrid", hybrid_rows), ("popular", popular_rows)):
        for item in _round_metric(rows):
            metrics.append({"algo": algo, **item})
    return {
        "batchNo": batch_no,
        "halfLifeDays": HALF_LIFE_DAYS,
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
        f"Spark 为 {user_count} 名学生各生成协同过滤、内容、融合 Top{TOP_N}；"
        f"协同过滤选用{method}，融合为{fusion} alpha={best['alpha']}（{adaptive}），"
        f"融合 NDCG@10={hybrid_ndcg:.4f}。{cf_reason}"
    )
    if len(text) > 500:
        return text[:497] + "..."
    return text


def _save_model(payload: dict) -> None:
    RECOMMEND_DIR.mkdir(parents=True, exist_ok=True)
    tmp = RECOMMEND_MODEL_PATH.with_suffix(".tmp")
    with tmp.open("wb") as handle:
        pickle.dump(payload, handle, protocol=4)
    tmp.replace(RECOMMEND_MODEL_PATH)


def _save_eval_json(payload: dict) -> None:
    RECOMMEND_DIR.mkdir(parents=True, exist_ok=True)
    RECOMMEND_EVAL_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = ["run_recommend", "holdout_count"]
