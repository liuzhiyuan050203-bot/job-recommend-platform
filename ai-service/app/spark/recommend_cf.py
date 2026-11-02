"""混合推荐在 Spark 上的核心计算（DataFrame 实现，生产离线任务使用）。

所有矩阵级运算都以稀疏三元组 DataFrame 表示，不在 Driver 上物化用户×职位矩阵：

* 隐式评分：浏览 1、收藏 3、投递 5（或行为表 weight），相对全体行为最大时间做 45 天半衰期
  衰减，按 (学生, 职位) 求和后 log1p。
* 用户-用户余弦：评分表按职位自连接（只保留 u < v 的一半再镜像），一次聚合同时得到
  点积 Σ r_ui·r_vi 与共同交互数 co；sim = dot / (‖u‖·‖v‖) × co / (co + SHRINK)。
  选它而不是 RowMatrix.columnSimilarities：后者（DIMSUM）只给余弦，收缩还要另算一遍
  二值矩阵的共现；自连接一次 shuffle 就拿到两者，结果精确，代价是 Σ_i m_i²（m_i 为职位 i
  的交互人数），对校园场景（职位热度长尾、每个职位几十人以内）是线性可扩展的。
* Top-N 正相关邻居：Window(partition by user, order by sim desc) + row_number。
* 预测：邻居相似度 × 邻居评分按 (学生, 职位) 聚合，除以邻居相似度之和。
* 候选集：学生 × 在架职位，减去屏蔽对（评估时为训练期交互，生产时为已投递）。
* 内容分、协同分逐行 min-max、线性/门控融合、学历惩罚、冷启动兜底全部是列表达式。
* 排序：score - item_idx×1e-9 降序 row_number，与原 numpy 实现的同分规则一致。
* 评估：Precision/Recall/NDCG@K 与覆盖率用 DataFrame 聚合，只把指标行收回 Driver。

只有最终 Top-K 结果、评估指标行和供实时服务使用的稀疏模型导出会收集到 Driver。
"""

from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from app.spark.recommend_eval import HALF_LIFE_DAYS, NEIGHBORS, SHRINK

EDU_PENALTY = 0.35
TIE_EPS = 1e-9


# --------------------------------------------------------------------------- 评分与热度


def implicit_ratings(events: DataFrame, ref_ts: float, half_life_days: float | None = HALF_LIFE_DAYS):
    """返回 (ratings[user_id, position_id, contrib, rating], item_pop[position_id, pop_raw])。"""
    behavior = F.coalesce(F.col("behavior_type").cast("int"), F.lit(1))
    fallback = F.when(behavior == 2, F.lit(3.0)).when(behavior == 3, F.lit(5.0)).otherwise(F.lit(1.0))
    raw_weight = F.col("weight").cast("double")
    weight = F.when(raw_weight.isNotNull() & ~F.isnan(raw_weight) & (raw_weight > 0), raw_weight).otherwise(fallback)
    ts = F.coalesce(F.col("ts").cast("double"), F.lit(0.0))
    age = F.greatest(F.lit(0.0), F.lit(float(ref_ts)) - ts)
    if half_life_days is None or half_life_days <= 0:
        contrib = weight
    else:
        contrib = weight * F.pow(F.lit(0.5), age / F.lit(float(half_life_days) * 86400.0))
    frame = events.select(
        F.col("user_id").cast("long").alias("user_id"),
        F.col("position_id").cast("long").alias("position_id"),
        contrib.alias("contrib"),
    )
    ratings = (
        frame.groupBy("user_id", "position_id")
        .agg(F.sum("contrib").alias("contrib"))
        .withColumn("rating", F.log1p("contrib"))
    )
    item_pop = frame.groupBy("position_id").agg(F.sum("contrib").alias("pop_raw"))
    return ratings, item_pop


