"""数据改善实验公共工具：数据加载、黄金测试集、泄漏防护、评测指标。

黄金测试集（golden_test_ids.csv）只用于评测：
  * 不参与任何训练、特征拟合（编码器/PCA/词表）、插补或外部数据混入；
  * 训练集还会排除与黄金行「同公司+同标题」的所有行（防近重复泄漏），见 train_pool()。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parent
REAL = REPO / "data" / "real_salary"
GOLDEN_IDS = HERE / "golden_test_ids.csv"
RESULTS = HERE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
if str(EXP) not in sys.path:
    sys.path.insert(0, str(EXP))

EDU_YEARS = {0: 16.0, 1: 15.0, 2: 16.0, 3: 19.0, 4: 22.0}


def load_real(name: str) -> pd.DataFrame:
    df = pd.read_csv(REAL / f"{name}.csv", keep_default_na=False, na_values=[""])
    for col in ("title", "skills", "company_name", "company_type", "welfare", "industry", "tokens"):
        df[col] = df[col].fillna("").astype(str)
    df["data_year"] = 2023.0 if name.startswith("boss") else 2018.0
    df["edu_years"] = df["education"].map(EDU_YEARS).astype(float)
    df["company_size"] = df["company_size"].fillna(0).astype(float)
    df["salary_mid"] = (df["salary_min"] + df["salary_max"]) / 2.0
    df["data_source"] = "core_boss2023" if name.startswith("boss") else "ext_51job2018"
    return df


def golden_ids() -> list[str]:
    return pd.read_csv(GOLDEN_IDS)["row_id"].astype(str).tolist()


def _group_key(df: pd.DataFrame) -> pd.Series:
    return df["company_name"].str.strip() + "||" + df["title"].str.strip()


def split_core() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """返回 (core 训练池, 黄金测试集, 统计)。core = BOSS 2023 真实月薪。"""
    boss = load_real("boss_2023")
    gid = set(golden_ids())
    golden = boss[boss["row_id"].isin(gid)].copy()
    assert len(golden) == len(gid), "黄金集 id 与数据文件不一致，请勿重新生成 boss_2023.csv 的 row_id"
    rest = boss[~boss["row_id"].isin(gid)]
    gkeys = set(_group_key(golden))
    leak = _group_key(rest).isin(gkeys) & (rest["company_name"].str.len() > 0)
    train = rest[~leak].copy()
    stats = {"boss_rows": int(len(boss)), "golden": int(len(golden)), "excluded_same_company_title": int(leak.sum()),
             "core_train": int(len(train))}
    return train, golden, stats


def metrics(y_true, y_pred) -> dict:
    y, p = np.asarray(y_true, float), np.asarray(y_pred, float)
    err = p - y
    ss_res = float((err ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return {"mae": float(np.abs(err).mean()), "rmse": float(np.sqrt((err ** 2).mean())), "r2": 1.0 - ss_res / ss_tot}


def bootstrap_ci(y_true, y_pred, n: int = 1000, seed: int = 7) -> dict:
    y, p = np.asarray(y_true, float), np.asarray(y_pred, float)
    rng = np.random.default_rng(seed)
    r2s, maes = [], []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        m = metrics(y[idx], p[idx])
        r2s.append(m["r2"])
        maes.append(m["mae"])
    return {"r2_ci": [float(np.percentile(r2s, 2.5)), float(np.percentile(r2s, 97.5))],
            "mae_ci": [float(np.percentile(maes, 2.5)), float(np.percentile(maes, 97.5))]}
