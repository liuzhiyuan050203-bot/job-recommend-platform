#!/usr/bin/env python3
"""确定性生成固定黄金测试集 golden_test_ids.csv（只需运行一次，结果入库；重跑结果完全一致）。

为什么不用平台自爬的 1758 条校招职位：它们的 salary_min/max 是按「方向×城市」公式估算的
（见 data/REAL_DATA.md），不是真实标签，拿来当测试集只会测出「模型记住了估算公式」（R²≈0.999）。
因此黄金集取自带真实月薪、时间最近、且有职位名/公司名/技能的 BOSS 直聘 2023（MIT 公开数据，
平台薪资模型的核心训练源）。

高质量筛选：方向≠其他；技能≥2 个；有公司名和福利；薪资区间上下限比 ≤2（标签噪声小）；
月薪均值在 [3000, 60000]。按技术方向分层抽样（每方向至少 5 条，按比例分配到 300），
每家公司最多 2 条，随机种子 20261111。
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from di_common import GOLDEN_IDS, HERE, load_real, split_core

SEED = 20261111
TARGET = 300


def main() -> int:
    df = load_real("boss_2023")
    q = df[(df["tech_direction"] != "其他")
           & (df["skills"].str.split().str.len() >= 2)
           & (df["company_name"].str.len() > 0)
           & (df["welfare"].str.len() > 0)
           & (df["salary_max"] / df["salary_min"] <= 2.0)
           & df["salary_mid"].between(3000, 60000)].copy()
    rng = np.random.default_rng(SEED)
    q = q.iloc[rng.permutation(len(q))]
    q = q.groupby("company_name", sort=False).head(2)
    counts = q["tech_direction"].value_counts()
    alloc = {d: max(5, int(round(TARGET * c / len(q)))) for d, c in counts.items()}
    alloc = {d: min(n, int(counts[d])) for d, n in alloc.items()}
    while sum(alloc.values()) > TARGET:
        big = max(alloc, key=alloc.get)
        alloc[big] -= 1
    picked = pd.concat([q[q["tech_direction"] == d].head(n) for d, n in sorted(alloc.items())])
    picked = picked.sort_values("row_id")
    picked[["row_id", "tech_direction", "city", "title", "company_name", "salary_min", "salary_max"]].to_csv(
        GOLDEN_IDS, index=False)
    print(f"高质量候选 {len(q)} 条（去重公司后）→ 黄金集 {len(picked)} 条 → {GOLDEN_IDS}")
    print(picked["tech_direction"].value_counts().to_dict())
    print("城市数", picked["city"].nunique(), "公司数", picked["company_name"].nunique(),
          "月薪均值", round(picked["salary_mid"].mean()), "标准差", round(picked["salary_mid"].std()))
    # 训练排除清单 = 黄金集 + 与黄金行同公司同标题的近重复行；生产 salary_model.py 也读取它
    train, golden, stats = split_core()
    boss = load_real("boss_2023")
    excl = boss[~boss["row_id"].isin(set(train["row_id"]))]["row_id"].sort_values()
    excl.to_frame().to_csv(HERE / "train_exclude_ids.csv", index=False)
    print("训练排除", len(excl), "条", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