def popularity_scores(item_pop: DataFrame) -> DataFrame:
    """100·log1p(raw)/log1p(peak)，未出现的职位在使用处补 0。"""
    peak = F.max("pop_raw").over(Window.partitionBy(F.lit(1)))
    return item_pop.select(
        "position_id",
        F.when(peak > 0, F.lit(100.0) * F.log1p("pop_raw") / F.log1p(peak)).otherwise(F.col("pop_raw")).alias("popularity"),
    )


def activity(ratings: DataFrame) -> DataFrame:
    return ratings.where(F.col("rating") > 0).groupBy("user_id").agg(F.count(F.lit(1)).cast("double").alias("activity"))


# --------------------------------------------------------------------------- 用户余弦


def user_cosine_neighbors(ratings: DataFrame, shrink: float = SHRINK, neighbors: int = NEIGHBORS) -> DataFrame:
    """[user_id, neighbor_id, cosine, co_count, similarity, rank_no]，每个学生最多 neighbors 个正相关邻居。"""
    r = ratings.where(F.col("rating") > 0).select("user_id", "position_id", "rating")
    norms = r.groupBy("user_id").agg(F.sqrt(F.sum(F.col("rating") * F.col("rating"))).alias("norm")).where(F.col("norm") > 1e-8)
    a = r.alias("a")
    b = r.alias("b")
    half = (
        a.join(b, (F.col("a.position_id") == F.col("b.position_id")) & (F.col("a.user_id") < F.col("b.user_id")))
        .groupBy(F.col("a.user_id").alias("user_id"), F.col("b.user_id").alias("neighbor_id"))
        .agg(
            F.sum(F.col("a.rating") * F.col("b.rating")).alias("dot"),
            F.count(F.lit(1)).alias("co_count"),
        )
    )
    pairs = half.unionByName(
        half.select(
            F.col("neighbor_id").alias("user_id"),
            F.col("user_id").alias("neighbor_id"),
            "dot",
            "co_count",
        )
    )
    nu = norms.select(F.col("user_id"), F.col("norm").alias("norm_u"))
    nv = norms.select(F.col("user_id").alias("neighbor_id"), F.col("norm").alias("norm_v"))
    sims = (
        pairs.join(nu, "user_id")
        .join(nv, "neighbor_id")
        .withColumn("cosine", F.col("dot") / (F.col("norm_u") * F.col("norm_v")))
        .withColumn("similarity", F.col("cosine") * F.col("co_count") / (F.col("co_count") + F.lit(float(shrink))))
        .where(F.col("similarity") > 0)
    )
    window = Window.partitionBy("user_id").orderBy(F.desc("similarity"), F.asc("neighbor_id"))
    return (
        sims.withColumn("rank_no", F.row_number().over(window))
        .where(F.col("rank_no") <= int(neighbors))
        .select("user_id", "neighbor_id", "cosine", F.col("co_count").cast("long").alias("co_count"), "similarity", "rank_no")
    )


def cosine_predictions(ratings: DataFrame, neighbors: DataFrame) -> DataFrame:
    """[user_id, position_id, cf_raw] = Σ sim·r_v / Σ sim（只含有邻居评分的职位，其余为 0）。"""
    denom = neighbors.groupBy("user_id").agg(F.sum("similarity").alias("sim_sum"))
    neighbor_ratings = ratings.where(F.col("rating") > 0).select(
        F.col("user_id").alias("neighbor_id"), "position_id", "rating"
    )
    return (
        neighbors.select("user_id", "neighbor_id", "similarity")
        .join(neighbor_ratings, "neighbor_id")
        .groupBy("user_id", "position_id")
        .agg(F.sum(F.col("similarity") * F.col("rating")).alias("num"))
        .join(denom, "user_id")
        .select("user_id", "position_id", (F.col("num") / F.greatest(F.col("sim_sum"), F.lit(1e-12))).alias("cf_raw"))
    )


# --------------------------------------------------------------------------- 留出


