"""第 2 步（特征工程）与第 3 步（外部扩充）的消融，被 run_ablation.py 调用。"""

from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd

from di_common import HERE, load_real, split_core
from extract import extract_frame, load_cache
from features import Featurizer

TARGET = "avg_salary"
EMB_CACHE = HERE / "cache"
LADDER = [  # 每一行在上一行基础上加一组特征
    ("F0 base(城市/方向/学历/经验)", []),
    ("F1 +公司规模/行业", ["company"]),
    ("F2 +标题职级/岗位类型", ["company", "title"]),
    ("F3 +公司档位", ["company", "title", "tier"]),
    ("F4 +福利标记", ["company", "title", "tier", "welfare"]),
    ("F5 +结构化硬技能", ["company", "title", "tier", "welfare", "skills"]),
    ("F6 +bge向量PCA16", ["company", "title", "tier", "welfare", "skills", "emb"]),
]


def embed(df: pd.DataFrame, name: str) -> np.ndarray:
    """bge-small-zh-v1.5（与 RAG 同一模型）对「职位名 + 技能」编码，按 row_id 缓存为 npz（不入库）。"""
    path = EMB_CACHE / f"emb_{name}.npz"
    if path.exists():
        z = np.load(path, allow_pickle=True)
        idx = {r: i for i, r in enumerate(z["ids"])}
        if all(r in idx for r in df["row_id"]):
            return z["emb"][[idx[r] for r in df["row_id"]]]
    from fastembed import TextEmbedding
    cache_dir = os.getenv("EMBEDDING_CACHE_DIR", str(HERE.parents[1] / "ai-service" / "data" / "models"))
    model = TextEmbedding(model_name="BAAI/bge-small-zh-v1.5", cache_dir=cache_dir, threads=4)
    texts = (df["title"] + " " + df["skills"]).str.slice(0, 200).tolist()
    t0 = time.time()
    emb = np.asarray(list(model.embed(texts, batch_size=128)), dtype=np.float32)
    print(f"  bge 编码 {len(texts)} 条 {time.time() - t0:.0f}s", flush=True)
    np.savez_compressed(path, ids=np.asarray(df["row_id"]), emb=emb)
    return emb


def extractor(df: pd.DataFrame) -> dict:
    backend = os.getenv("EXTRACT_BACKEND", "rule")
    res = extract_frame(df, "rule")
    if backend == "llm":  # 仅使用已缓存的 LLM 结果（先跑 extract.py --backend llm），缺的用规则补
        cache = load_cache("llm")
        from extract import key_of
        model = os.getenv("EXTRACT_LLM_MODEL") or os.getenv("LLM_MODEL") or "qwen2.5:3b"
        hit = 0
        for row in df.to_dict("records"):
            rec = cache.get(key_of("llm", model, row))
            if rec:
                res[row["row_id"]] = rec["result"]
                hit += 1
        print(f"  LLM 抽取缓存命中 {hit}/{len(df)}，其余用规则")
    return res


def spark_fit_predict(spark, kind, Xtr, ytr, Xte, wtr=None):
    from pyspark.ml.feature import VectorAssembler
    from pyspark.ml.regression import GBTRegressor, RandomForestRegressor
    cols = [f"f{i}" for i in range(Xtr.shape[1])]
    tr = pd.DataFrame(Xtr.values, columns=cols)
    tr["label"] = np.asarray(ytr, float)
    tr["w"] = 1.0 if wtr is None else np.asarray(wtr, float)
    te = pd.DataFrame(Xte.values, columns=cols)
    te["rid"] = np.arange(len(te))
    va = VectorAssembler(inputCols=cols, outputCol="features")
    s_tr = va.transform(spark.createDataFrame(tr))
    s_te = va.transform(spark.createDataFrame(te))
    if kind == "SparkRF":  # 与生产 salary_model._pipeline() 同超参
        est = RandomForestRegressor(labelCol="label", weightCol="w", numTrees=100, maxDepth=10, seed=42,
                                    subsamplingRate=0.8, featureSubsetStrategy="onethird", minInstancesPerNode=3)
    else:  # 与 run_salary_experiment 同超参
        est = GBTRegressor(labelCol="label", weightCol="w", maxIter=80, maxDepth=5, stepSize=0.1, subsamplingRate=0.8,
                           seed=42)
    pred = est.fit(s_tr).transform(s_te).select("rid", "prediction").toPandas().sort_values("rid")
    return pred["prediction"].values


def lgb_fit_predict(Xtr, ytr, Xte, wtr=None):
    import lightgbm as lgb
    m = lgb.LGBMRegressor(n_estimators=600, learning_rate=0.03, num_leaves=31, min_child_samples=20, subsample=0.8,
                          subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=42, verbose=-1)
    m.fit(Xtr.values, np.asarray(ytr, float), sample_weight=wtr)
    return m.predict(Xte.values)


MODELS = ("SparkRF", "SparkGBT", "LightGBM")


def fit_predict(spark, kind, Xtr, ytr, Xte, wtr=None):
    if kind == "LightGBM":
        return lgb_fit_predict(Xtr, ytr, Xte, wtr)
    return spark_fit_predict(spark, kind, Xtr, ytr, Xte, wtr)


def prod_skillfix(spark, rows, preds, record, spark_predict, golden, step):
    """生产管线原样 + 技能按空格也切分（BOSS 技能是空格分隔，原实现整串当一个词，基本进不了词表）。"""
    from pyspark.sql import functions as F
    from app.spark import salary_model as prod
    prod._excluded_ids = lambda: []
    prod.SKILL_SPLIT_PATTERN = r"[、;/|\s]+"  # 即生产新口径
    full = prod._load_real(spark)
    excluded = set(load_real("boss_2023")["row_id"]) - set(split_core()[0]["row_id"])
    train = full.filter(F.col("row_id").isNull() | ~F.col("row_id").isin(list(excluded)))
    gold = full.filter(F.col("row_id").isin(list(golden["row_id"])))
    t0 = time.time()
    model = prod._pipeline().fit(train)
    record(rows, preds, step, "prod_pooled_real+技能切分修复", "core+51job", "SparkRF(prod)", golden,
           spark_predict(model, gold, golden), train.count(), {"fit_s": round(time.time() - t0, 1)})


