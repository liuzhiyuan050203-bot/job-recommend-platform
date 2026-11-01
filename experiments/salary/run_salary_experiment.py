#!/usr/bin/env python3
"""薪资回归对比实验（Spark MLlib）。

一条命令：  .venv/bin/python experiments/salary/run_salary_experiment.py [--folds 5] [--datasets a,b]

协议：每个数据集先按 seed=42 留出 20% 测试集；在其余 80% 上做 K 折交叉验证（报告 mean±std），
再用全部 80% 训练、在 20% 测试集上报告 R²/RMSE/MAE。所有特征编码器（StringIndexer/CountVectorizer/IDF）
均只在训练折上拟合，避免信息泄漏。
输出：experiments/results/salary_metrics.csv、salary_results.json、salary_importance.json 与 figures/salary_*.png
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import DATA, FIGURES, REPO, RESULTS, env_info, save_json, setup_matplotlib, spark_session  # noqa: E402

from pyspark.ml import Pipeline  # noqa: E402
from pyspark.ml.evaluation import RegressionEvaluator  # noqa: E402
from pyspark.ml.feature import IDF, CountVectorizer, OneHotEncoder, StringIndexer, VectorAssembler  # noqa: E402
from pyspark.ml.regression import GBTRegressor, LinearRegression, RandomForestRegressor  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

EDU_YEARS = {0: 16.0, 1: 15.0, 2: 16.0, 3: 19.0, 4: 22.0}
SEED = 42
LAMBDA_GRID = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]  # Ridge/Lasso 正则强度，按训练集 K 折 CV 的平均 R² 选择

DATASETS = {
    "synthetic": {"path": DATA / "platform_synthetic.csv", "label": "(a) 合成基准集 demo_（生成器公式）", "ground_truth": "合成"},
    "campus_estimated": {"path": DATA / "platform_campus_estimated.csv", "label": "(a') 真实校招·估算薪资（非真值）", "ground_truth": "估算，不可作真值"},
    "boss_2023": {"path": REPO / "data/real_salary/boss_2023.csv", "label": "(b1) BOSS直聘 2023 真实薪资", "ground_truth": "真实"},
    "job51_2018": {"path": REPO / "data/real_salary/job51_2018.csv", "label": "(b2) 前程无忧 2018 真实薪资", "ground_truth": "真实"},
    "pooled_real": {"path": None, "label": "(b3) 合并真实集（含年份特征，生产模型口径）", "ground_truth": "真实"},
}
FEATURE_SETS = {
    "synthetic": ["base", "base+jobtype", "base+jobtype+text"],
    "campus_estimated": ["base", "base+jobtype", "base+jobtype+text"],
    "boss_2023": ["base", "base+company", "base+company+text"],
    "job51_2018": ["base", "base+company", "base+company+text"],
    "pooled_real": ["base+year"],
}


def load(name: str) -> pd.DataFrame:
    if name == "pooled_real":
        a = load("boss_2023")
        b = load("job51_2018")
        return pd.concat([a, b], ignore_index=True)
    df = pd.read_csv(DATASETS[name]["path"])
    df["edu_years"] = df["education"].map(EDU_YEARS).astype(float)
    df["data_year"] = 2023.0 if name == "boss_2023" else 2018.0 if name == "job51_2018" else 2026.0
    df["tokens"] = df["tokens"].fillna("").astype(str)
    df["industry"] = df["industry"].fillna("未知").astype(str)
    df["company_size"] = df["company_size"].fillna(0).astype(float)
    df["job_type"] = df["job_type"].astype(float) if "job_type" in df else 1.0
    keep = ["job_type", "city", "city_tier", "edu_years", "exp_years", "tech_direction", "company_size", "industry",
            "tokens", "avg_salary", "data_year"]
    out = df[keep].copy()
    out["city_tier"] = out["city_tier"].astype(float)
    out["exp_years"] = out["exp_years"].astype(float)
    out["avg_salary"] = out["avg_salary"].astype(float)
    return out


def stages_for(fs: str):
    stages, cols = [], []
    for col in ("city", "tech_direction"):
        stages.append(StringIndexer(inputCol=col, outputCol=f"{col}_idx", handleInvalid="keep", stringOrderType="alphabetAsc"))
        stages.append(OneHotEncoder(inputCols=[f"{col}_idx"], outputCols=[f"{col}_vec"], handleInvalid="keep", dropLast=False))
        cols.append(f"{col}_vec")
    cols += ["city_tier", "edu_years", "exp_years"]
    if "jobtype" in fs:
        cols.append("job_type")
    if "company" in fs:
        stages.append(StringIndexer(inputCol="industry", outputCol="industry_idx", handleInvalid="keep", stringOrderType="frequencyDesc"))
        stages.append(OneHotEncoder(inputCols=["industry_idx"], outputCols=["industry_vec"], handleInvalid="keep", dropLast=False))
        cols += ["company_size", "industry_vec"]
    if "text" in fs:
        stages.append(CountVectorizer(inputCol="tok_arr", outputCol="tf", vocabSize=300, minDF=5.0))
        stages.append(IDF(inputCol="tf", outputCol="tfidf"))
        cols.append("tfidf")
    if "year" in fs:
        cols.append("data_year")
    stages.append(VectorAssembler(inputCols=cols, outputCol="features", handleInvalid="keep"))
    return stages


def models():
    return {
        "LinearRegression": LinearRegression(labelCol="avg_salary", regParam=0.0, maxIter=100),
        "Ridge": LinearRegression(labelCol="avg_salary", elasticNetParam=0.0, maxIter=100),
        "Lasso": LinearRegression(labelCol="avg_salary", elasticNetParam=1.0, maxIter=100),
        "RandomForest": RandomForestRegressor(labelCol="avg_salary", numTrees=100, maxDepth=10, minInstancesPerNode=3,
                                              subsamplingRate=0.9, featureSubsetStrategy="onethird", seed=SEED),
        "GBT": GBTRegressor(labelCol="avg_salary", maxIter=80, maxDepth=5, stepSize=0.1, subsamplingRate=0.8, seed=SEED),
    }


def score(pred) -> dict:
    return {m: float(RegressionEvaluator(labelCol="avg_salary", predictionCol="prediction", metricName=m).evaluate(pred))
            for m in ("r2", "rmse", "mae")}


def mean_baseline(train, test) -> dict:
    mu = train.agg(F.avg("avg_salary")).first()[0]
    return score(test.withColumn("prediction", F.lit(float(mu))))


def feature_names(frame) -> list[str]:
    meta = frame.schema["features"].metadata.get("ml_attr", {})
    names = {}
    for group in meta.get("attrs", {}).values():
        for a in group:
            names[a["idx"]] = a.get("name", f"f{a['idx']}")
    return [names.get(i, f"f{i}") for i in range(meta.get("num_attrs", len(names)))]


def group_of(name: str) -> str:
    for prefix, g in (("city_vec", "城市"), ("tech_direction_vec", "技术方向"), ("industry_vec", "行业"), ("tfidf", "标题/技能TF-IDF"),
                      ("city_tier", "城市等级"), ("edu_years", "学历"), ("exp_years", "经验"), ("company_size", "公司规模"),
                      ("data_year", "数据年份")):
        if name.startswith(prefix):
            return g
    return name


def run(args) -> int:
    spark = spark_session(driver_memory=args.driver_memory, app="salary-experiment")
    rows, importance, details = [], {}, {}
    plt = setup_matplotlib()
    selected = [d for d in args.datasets.split(",") if d]
    for ds in selected:
        pdf = load(ds)
        sdf = spark.createDataFrame(pdf).withColumn("tok_arr", F.expr("filter(split(tokens, ' '), x -> x != '')"))
        train, test = sdf.randomSplit([0.8, 0.2], seed=SEED)
        train = train.withColumn("fold", (F.rand(SEED) * args.folds).cast("int")).cache()
        test = test.cache()
        n_train, n_test = train.count(), test.count()
        details[ds] = {"label": DATASETS[ds]["label"], "ground_truth": DATASETS[ds]["ground_truth"], "rows": int(len(pdf)),
                       "train": n_train, "test": n_test, "salary_mean": float(pdf["avg_salary"].mean()),
                       "salary_std": float(pdf["avg_salary"].std())}
        print(f"\n==== {ds}: rows={len(pdf)} train={n_train} test={n_test}", flush=True)
        base = mean_baseline(train, test)
        rows.append({"dataset": ds, "feature_set": "-", "model": "MeanBaseline", **{f"test_{k}": v for k, v in base.items()},
                     **{f"cv_{k}_mean": None for k in ("r2", "rmse", "mae")}, **{f"cv_{k}_std": None for k in ("r2", "rmse", "mae")},
                     "fit_seconds": 0.0})
        for fs in FEATURE_SETS[ds]:
            for mname, est in models().items():
                t0 = time.time()
                grid = LAMBDA_GRID if mname in ("Ridge", "Lasso") else [None]
                best = None
                for lam in grid:
                    if lam is not None:
                        est = est.copy({est.regParam: lam})
                    cv = []
                    for k in range(args.folds):
                        tr = train.filter(F.col("fold") != k)
                        va = train.filter(F.col("fold") == k)
                        model = Pipeline(stages=stages_for(fs) + [est]).fit(tr)
                        cv.append(score(model.transform(va)))
                    r2m = sum(c["r2"] for c in cv) / len(cv)
                    if best is None or r2m > best[0]:
                        best = (r2m, lam, cv, est)
                _, lam, cv, est = best
                final = Pipeline(stages=stages_for(fs) + [est]).fit(train)
                pred = final.transform(test)
                te = score(pred)
                elapsed = time.time() - t0
                rec = {"dataset": ds, "feature_set": fs, "model": mname if lam is None else f"{mname}(λ={lam:g})",
                       "fit_seconds": round(elapsed, 1)}
                for m in ("r2", "rmse", "mae"):
                    vals = [c[m] for c in cv]
                    rec[f"cv_{m}_mean"] = float(pd.Series(vals).mean())
                    rec[f"cv_{m}_std"] = float(pd.Series(vals).std(ddof=1)) if len(vals) > 1 else 0.0
                    rec[f"test_{m}"] = te[m]
                rows.append(rec)
                print(f"  {fs:<20} {rec['model']:<16} CV R2={rec['cv_r2_mean']:.4f}±{rec['cv_r2_std']:.4f} "
                      f"test R2={te['r2']:.4f} RMSE={te['rmse']:.0f} MAE={te['mae']:.0f} ({elapsed:.0f}s)", flush=True)
                last_fs = FEATURE_SETS[ds][-1]
                if fs == last_fs and mname in ("RandomForest", "GBT"):
                    reg = final.stages[-1]
                    names = feature_names(pred)
                    imp = reg.featureImportances.toArray().tolist()
                    grouped: dict[str, float] = {}
                    for n, v in zip(names, imp):
                        grouped[group_of(n)] = grouped.get(group_of(n), 0.0) + v
                    top = sorted(zip(names, imp), key=lambda x: -x[1])[:15]
                    importance[f"{ds}|{fs}|{mname}"] = {"grouped": dict(sorted(grouped.items(), key=lambda x: -x[1])),
                                                         "top_features": [[n, v] for n, v in top]}
                if fs == last_fs and mname == "GBT":
                    sample = pred.select("avg_salary", "prediction").limit(3000).toPandas()
                    fig, ax = plt.subplots(figsize=(4.6, 4.2))
                    ax.scatter(sample["avg_salary"], sample["prediction"], s=4, alpha=0.35)
                    lim = [0, max(sample["avg_salary"].quantile(0.99), sample["prediction"].quantile(0.99))]
                    ax.plot(lim, lim, "r--", lw=1)
                    ax.set_xlim(lim); ax.set_ylim(lim)
                    ax.set_xlabel("真实月薪（元）"); ax.set_ylabel("预测月薪（元）")
                    ax.set_title(f"{ds} · GBT · 测试集 R²={te['r2']:.3f}", fontsize=10)
                    fig.tight_layout(); fig.savefig(FIGURES / f"salary_scatter_{ds}.png"); plt.close(fig)
        train.unpersist(); test.unpersist()

    out = RESULTS / "salary_metrics.csv"
    existing = []
    if out.exists() and args.merge:
        existing = [r for r in csv.DictReader(out.open(encoding="utf-8")) if r["dataset"] not in selected]
    fields = ["dataset", "feature_set", "model", "test_r2", "test_rmse", "test_mae", "cv_r2_mean", "cv_r2_std",
              "cv_rmse_mean", "cv_rmse_std", "cv_mae_mean", "cv_mae_std", "fit_seconds"]
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in existing + rows:
            w.writerow({k: r.get(k) for k in fields})
    print("[saved]", out)
    prev = {}
    jpath = RESULTS / "salary_results.json"
    if jpath.exists() and args.merge:
        import json
        prev = json.loads(jpath.read_text(encoding="utf-8"))
    payload = {"env": env_info(), "protocol": {"holdout": "80/20 randomSplit seed=42", "cv_folds": args.folds, "lambda_grid": LAMBDA_GRID,
                                               "target": "月薪中位数 (salary_min+salary_max)/2，单位元"},
               "datasets": {**prev.get("datasets", {}), **details}}
    save_json("salary_results.json", payload)
    prev_imp = {}
    ipath = RESULTS / "salary_importance.json"
    if ipath.exists() and args.merge:
        import json
        prev_imp = {k: v for k, v in json.loads(ipath.read_text(encoding="utf-8")).items() if k.split("|")[0] not in selected}
    save_json("salary_importance.json", {**prev_imp, **importance})
    spark.stop()
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--datasets", default="synthetic,campus_estimated,boss_2023,job51_2018,pooled_real")
    ap.add_argument("--driver-memory", default="2g")
    ap.add_argument("--merge", action="store_true", help="只重跑指定数据集并与已有结果合并")
    sys.exit(run(ap.parse_args()))