def split_holdout(events: DataFrame) -> DataFrame:
    """每个学生按时间留出最后约 20% 的收藏/投递职位（与 holdout_count 相同），返回 [user_id, position_id]。"""
    last = (
        events.where(F.col("behavior_type").isin(2, 3))
        .groupBy("user_id", "position_id")
        .agg(F.max(F.coalesce(F.col("ts").cast("double"), F.lit(0.0))).alias("ts"))
    )
    by_user = Window.partitionBy("user_id")
    ordered = Window.partitionBy("user_id").orderBy(F.desc("ts"), F.desc("position_id"))
    n = F.count(F.lit(1)).over(by_user)
    n_test = F.when(n < 2, F.lit(0)).otherwise(F.least(F.greatest(F.lit(1), F.round(n * 0.2).cast("int")), n - 1))
    return (
        last.withColumn("n_test", n_test)
        .withColumn("rn", F.row_number().over(ordered))
        .where(F.col("rn") <= F.col("n_test"))
        .select("user_id", "position_id")
    )


# --------------------------------------------------------------------------- 内容分


def user_tag_vectors(skills: DataFrame) -> DataFrame:
    return skills.groupBy("user_id", "tag_id").agg(F.max(F.col("proficiency").cast("double")).alias("prof"))


def tag_cosine(user_tags: DataFrame, job_tags: DataFrame) -> DataFrame:
    """[user_id, position_id, tag_cos]：熟练度向量与职位标签二值向量的余弦。"""
    jt = job_tags.select("position_id", "tag_id").distinct()
    unorm = user_tags.groupBy("user_id").agg(F.sqrt(F.sum(F.col("prof") * F.col("prof"))).alias("unorm"))
    jnorm = jt.groupBy("position_id").agg(F.sqrt(F.count(F.lit(1)).cast("double")).alias("jnorm"))
    return (
        user_tags.join(jt, "tag_id")
        .groupBy("user_id", "position_id")
        .agg(F.sum("prof").alias("dot"))
        .join(unorm, "user_id")
        .join(jnorm, "position_id")
        .select(
            "user_id",
            "position_id",
            F.least(F.lit(1.0), F.greatest(F.lit(0.0), F.col("dot") / (F.greatest(F.col("unorm"), F.lit(1e-12)) * F.greatest(F.col("jnorm"), F.lit(1e-12))))).alias("tag_cos"),
        )
    )


def with_content(cands: DataFrame, tag_cos: DataFrame, edu_penalty: float = EDU_PENALTY) -> DataFrame:
    """cands 需含学生维度 (u_edu, u_dir, u_city, u_major) 与职位维度 (j_edu, j_dir, j_city, j_text)。"""
    frame = cands.join(tag_cos, ["user_id", "position_id"], "left").fillna({"tag_cos": 0.0})
    dir_match = ((F.col("u_dir") != "") & (F.col("u_dir") == F.col("j_dir"))).cast("double")
    city_match = ((F.col("u_city") != "") & (F.col("u_city") == F.col("j_city"))).cast("double")
    edu_ok = (F.col("j_edu") == 0) | (F.col("j_edu") <= F.col("u_edu"))
    major_hit = ((F.length("u_major") >= 2) & (F.instr(F.col("j_text"), F.col("u_major")) > 0)).cast("double")
    base = F.lit(100.0) * (
        F.lit(0.50) * F.col("tag_cos")
        + F.lit(0.20) * F.col("dir_match")
        + F.lit(0.16) * F.col("city_match")
        + F.lit(0.08) * F.col("edu_ok").cast("double")
        + F.lit(0.06) * F.col("major_hit")
    )
    content = F.when(F.col("edu_ok"), base).otherwise(base * F.lit(float(edu_penalty)))
    return (
        frame.withColumn("dir_match", dir_match)
        .withColumn("city_match", city_match)
        .withColumn("edu_ok", edu_ok)
        .withColumn("major_hit", major_hit)
        .withColumn("content", F.least(F.lit(100.0), F.greatest(F.lit(0.0), content)))
    )


