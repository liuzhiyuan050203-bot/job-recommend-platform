"""单次压测：一个引擎 × 一个任务 × 一个规模，在独立进程中运行，结果以 JSON 打印到 stdout 最后一行。

由 run_scale_bench.py 调用；也可手动：
    .venv/bin/python experiments/scale/bench_worker.py --engine spark --cores 4 --task clean --scale 100000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import DATA  # noqa: E402,F401  (同时把 ai-service 加入 sys.path)

SCALE_DIR = Path(__file__).resolve().parents[1] / "data" / "scale"
TMP = Path("/tmp/bishe-scale")


def tag_split(series):
    return series.fillna("").str.replace("、", ",", regex=False).str.split(",")


# ------------------------------------------------------------------ pandas
def pandas_clean(scale):
    import pandas as pd
    from app.spark.clean import _parse_row

    raw = pd.read_csv(SCALE_DIR / f"jobs_{scale}.csv", dtype=str, keep_default_na=False)
    raw_count = len(raw)
    keyed = raw.drop_duplicates().drop_duplicates(["title", "company", "city"])
    cols = ["status", "city", "province", "salary_min", "salary_max", "salary_avg", "salary_months",
            "education", "experience_req", "publish_date", "direction"]
    parsed = pd.DataFrame(
        [_parse_row(*r) for r in keyed[["salary_text", "city", "education_text", "experience_text", "publish_date", "direction"]].itertuples(index=False, name=None)],
        columns=cols, index=keyed.index,
    )
    out = pd.concat([keyed[["title", "company", "tags"]], parsed], axis=1)
    counts = out["status"].value_counts().to_dict()
    valid = out[out["status"] == "valid"]
    TMP.mkdir(parents=True, exist_ok=True)
    valid.to_parquet(TMP / f"clean_pandas_{scale}.parquet", index=False)
    return {"raw": raw_count, "valid": int(counts.get("valid", 0)), "status": {k: int(v) for k, v in counts.items()}}


def pandas_aggregate(scale):
    import pandas as pd

    df = pd.read_parquet(SCALE_DIR / f"clean_{scale}.parquet")
    g = df.groupby(["province", "city", "direction"])["salary_avg"]
    salary = g.agg(job_count="count", avg_salary="mean",
                   p25=lambda s: s.quantile(0.25), median="median", p75=lambda s: s.quantile(0.75)).reset_index()
    tags = df.assign(month=df["publish_date"].str[:7], tag=tag_split(df["tags"])).explode("tag")
    tags = tags[tags["tag"].str.len() > 0].groupby(["month", "tag"]).size().reset_index(name="cnt")
    region = df.groupby("province")["salary_avg"].agg(["count", "mean"]).reset_index()
    return {"salary_groups": len(salary), "tag_month_groups": len(tags), "provinces": len(region)}


def pandas_als(scale, threads):
    import numpy as np
    import pandas as pd
    import scipy.sparse as sp
    from threadpoolctl import threadpool_limits
    import implicit

    ev = pd.read_parquet(SCALE_DIR / f"events_{scale}.parquet")
    agg = ev.groupby(["user_id", "position_id"], as_index=False)["weight"].sum()
    agg["rating"] = np.log1p(agg["weight"].astype(np.float32))
    n_u, n_i = int(agg["user_id"].max()) + 1, int(agg["position_id"].max()) + 1
    mat = sp.csr_matrix((agg["rating"].to_numpy(np.float32) * 20.0, (agg["user_id"], agg["position_id"])), shape=(n_u, n_i))
    with threadpool_limits(1, "blas"):
        model = implicit.cpu.als.AlternatingLeastSquares(factors=16, regularization=0.1, iterations=10,
                                                         num_threads=threads, random_state=42)
        model.fit(mat, show_progress=False)
    return {"pairs": len(agg), "users": n_u, "items": n_i}


# ------------------------------------------------------------------ spark
def spark_session(cores, driver_memory):
    from pyspark.sql import SparkSession

    tmp = TMP / "spark-local"
    tmp.mkdir(parents=True, exist_ok=True)
    return (
        SparkSession.builder.appName("scale-bench").master(f"local[{cores}]")
        .config("spark.driver.memory", driver_memory)
        .config("spark.sql.shuffle.partitions", str(max(4, 2 * int(cores))))
        .config("spark.ui.enabled", "false").config("spark.ui.showConsoleProgress", "false")
        .config("spark.driver.host", "127.0.0.1").config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.local.dir", str(tmp))
        .config("spark.sql.session.timeZone", "Asia/Shanghai")
        .getOrCreate()
    )


def spark_clean(spark, scale):
    from pyspark.sql import functions as F
    from app.spark.clean import _PARSE_SCHEMA, _parse_row

    raw = spark.read.option("header", True).option("encoding", "UTF-8").option("escape", '"').csv(str(SCALE_DIR / f"jobs_{scale}.csv"))
    raw_count = raw.count()
    keyed = raw.dropDuplicates().dropDuplicates(["title", "company", "city"])
    parse = F.udf(_parse_row, _PARSE_SCHEMA)
    parsed = keyed.withColumn("parsed", parse("salary_text", "city", "education_text", "experience_text", "publish_date", "direction")).cache()
    counts = {r["s"]: int(r["count"]) for r in parsed.groupBy(F.col("parsed.status").alias("s")).count().collect()}
    valid = parsed.filter(F.col("parsed.status") == "valid").select("title", "company", "tags", "parsed.*")
    valid.write.mode("overwrite").parquet(str(TMP / f"clean_spark_{scale}.parquet"))
    parsed.unpersist()
    return {"raw": raw_count, "valid": counts.get("valid", 0), "status": counts}


def spark_aggregate(spark, scale):
    from pyspark.sql import functions as F

    df = spark.read.parquet(str(SCALE_DIR / f"clean_{scale}.parquet")).cache()
    salary = df.groupBy("province", "city", "direction").agg(
        F.count("*").alias("job_count"), F.avg("salary_avg").alias("avg_salary"),
        F.expr("percentile_approx(salary_avg, 0.25, 10000)").alias("p25"),
        F.expr("percentile_approx(salary_avg, 0.5, 10000)").alias("median"),
        F.expr("percentile_approx(salary_avg, 0.75, 10000)").alias("p75"),
    ).collect()
    tags = (
        df.withColumn("month", F.substring("publish_date", 1, 7))
        .withColumn("tag", F.explode(F.split(F.regexp_replace(F.coalesce("tags", F.lit("")), "、", ","), ",")))
        .filter(F.length("tag") > 0).groupBy("month", "tag").count().collect()
    )
    region = df.groupBy("province").agg(F.count("*"), F.avg("salary_avg")).collect()
    df.unpersist()
    return {"salary_groups": len(salary), "tag_month_groups": len(tags), "provinces": len(region)}


def spark_als(spark, scale):
    from pyspark.ml.recommendation import ALS
    from pyspark.sql import functions as F

    ev = spark.read.parquet(str(SCALE_DIR / f"events_{scale}.parquet"))
    agg = ev.groupBy("user_id", "position_id").agg(F.sum("weight").alias("w")).withColumn("rating", F.log1p("w")).cache()
    pairs = agg.count()
    model = ALS(userCol="user_id", itemCol="position_id", ratingCol="rating", implicitPrefs=True, rank=16,
                maxIter=10, regParam=0.1, alpha=20.0, seed=42, checkpointInterval=-1).fit(agg)
    users = model.userFactors.count()
    items = model.itemFactors.count()
    agg.unpersist()
    return {"pairs": pairs, "users": users, "items": items}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["pandas", "spark"], required=True)
    ap.add_argument("--cores", type=int, default=1)
    ap.add_argument("--task", choices=["clean", "aggregate", "als"], required=True)
    ap.add_argument("--scale", type=int, required=True)
    ap.add_argument("--driver-memory", default="3g")
    args = ap.parse_args()
    t0 = time.perf_counter()
    startup = 0.0
    if args.engine == "pandas":
        os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
        t1 = time.perf_counter()
        if args.task == "clean":
            info = pandas_clean(args.scale)
        elif args.task == "aggregate":
            info = pandas_aggregate(args.scale)
        else:
            info = pandas_als(args.scale, args.cores)
    else:
        spark = spark_session(args.cores, args.driver_memory)
        spark.sparkContext.setLogLevel("ERROR")
        spark.range(1).count()
        t1 = time.perf_counter()
        startup = t1 - t0
        fn = {"clean": spark_clean, "aggregate": spark_aggregate, "als": spark_als}[args.task]
        info = fn(spark, args.scale)
    task_s = time.perf_counter() - t1
    print(json.dumps({"task_seconds": round(task_s, 3), "startup_seconds": round(startup, 3), "info": info}, ensure_ascii=False))


if __name__ == "__main__":
    main()