def cv_lgb(groups, df, emb, ext, folds=5):
    from sklearn.model_selection import KFold
    from di_common import metrics
    r2s = []
    for tr_idx, va_idx in KFold(folds, shuffle=True, random_state=42).split(df):
        tr, va = df.iloc[tr_idx], df.iloc[va_idx]
        etr, eva = (emb[tr_idx], emb[va_idx]) if "emb" in groups else (None, None)
        fz = Featurizer(groups).fit(tr, ext, etr)
        p = lgb_fit_predict(fz.transform(tr, ext, etr), tr[TARGET], fz.transform(va, ext, eva))
        r2s.append(metrics(va[TARGET], p)["r2"])
    return {"r2_mean": float(np.mean(r2s)), "r2_std": float(np.std(r2s, ddof=1))}


def run(spark, step, rows, preds, record, spark_predict, to_spark):
    core, golden, stats = split_core()
    print("切分:", stats, "抽取后端:", os.getenv("EXTRACT_BACKEND", "rule"))
    ext = extractor(pd.concat([core, golden]))
    need_emb = True
    emb_all = embed(pd.concat([core, golden]), "boss_2023") if need_emb else None
    e_core, e_gold = emb_all[: len(core)], emb_all[len(core):]

    def eval_set(variant, groups, train_df, e_train, ext_map, weights=None, models=MODELS, target="mid"):
        fz = Featurizer(groups).fit(train_df, ext_map, e_train if "emb" in groups else None)
        Xtr = fz.transform(train_df, ext_map, e_train if "emb" in groups else None)
        Xte = fz.transform(golden, ext_map, e_gold if "emb" in groups else None)
        for kind in models:
            t0 = time.time()
            if target == "mid":
                p = fit_predict(spark, kind, Xtr, train_df[TARGET], Xte, weights)
            elif target == "log":
                p = np.expm1(fit_predict(spark, kind, Xtr, np.log1p(train_df[TARGET]), Xte, weights))
            else:  # min/max 分别建模，中位 = 两者平均
                pmin = fit_predict(spark, kind, Xtr, train_df["salary_min"], Xte, weights)
                pmax = fit_predict(spark, kind, Xtr, train_df["salary_max"], Xte, weights)
                p = (pmin + pmax) / 2
                from di_common import metrics
                extra_mm = {"min_mae": round(metrics(golden["salary_min"], pmin)["mae"], 1),
                            "max_mae": round(metrics(golden["salary_max"], pmax)["mae"], 1)}
            extra = {"n_features": Xtr.shape[1], "target": target, "fit_s": round(time.time() - t0, 1)}
            if target == "minmax":
                extra.update(extra_mm)
            record(rows, preds, step, variant, train_df["data_source"].iloc[0] if weights is None else "mixed", kind,
                   golden, p, len(train_df), extra)
        return Xtr.shape[1]

    # 特征组合按训练集 5 折 CV（LightGBM，R²）选择，黄金集不参与选型
    sel_path = HERE / "results" / "feature_selection_cv.json"
    if step == "step1" or not sel_path.exists():
        cv = {name: cv_lgb(groups, core, e_core, ext) for name, groups in LADDER}
        best_name = max(cv, key=lambda k: cv[k]["r2_mean"])
        import json
        sel_path.write_text(json.dumps({"cv": cv, "selected": best_name}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  训练集 5 折 CV 选型:", {k: round(v["r2_mean"], 4) for k, v in cv.items()}, "→", best_name, flush=True)
    import json
    best_name = json.loads(sel_path.read_text(encoding="utf-8"))["selected"]
    best_groups = dict(LADDER)[best_name]
    if step == "step1":
        prod_skillfix(spark, rows, preds, record, spark_predict, golden, step)
        for name, groups in LADDER:
            eval_set(name, groups, core, e_core, ext)
        eval_set(f"{best_name.split()[0]}(CV选定) 目标=log(月薪)", best_groups, core, e_core, ext, target="log")
        eval_set(f"{best_name.split()[0]}(CV选定) 目标=min/max 分别预测", best_groups, core, e_core, ext, target="minmax")
        return golden

    # ---- step2：外部扩充 ----
    j51 = load_real("job51_2018")
    ext51 = extract_frame(j51, "rule")
    e51 = embed(j51, "job51_2018")
    ats = HERE / "ats_salary_rows.csv"
    ats_rows = pd.read_csv(ats) if ats.exists() else pd.DataFrame()
    print(f"  外部扩充：51job 2018 IT {len(j51)} 条；ATS 带真实薪资 {len(ats_rows)} 条")
    g_year = best_groups + ["year"]
    tag = best_name.split()[0]
    eval_set(f"S2a core only ({tag}+year)", g_year, core, e_core, {**ext})
    mix = pd.concat([core, j51], ignore_index=True)
    e_mix = np.vstack([e_core, e51])
    ext_mix = {**ext, **ext51}
    eval_set("S2b core+51job(权重1)", g_year, mix, e_mix, ext_mix,
             weights=np.r_[np.ones(len(core)), np.ones(len(j51))])
    eval_set("S2c core+51job(权重0.3)", g_year, mix, e_mix, ext_mix,
             weights=np.r_[np.ones(len(core)), np.full(len(j51), 0.3)])
    return golden