# --------------------------------------------------------------------------- 归一化与融合


def with_cf_minmax(frame: DataFrame, raw_col: str = "cf_raw") -> DataFrame:
    """按学生在候选集上把 raw_col 缩放到 0-100（全 0 行保持 0，平坦行为 100）；同时给出 cf_hi 供冷启动判断。"""
    stats = frame.groupBy("user_id").agg(F.min(raw_col).alias("cf_lo"), F.max(raw_col).alias("cf_hi"))
    span = F.col("cf_hi") - F.col("cf_lo")
    scaled = (
        F.when(F.col("cf_hi") <= 1e-8, F.lit(0.0))
        .when(span > 1e-6, (F.col(raw_col) - F.col("cf_lo")) / span * F.lit(100.0))
        .otherwise(F.lit(100.0))
    )
    return frame.join(stats, "user_id").withColumn("cf_mm", F.least(F.lit(100.0), F.greatest(F.lit(0.0), scaled)))


def fused_expr(alpha, fusion, adaptive) -> F.Column:
    """alpha/fusion/adaptive 可以是 Python 常量或列。需要 cf_mm、content、popularity、activity、cf_hi 列。"""
    alpha_c = alpha if isinstance(alpha, F.Column) else F.lit(float(alpha))
    fusion_c = fusion if isinstance(fusion, F.Column) else F.lit(str(fusion))
    adaptive_c = adaptive if isinstance(adaptive, F.Column) else F.lit(bool(adaptive))
    ramp = F.least(F.lit(1.0), F.greatest(F.lit(0.0), F.col("activity") / 8.0))
    alpha_u = F.when(adaptive_c, alpha_c * (F.lit(0.25) + F.lit(0.75) * ramp)).otherwise(alpha_c)
    gated = F.col("content") * ((F.lit(1.0) - alpha_u) + alpha_u * (F.col("cf_mm") / 100.0))
    linear = alpha_u * F.col("cf_mm") + (F.lit(1.0) - alpha_u) * F.col("content")
    mixed = F.when(fusion_c == "gated", gated).otherwise(linear)
    # 没有行为、或协同过滤整行为 0（max cf_mm<=0 ⇔ cf_hi<=1e-8）时按冷启动处理
    cold = (F.col("activity") <= 0) | (F.col("cf_hi") <= 1e-8)
    mixed = F.when(cold, F.lit(0.75) * F.col("content") + F.lit(0.25) * F.col("popularity")).otherwise(mixed)
    return F.least(F.lit(100.0), F.greatest(F.lit(0.0), mixed))


# --------------------------------------------------------------------------- 排序与评估


def top_k(frame: DataFrame, score_col: str, k: int, partition_cols: list[str]) -> DataFrame:
    key = F.col(score_col) - F.col("item_idx") * F.lit(TIE_EPS)
    window = Window.partitionBy(*partition_cols).orderBy(key.desc(), F.asc("position_id"))
    return frame.withColumn("rank_no", F.row_number().over(window)).where(F.col("rank_no") <= int(k))


