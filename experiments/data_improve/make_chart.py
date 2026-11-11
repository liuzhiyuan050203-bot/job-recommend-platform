#!/usr/bin/env python3
"""汇总 step0/1/2 指标并画消融折线图（黄金集 MAE 与 R²）。输出 figures/data_improve_ablation.png 与 results/summary.csv"""

from __future__ import annotations

import sys

import pandas as pd

from di_common import HERE, RESULTS

sys.path.insert(0, str(HERE.parent))
from common import setup_matplotlib  # noqa: E402

FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)


def main() -> int:
    s0 = pd.read_csv(RESULTS / "step0_metrics.csv")
    s1 = pd.read_csv(RESULTS / "step1_metrics.csv")
    s2 = pd.read_csv(RESULTS / "step2_metrics.csv")
    ladder = s1[s1["variant"].str.match(r"^F\d ")]
    ladder = ladder[~ladder["variant"].str.contains("目标")]
    s2m = s2[s2["variant"].str.startswith("S2")]
    path = pd.concat([ladder, s2m[~s2m["variant"].str.startswith("S2a")]], ignore_index=True)
    labels = list(dict.fromkeys(path["variant"]))
    short = [v.split(" ", 1)[1] if v.startswith("F") else v.split(" ", 1)[1] for v in labels]
    plt = setup_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, metric, title in ((axes[0], "mae", "黄金集 MAE（元/月，越低越好）"), (axes[1], "r2", "黄金集 R²（越高越好）")):
        for model, mk in (("SparkRF", "o"), ("SparkGBT", "s"), ("LightGBM", "^")):
            sub = path[path["model"] == model].set_index("variant").reindex(labels)
            ax.plot(range(len(labels)), sub[metric].values, marker=mk, label=model)
        prod0 = s0[s0["variant"] == "prod_pooled_real"][metric].iloc[0]
        prod1 = s1[s1["variant"].str.startswith("prod_pooled_real")][metric].iloc[0]
        ax.axhline(prod0, color="gray", ls="--", lw=1, label=f"step0 生产 RF 基线 ({prod0:.3g})")
        ax.axhline(prod1, color="gray", ls=":", lw=1, label=f"生产 RF + 技能切分修复 ({prod1:.3g})")
        ax.axvline(len(ladder["variant"].unique()) - 0.5, color="#bbb", lw=0.8)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(short, rotation=35, ha="right", fontsize=8)
        ax.set_title(title)
        ax.grid(alpha=0.3)
    axes[1].legend(fontsize=7, loc="lower right")
    fig.suptitle("薪资预测数据改善消融（固定黄金测试集 300 条 BOSS 2023 真实月薪；竖线右侧为外部扩充）", fontsize=10)
    fig.tight_layout()
    out = FIG / "data_improve_ablation.png"
    fig.savefig(out, dpi=150)
    pd.concat([s0, s1, s2], ignore_index=True).to_csv(RESULTS / "summary.csv", index=False)
    print("saved", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
