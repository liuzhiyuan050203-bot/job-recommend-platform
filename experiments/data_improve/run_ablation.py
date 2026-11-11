#!/usr/bin/env python3
"""薪资预测数据改善消融：所有指标都在固定黄金测试集（golden_test_ids.csv，300 条 BOSS 2023 真实月薪）上报告。

  .venv/bin/python experiments/data_improve/run_ablation.py --step step0   # 基线：现有模型
  .venv/bin/python experiments/data_improve/run_ablation.py --step step1   # + 特征工程
  .venv/bin/python experiments/data_improve/run_ablation.py --step step2   # + 外部扩充样本
输出：results/<step>_metrics.csv、results/<step>.json、results/<step>_predictions.csv
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import pandas as pd

from di_common import RESULTS, bootstrap_ci, load_real, metrics, split_core

import common  # noqa: E402  (experiments/common.py：Spark 会话、JAVA_HOME)
from pyspark.ml import Pipeline  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

TARGET = "avg_salary"


def to_spark(spark, pdf: pd.DataFrame, cols: list[str]):
    sdf = spark.createDataFrame(pdf[cols].copy())
    if "tokens" in cols:
        sdf = sdf.withColumn("tok_arr", F.expr("filter(split(tokens, ' '), x -> x != '')"))
    return sdf


def exp_frame(df: pd.DataFrame) -> pd.DataFrame:
    """run_salary_experiment.load() 同口径列。"""
    out = df[["city", "city_tier", "edu_years", "exp_years", "tech_direction", "company_size", "industry", "tokens",
              "avg_salary", "data_year", "row_id"]].copy()
    out["job_type"] = 1.0
    out["industry"] = out["industry"].replace("", "未知")
    for c in ("city_tier", "exp_years", "avg_salary", "company_size"):
        out[c] = out[c].astype(float)
    return out


def record(rows, preds, step, variant, train_src, model, golden, pred, n_train, extra=None):
    m = metrics(golden[TARGET].values, pred)
    ci = bootstrap_ci(golden[TARGET].values, pred)
    rec = {"step": step, "variant": variant, "train_source": train_src, "model": model, "n_train": int(n_train),
           "n_golden": int(len(golden)), "mae": round(m["mae"], 1), "rmse": round(m["rmse"], 1), "r2": round(m["r2"], 4),
           "r2_ci95": f"[{ci['r2_ci'][0]:.3f}, {ci['r2_ci'][1]:.3f}]",
           "mae_ci95": f"[{ci['mae_ci'][0]:.0f}, {ci['mae_ci'][1]:.0f}]", **(extra or {})}
    rows.append(rec)
    preds[f"{variant}|{model}"] = list(map(float, pred))
    print(f"  {variant:<34} {model:<22} n={n_train:<6} MAE={rec['mae']:<8} RMSE={rec['rmse']:<8} R2={rec['r2']}", flush=True)


def spark_predict(model, sdf_golden, golden):
    out = model.transform(sdf_golden).select("row_id", "prediction").toPandas().set_index("row_id")["prediction"]
    return out.reindex(golden["row_id"]).values


def step0(spark, rows, preds):
    from app.spark import salary_model as prod
    import salary.run_salary_experiment as rse

    core, golden, stats = split_core()
    print("切分:", stats)
    excluded = set(load_real("boss_2023")["row_id"]) - set(core["row_id"])

    # (1) 均值基线
    record(rows, preds, "step0", "baseline", "core", "MeanBaseline", golden,
           [core[TARGET].mean()] * len(golden), len(core))

    # (2) 现有生产模型：PySpark RF，pooled_real(BOSS+51job)，生产 _pipeline() 原样
    prod._excluded_ids = lambda: []  # 先读全量，再在这里按同一排除清单切分
    full = prod._load_real(spark).cache()
    g_ids = list(golden["row_id"])
    train = full.filter(F.col("row_id").isNull() | ~F.col("row_id").isin(list(excluded))).cache()
    gold_s = full.filter(F.col("row_id").isin(g_ids)).cache()
    n = train.count()
    t0 = time.time()
    model = prod._pipeline().fit(train)
    record(rows, preds, "step0", "prod_pooled_real", "core+51job", "SparkRF(prod)", golden,
           spark_predict(model, gold_s, golden), n, {"fit_s": round(time.time() - t0, 1)})

    # (3) 既有实验管线（run_salary_experiment.stages_for），只用 core 训练
    core_s = to_spark(spark, exp_frame(core), list(exp_frame(core).columns)).cache()
    gold_e = to_spark(spark, exp_frame(golden), list(exp_frame(golden).columns)).cache()
    for fs in rse.FEATURE_SETS["boss_2023"]:
        for mname in ("RandomForest", "GBT"):
            est = rse.models()[mname]
            t0 = time.time()
            model = Pipeline(stages=rse.stages_for(fs) + [est]).fit(core_s)
            record(rows, preds, "step0", f"core:{fs}", "core", f"Spark{mname}", golden,
                   spark_predict(model, gold_e, golden), len(core), {"fit_s": round(time.time() - t0, 1)})
    return golden


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", default="step0", choices=["step0", "step1", "step2"])
    ap.add_argument("--driver-memory", default="3g")
    args = ap.parse_args()
    spark = common.spark_session(driver_memory=args.driver_memory, app=f"data-improve-{args.step}")
    rows, preds = [], {}
    if args.step == "step0":
        golden = step0(spark, rows, preds)
    else:
        import steps_feat
        golden = steps_feat.run(spark, args.step, rows, preds, record, spark_predict, to_spark)
    pd.DataFrame(rows).to_csv(RESULTS / f"{args.step}_metrics.csv", index=False)
    p = pd.DataFrame(preds)
    p.insert(0, "row_id", list(golden["row_id"]))
    p.insert(1, "y_true", list(golden[TARGET]))
    p.to_csv(RESULTS / f"{args.step}_predictions.csv", index=False)
    (RESULTS / f"{args.step}.json").write_text(json.dumps({"env": common.env_info(), "rows": rows}, ensure_ascii=False,
                                                          indent=2), encoding="utf-8")
    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