def evaluate(spark, ranked: DataFrame, truth: DataFrame, ks, catalog_size: int, group_cols: list[str]) -> list[dict]:
    """ranked: group_cols + [user_id, position_id, rank_no]（rank_no<=max(ks)，只含真值学生）。
    返回 [{group..., k, precision, recall, ndcg, coverage, userCount}]，与 evaluate_rankings 口径一致。"""
    catalog = float(catalog_size if catalog_size > 0 else 1)
    ks_df = spark.createDataFrame([(int(k),) for k in ks], ["k"])
    truth = truth.select("user_id", "position_id").distinct()
    sizes = truth.groupBy("user_id").agg(F.count(F.lit(1)).alias("n_rel"))
    groups = ranked.select(*group_cols).distinct() if group_cols else None
    rel = ranked.join(truth.withColumn("rel", F.lit(1.0)), ["user_id", "position_id"], "left").fillna({"rel": 0.0})
    cut = rel.crossJoin(ks_df).where(F.col("rank_no") <= F.col("k")).join(sizes.select("user_id"), "user_id")
    per_user = cut.groupBy(*group_cols, "k", "user_id").agg(
        F.sum("rel").alias("hits"),
        F.sum(F.col("rel") / F.log2(F.col("rank_no") + 1.0)).alias("dcg"),
    )
    base = sizes.crossJoin(ks_df)
    if groups is not None:
        base = base.crossJoin(groups)
    joined = base.join(per_user, [*group_cols, "k", "user_id"], "left").fillna({"hits": 0.0, "dcg": 0.0})
    idcg = F.expr("aggregate(sequence(1, least(k, n_rel)), 0D, (acc, i) -> acc + 1D / log2(i + 1))")
    metrics = joined.groupBy(*group_cols, "k").agg(
        F.avg(F.col("hits") / F.col("k")).alias("precision"),
        F.avg(F.col("hits") / F.col("n_rel")).alias("recall"),
        F.avg(F.when(idcg > 0, F.col("dcg") / idcg).otherwise(F.lit(0.0))).alias("ndcg"),
        F.count(F.lit(1)).alias("userCount"),
    )
    coverage = cut.groupBy(*group_cols, "k").agg((F.countDistinct("position_id") / F.lit(catalog)).alias("coverage"))
    out = metrics.join(coverage, [*group_cols, "k"], "left").fillna({"coverage": 0.0})
    rows = []
    for row in out.collect():
        item = row.asDict()
        rows.append(
            {
                **{col: item[col] for col in group_cols},
                "k": int(item["k"]),
                "precision": float(item["precision"] or 0.0),
                "recall": float(item["recall"] or 0.0),
                "ndcg": float(item["ndcg"] or 0.0),
                "coverage": float(item["coverage"] or 0.0),
                "userCount": int(item["userCount"] or 0),
            }
        )
    rows.sort(key=lambda r: ([str(r[c]) for c in group_cols], r["k"]))
    return rows


# --------------------------------------------------------------------------- 推荐理由所需的技能重合


def skill_overlap(pairs: DataFrame, user_tags: DataFrame, job_tags: DataFrame, tag_names: DataFrame) -> DataFrame:
    """[user_id, position_id, skill_percent, skill_names]，口径同 recommend_eval.skill_match_percent。"""
    jt = job_tags.select("position_id", "tag_id").distinct()
    jcount = jt.groupBy("position_id").agg(F.count(F.lit(1)).alias("jcount"))
    unorm = user_tags.groupBy("user_id").agg(F.sqrt(F.sum(F.col("prof") * F.col("prof"))).alias("unorm"))
    named = jt.join(tag_names.where(F.col("tag_name") != ""), "tag_id")
    overlap = (
        pairs.select("user_id", "position_id")
        .distinct()
        .join(user_tags, "user_id")
        .join(named, ["position_id", "tag_id"])
        .groupBy("user_id", "position_id")
        .agg(
            F.sum("prof").alias("num"),
            F.sort_array(F.collect_list(F.struct((-F.col("prof")).alias("neg"), F.col("tag_name").alias("name")))).alias("lst"),
        )
        .join(unorm, "user_id")
        .join(jcount, "position_id")
    )
    percent = F.when(
        (F.col("unorm") > 0) & (F.col("jcount") > 0),
        F.bround(F.lit(100.0) * F.col("num") / (F.col("unorm") * F.sqrt(F.col("jcount").cast("double"))), 0),
    ).otherwise(F.lit(0.0))
    return overlap.select(
        "user_id",
        "position_id",
        F.least(F.lit(100), F.greatest(F.lit(0), percent.cast("int"))).alias("skill_percent"),
        F.expr("transform(slice(lst, 1, 3), x -> x.name)").alias("skill_names"),
    )
