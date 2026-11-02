"""推荐算法消融实验（一条命令复现）。

    .venv/bin/python experiments/recommend/run_recommend_ablation.py [--seeds 5] [--quick]

数据：库里 user_behavior_log / stu_profile / stu_skill / job_position（由 data/generate_demo_data.py
生成的合成行为）。复用 numpy_reference.py（生产 Spark 实现的 numpy 参考版，数值等价性见
verify_spark_cf.py）的加载、内容打分、用户余弦、ALS、融合与评估函数。

评估协议
- 正样本：收藏/投递过的 (学生, 职位)。每个学生留出 20% 正样本做测试（向下取整，至少 1 个，
  与生产 holdout_count 相同）。训练期出现过的职位在排序时屏蔽。
- random 协议：按随机种子随机留出，重复 --seeds 次，报告 mean±std；
  time 协议：生产所用的按时间留出最后 20%（确定性，单次）。
- 融合权重 alpha 的选择不看测试集：在训练集里再按同样方式留出 20% 作验证集选 alpha，
  再用全部训练数据重算分数在测试集上报告（"Hybrid(val-α)"）。alpha 扫描曲线 0..1 步长 0.1
  直接画测试集指标，仅用于展示敏感性。
- 消融：45 天时间衰减 开/关；学历惩罚 0.35 开/关（=1.0）；求职方向归一 + 冲突降权 开/关
  （关 = 方向只看字面相等，P1-1 修复前的口径）。另报 FarDir@10：Top-10 中与期望方向冲突的职位占比。
- 冷启动：随机抽 20% 学生当"新学生"：full = 删掉其全部行为（没有协同信号，融合走 0.75 内容 + 0.25
  热门的兜底）；fewshot3 = 只保留其随机 3 条行为。真值为这些学生其余的收藏/投递。
  （原生成器每人 8–14 个收藏，天然不存在稀疏学生，所以用模拟。）
- 行为偏差对照（--variant pop_noise）：另行在内存里生成一份"弱偏好"行为：每次交互 25% 按内容偏好、
  50% 按 Zipf 热度、25% 均匀随机，检验算法排序是否依赖原生成器的"方向+城市"假设。
输出：experiments/results/recommend_*.json/csv，experiments/figures/recommend_*.png。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import FIGURES, RESULTS, env_info, save_json, setup_matplotlib  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 生产推荐已改为 Spark DataFrame 实现；消融实验需要上百组网格，仍用等价的 numpy 参考实现
import numpy_reference as R  # noqa: E402

E = R
from app.spark.session import get_spark  # noqa: E402

KS = (5, 10, 20)
NO_DIR = "nodir"
ALS_TUNING: list[dict] = []
SWEEP = [round(x * 0.1, 1) for x in range(11)]


# ---------------------------------------------------------------- 划分
def positive_pairs(events: pd.DataFrame) -> pd.DataFrame:
    pos = events[events["behavior_type"].isin([2, 3])]
    return pos.groupby(["user_id", "position_id"], as_index=False)["ts"].max()


def split_random(events: pd.DataFrame, seed: int) -> set[tuple[int, int]]:
    rng = np.random.default_rng(seed)
    held = set()
    for user_id, group in positive_pairs(events).groupby("user_id"):
        n_test = E.holdout_count(len(group))
        if n_test <= 0:
            continue
        items = group["position_id"].to_numpy()
        for pid in rng.choice(items, size=n_test, replace=False):
            held.add((int(user_id), int(pid)))
    return held


# ---------------------------------------------------------------- 打分
class Ctx:
    """一次实验需要的静态数据：用户/职位索引、内容矩阵、可推荐掩码。"""

    def __init__(self, frames, events):
        jobs, profiles = frames["jobs"], frames["profiles"]
        self.frames = frames
        self.events = events
        self.eligible_ids = set(int(i) for i in jobs.loc[jobs["eligible"], "position_id"])
        self.item_ids = sorted(int(i) for i in jobs["position_id"])
        users = set(int(i) for i in profiles["user_id"]) | set(int(i) for i in events["user_id"].unique())
        self.user_ids = sorted(users)
        self.user_index = {u: i for i, u in enumerate(self.user_ids)}
        self.item_index = {p: i for i, p in enumerate(self.item_ids)}
        self.shape = (len(self.user_ids), len(self.item_ids))
        self.eligible_row = np.array([p in self.eligible_ids for p in self.item_ids])
        self.catalog = len(self.eligible_ids)
        self.ref_ts = float(events["ts"].max())
        self.content = {}
        for pen in (R.EDU_PENALTY, 1.0):
            self.content[pen], aux = R._content_matrix(
                profiles, jobs, frames["skills"], frames["job_tags"], self.user_index, self.item_index, edu_penalty=pen
            )
            self.dir_factor = aux["dir_factor"]
        # 方向加权消融：方向只看字面相等、无冲突系数（P1-1 修复前的口径）
        self.content[NO_DIR], _ = R._content_matrix(
            profiles, jobs, frames["skills"], frames["job_tags"], self.user_index, self.item_index,
            edu_penalty=R.EDU_PENALTY, direction_weighting=False,
        )
        self.far = self.dir_factor < 0.75

    def ratings(self, train_events, half_life):
        grouped, pop = E.aggregate_frame(train_events, self.ref_ts, half_life_days=half_life)
        mat = E.fill_matrix(grouped, self.user_index, self.item_index, self.shape)
        return mat, E.popularity_scores(pop, self.item_index, self.shape[1])

    def truth(self, held):
        return R._truth(held, self.eligible_ids, self.user_index)

    def metrics(self, scores, banned, truth, users=None):
        if users is not None:
            truth = {u: v for u, v in truth.items() if u in users}
        rows = R._rank_metrics(scores, banned, self.user_ids, self.item_ids, truth, self.catalog)
        out = {}
        for row in rows:
            k = row["k"]
            out[f"P@{k}"] = row["precision"]
            out[f"R@{k}"] = row["recall"]
            out[f"NDCG@{k}"] = row["ndcg"]
            out[f"Cov@{k}"] = row["coverage"]
        out["users"] = rows[0]["userCount"] if rows else 0
        # 跨方向率：真值学生 Top-10 里与期望方向冲突的职位占比（越低越对口）
        idx = [self.user_index[u] for u in truth if u in self.user_index]
        out["FarDir@10"] = float("nan")
        if idx and scores is not None:
            top = R.top_indices(scores[idx], banned[idx], 10)
            valid = top >= 0
            far = np.take_along_axis(self.far[idx], np.where(valid, top, 0), axis=1) & valid
            out["FarDir@10"] = float(far.sum() / max(1, valid.sum()))
        return out


def score_all(ctx: Ctx, spark, train_events, half_life, seed, with_als=True, als_params=None):
    ratings, pop = ctx.ratings(train_events, half_life)
    banned = (ratings > 0) | ~ctx.eligible_row
    cos = E.cosine_predict(ratings)
    als = None
    if with_als:
        p = als_params or {}
        als = als_predict(spark, ratings, ctx, seed, **p)
    activity = (ratings > 0).sum(axis=1).astype(np.float64)
    return {
        "ratings": ratings,
        "pop": pop,
        "banned": banned,
        "cos_mm": E.minmax_rows(cos, banned),
        "als_mm": E.minmax_rows(als, banned) if als is not None else None,
        "activity": activity,
        "pop_mat": np.broadcast_to(pop, ratings.shape).copy(),
        "dir_factor": ctx.dir_factor,
    }


def als_predict(spark, ratings, ctx, seed, rank=None, reg=None, alpha=None, iters=None):
    rows, cols = np.nonzero(ratings > 0)
    from pyspark.ml.recommendation import ALS

    frame = spark.createDataFrame(
        [(int(r), int(c), float(ratings[r, c])) for r, c in zip(rows, cols)], ["u", "i", "rating"]
    )
    model = ALS(
        userCol="u", itemCol="i", ratingCol="rating", implicitPrefs=True, rank=rank or R.ALS_RANK,
        maxIter=iters or R.ALS_ITER, regParam=R.ALS_REG if reg is None else reg,
        alpha=alpha or R.ALS_ALPHA, coldStartStrategy="drop", seed=int(seed),
    ).fit(frame)
    U = np.zeros((ctx.shape[0], rank or R.ALS_RANK))
    V = np.zeros((ctx.shape[1], rank or R.ALS_RANK))
    for rec in model.userFactors.collect():
        U[rec["id"]] = rec["features"]
    for rec in model.itemFactors.collect():
        V[rec["id"]] = rec["features"]
    return U @ V.T


def fuse(s, content, cf_key, alpha, adaptive=False, direction=True):
    factor = s["dir_factor"] if direction else None
    return E.fuse_scores(s[cf_key], content, s["pop"], s["activity"], alpha, "linear", adaptive, factor)


def pick_alpha_on_val(ctx, spark, train_events, half_life, content, seed, cf_key, als_params=None, direction=True):
    """在训练集内部再留出 20% 正样本选 alpha（不触碰测试集）。"""
    val_held = split_random(train_events, seed + 1000)
    inner = E.drop_pairs(train_events, val_held)
    s = score_all(ctx, spark, inner, half_life, seed, with_als=(cf_key == "als_mm"), als_params=als_params)
    truth = ctx.truth(val_held)
    best, best_score = 0.5, -1
    for alpha in SWEEP:
        m = ctx.metrics(fuse(s, content, cf_key, alpha, direction=direction), s["banned"], truth)
        if m["NDCG@10"] > best_score + 1e-12:
            best, best_score = alpha, m["NDCG@10"]
    return best


ALS_GRID = [(r, reg, a) for r in (8, 32, 64) for reg in (0.1, 1.0, 10.0) for a in (5.0, 20.0, 40.0)]


def tune_als_on_val(ctx, spark, train_events, half_life, seed):
    """在训练集内部验证集上网格搜索 ALS（rank × reg × alpha，maxIter=10），避免"ALS 没调参"的质疑。"""
    val_held = split_random(train_events, seed + 1000)
    inner = E.drop_pairs(train_events, val_held)
    ratings, _ = ctx.ratings(inner, half_life)
    banned = (ratings > 0) | ~ctx.eligible_row
    truth = ctx.truth(val_held)
    best, best_score, grid = None, -1.0, []
    for rank, reg, alpha in ALS_GRID:
        sc = als_predict(spark, ratings, ctx, seed, rank=rank, reg=reg, alpha=alpha, iters=10)
        n = ctx.metrics(sc, banned, truth)["NDCG@10"]
        grid.append({"rank": rank, "reg": reg, "alpha": alpha, "val_ndcg10": n})
        if n > best_score:
            best, best_score = (rank, reg, alpha), n
    return best, grid


# ---------------------------------------------------------------- 弱偏好行为
def pop_noise_events(ctx: Ctx, base_events: pd.DataFrame, seed: int) -> pd.DataFrame:
    """与原数据同样的每人行为条数，但每次交互 25% 内容偏好 / 50% Zipf 热度 / 25% 随机。"""
    rng = np.random.default_rng(seed)
    elig = np.flatnonzero(ctx.eligible_row)
    zipf = 1.0 / np.arange(1, len(elig) + 1)
    hot_order = rng.permutation(elig)
    p_hot = zipf / zipf.sum()
    content = ctx.content[R.EDU_PENALTY]
    t0, t1 = float(base_events["ts"].min()), float(base_events["ts"].max())
    counts = base_events.groupby(["user_id", "behavior_type"]).size()
    rows = []
    for (user_id, btype), n in counts.items():
        u = ctx.user_index[int(user_id)]
        pref = content[u, elig]
        top = elig[np.argsort(-pref)[:60]]
        for _ in range(int(n)):
            roll = rng.random()
            if roll < 0.25:
                col = top[rng.integers(len(top))]
            elif roll < 0.75:
                col = hot_order[rng.choice(len(elig), p=p_hot)]
            else:
                col = elig[rng.integers(len(elig))]
            rows.append((int(user_id), int(btype), ctx.item_ids[int(col)], {1: 1, 2: 3, 3: 5}[int(btype)], rng.uniform(t0, t1)))
    return pd.DataFrame(rows, columns=["user_id", "behavior_type", "position_id", "weight", "ts"])


# ---------------------------------------------------------------- 主流程
def run_split(ctx, spark, events, held, seed, label, records, sweep_rows, cold_rows):
    train = E.drop_pairs(events, held)
    truth = ctx.truth(held)
    pen = R.EDU_PENALTY
    for decay_name, half_life in (("decay45", E.HALF_LIFE_DAYS), ("nodecay", None)):
        s = score_all(ctx, spark, train, half_life, seed, with_als=True)
        b = s["banned"]

        def add(method, scores, extra=None, users=None, subset="all"):
            m = ctx.metrics(scores, b, truth, users)
            rec = {"protocol": label, "seed": seed, "decay": decay_name, "subset": subset, "method": method, **m}
            if extra:
                rec.update(extra)
            records.append(rec)

        add("Popularity", s["pop_mat"])
        add("UserCF(cosine)", s["cos_mm"])
        add("ALS", s["als_mm"])
        add("Content", ctx.content[pen])
        add("Content(no edu penalty)", ctx.content[1.0])
        a_cos = pick_alpha_on_val(ctx, spark, train, half_life, ctx.content[pen], seed, "cos_mm")
        add("Hybrid(cosine, val-α)", fuse(s, ctx.content[pen], "cos_mm", a_cos), {"alpha": a_cos})
        add("Hybrid(cosine, val-α, no edu penalty)", fuse(s, ctx.content[1.0], "cos_mm", a_cos), {"alpha": a_cos})
        add("Content(no direction weighting)", ctx.content[NO_DIR])
        a_nd = pick_alpha_on_val(ctx, spark, train, half_life, ctx.content[NO_DIR], seed, "cos_mm", direction=False)
        add("Hybrid(cosine, val-α, no direction weighting)", fuse(s, ctx.content[NO_DIR], "cos_mm", a_nd, direction=False), {"alpha": a_nd})
        if decay_name == "decay45":
            (rk, rg, al), grid = tune_als_on_val(ctx, spark, train, half_life, seed)
            ALS_TUNING.append({"protocol": label, "seed": seed, "best": [rk, rg, al], "grid": grid})
            tuned = {"rank": rk, "reg": rg, "alpha": al, "iters": 10}
        als_t = als_predict(spark, s["ratings"], ctx, seed, **tuned)
        add("ALS(val-tuned)", als_t, {"als_rank": tuned["rank"], "als_reg": tuned["reg"], "als_alpha": tuned["alpha"]})
        s["als_tuned_mm"] = E.minmax_rows(als_t, b)
        a_als = pick_alpha_on_val(ctx, spark, train, half_life, ctx.content[pen], seed, "als_mm", als_params=tuned)
        add("Hybrid(ALS-tuned, val-α)", fuse(s, ctx.content[pen], "als_tuned_mm", a_als), {"alpha": a_als})
        # alpha 扫描（测试集，仅展示）
        for cf_key, cf_name in (("cos_mm", "cosine"), ("als_tuned_mm", "ALS(tuned)")):
            for alpha in SWEEP:
                m = ctx.metrics(fuse(s, ctx.content[pen], cf_key, alpha), b, truth)
                sweep_rows.append({"protocol": label, "seed": seed, "decay": decay_name, "cf": cf_name, "alpha": alpha, **m})

    # 冷启动：随机抽 20% 有正样本的学生作为"新学生"。full = 删除其全部行为；
    # fewshot3 = 只保留其随机 3 条行为（模拟刚注册、浏览了几次）。真值为其余正样本。
    rng = np.random.default_rng(seed + 7)
    pos_all = positive_pairs(events)[["user_id", "position_id"]]
    users_with_pos = sorted(pos_all["user_id"].astype(int).unique())
    cold = set(int(u) for u in rng.choice(users_with_pos, size=max(1, len(users_with_pos) // 5), replace=False))
    warm = events[~events["user_id"].isin(cold)]
    warm_train = E.drop_pairs(warm, {(u, p) for u, p in held if u not in cold})
    cold_events = events[events["user_id"].isin(cold)]
    keep_idx = []
    for _, g in cold_events.groupby("user_id"):
        keep_idx.extend(rng.choice(g.index.to_numpy(), size=min(3, len(g)), replace=False).tolist())
    few = cold_events.loc[keep_idx]
    for scenario, extra_events in (("full", cold_events.iloc[0:0]), ("fewshot3", few)):
        train = pd.concat([warm_train, extra_events], ignore_index=True)
        kept = set(zip(extra_events["user_id"].astype(int), extra_events["position_id"].astype(int)))
        truth_pairs = {(int(u), int(p)) for u, p in pos_all.itertuples(index=False) if int(u) in cold and (int(u), int(p)) not in kept}
        s = score_all(ctx, spark, train, E.HALF_LIFE_DAYS, seed, with_als=True)
        truth = ctx.truth(truth_pairs)
        b = s["banned"]
        cands = (
            ("Popularity", s["pop_mat"]),
            ("UserCF(cosine)", s["cos_mm"]),
            ("ALS", s["als_mm"]),
            ("Content", ctx.content[pen]),
            ("Content(no edu penalty)", ctx.content[1.0]),
            ("Content(no direction weighting)", ctx.content[NO_DIR]),
            ("Hybrid(α=0.5, linear)", fuse(s, ctx.content[pen], "cos_mm", 0.5)),
            ("Hybrid(α=0.5, adaptive)", fuse(s, ctx.content[pen], "cos_mm", 0.5, adaptive=True)),
        )
        for name, sc in cands:
            m = ctx.metrics(sc, b, truth)
            cold_rows.append({"protocol": label, "seed": seed, "scenario": scenario, "method": name, **m})


def summarize(df, keys, metrics):
    agg = df.groupby(keys)[metrics].agg(["mean", "std", "count"])
    agg.columns = [f"{a}_{b}" for a, b in agg.columns]
    return agg.reset_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--variant", choices=["original", "pop_noise", "both"], default="both")
    args = ap.parse_args()
    started = time.time()
    spark = get_spark()
    frames = R._load(spark)
    base_events = frames["events"]
    base_events = base_events[base_events["position_id"].isin(set(frames["jobs"]["position_id"].astype(int)))].copy()
    variants = ["original", "pop_noise"] if args.variant == "both" else [args.variant]
    metric_cols = [f"{m}@{k}" for k in KS for m in ("P", "R", "NDCG", "Cov")] + ["FarDir@10"]
    all_out = {"env": env_info(), "seeds": list(range(1, args.seeds + 1)), "variants": {}}
    for variant in variants:
        ctx = Ctx(frames, base_events)
        events = base_events if variant == "original" else pop_noise_events(ctx, base_events, 2026)
        if variant != "original":
            ctx = Ctx(frames, events)
        records, sweep_rows, cold_rows = [], [], []
        ALS_TUNING.clear()
        stats = {
            "users": ctx.shape[0], "items": ctx.shape[1], "eligible": ctx.catalog, "events": int(len(events)),
            "positive_pairs": int(len(positive_pairs(events))),
            "density": float(len(events.groupby(["user_id", "position_id"])) / (ctx.shape[0] * ctx.shape[1])),
        }
        print(f"[{variant}] {stats}", flush=True)
        for seed in range(1, args.seeds + 1):
            t = time.time()
            run_split(ctx, spark, events, split_random(events, seed), seed, "random", records, sweep_rows, cold_rows)
            print(f"  seed {seed} done ({time.time() - t:.0f}s)", flush=True)
        if variant == "original":
            run_split(ctx, spark, events, E.split_holdout(events), 0, "time", records, sweep_rows, cold_rows)
            print("  time split done", flush=True)
        rec = pd.DataFrame(records)
        sw = pd.DataFrame(sweep_rows)
        cr = pd.DataFrame(cold_rows)
        rec.to_csv(RESULTS / f"recommend_{variant}_raw.csv", index=False)
        sw.to_csv(RESULTS / f"recommend_{variant}_alpha_sweep_raw.csv", index=False)
        cr.to_csv(RESULTS / f"recommend_{variant}_coldstart_raw.csv", index=False)
        summ = summarize(rec, ["protocol", "decay", "subset", "method"], metric_cols)
        summ.to_csv(RESULTS / f"recommend_{variant}_summary.csv", index=False)
        sw_summ = summarize(sw, ["protocol", "decay", "cf", "alpha"], metric_cols)
        sw_summ.to_csv(RESULTS / f"recommend_{variant}_alpha_sweep.csv", index=False)
        cr_summ = summarize(cr, ["protocol", "scenario", "method"], metric_cols)
        cr_summ.to_csv(RESULTS / f"recommend_{variant}_coldstart.csv", index=False)
        alphas = rec.dropna(subset=["alpha"]).groupby(["protocol", "decay", "method"])["alpha"].apply(list).to_dict() if "alpha" in rec else {}
        all_out["variants"][variant] = {
            "stats": stats,
            "summary": summ.to_dict(orient="records"),
            "coldstart": cr_summ.to_dict(orient="records"),
            "val_alphas": {" | ".join(k): v for k, v in alphas.items()},
            "als_tuning": list(ALS_TUNING),
        }
        plot(variant, summ, sw_summ)
    all_out["elapsed_s"] = round(time.time() - started, 1)
    save_json("recommend_ablation.json", all_out)
    print(f"done in {all_out['elapsed_s']}s")


def plot(variant, summ, sw):
    plt = setup_matplotlib()
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    data = sw[(sw["protocol"] == "random") & (sw["decay"] == "decay45")]
    for ax, metric in zip(axes, ("P", "R", "NDCG")):
        for k, style in zip(KS, ("-", "--", ":")):
            for cf, color in (("cosine", "tab:blue"), ("ALS(tuned)", "tab:orange")):
                d = data[data["cf"] == cf].sort_values("alpha")
                ax.errorbar(d["alpha"], d[f"{metric}@{k}_mean"], yerr=d[f"{metric}@{k}_std"], linestyle=style,
                            color=color, marker="o", ms=3, capsize=2, label=f"{cf} K={k}")
        ax.set_xlabel("α（协同过滤权重；0=纯内容，1=纯协同）")
        ax.set_title(f"{metric}@K vs α")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=7, ncol=2)
    fig.suptitle(f"融合权重扫描（{variant} 行为，随机留出，mean±std）")
    fig.tight_layout()
    fig.savefig(FIGURES / f"recommend_alpha_sweep_{variant}.png", dpi=150)
    plt.close(fig)

    d = summ[(summ["protocol"] == "random") & (summ["decay"] == "decay45") & (summ["subset"] == "all")]
    order = ["Popularity", "UserCF(cosine)", "ALS", "ALS(val-tuned)", "Content", "Hybrid(cosine, val-α)", "Hybrid(ALS-tuned, val-α)"]
    d = d.set_index("method").reindex(order)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = np.arange(len(order))
    for j, k in enumerate(KS):
        ax.bar(x + (j - 1) * 0.27, d[f"NDCG@{k}_mean"], 0.27, yerr=d[f"NDCG@{k}_std"], capsize=2, label=f"NDCG@{k}")
    ax.set_xticks(x)
    ax.set_xticklabels(order, rotation=15, fontsize=8)
    ax.set_title(f"各方法 NDCG@K（{variant} 行为，随机留出 mean±std）")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES / f"recommend_methods_{variant}.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
