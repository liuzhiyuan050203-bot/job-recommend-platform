"""压测用的放大数据生成器（不写数据库）。

由 `data/generate_demo_data.py --scale N` 调用，也可直接运行：
    .venv/bin/python data/scale_generator.py --scale 100000 [--events-per-job 10] [--out experiments/data/scale]

职位：对 data/raw/jobs_raw.csv（演示生成器写出的 5000 行"爬虫原始 CSV"，含 K/元每月/万每年/元每天/面议/
异常值、城市别名、多种日期格式）做有放回重采样，并扰动薪资数值、给公司名加编号，使
(title, company, city) 基本唯一；再混入约 3% 完全重复行，保持与生产清洗任务相同的输入格式和脏数据比例。
行为：用户数 max(200, N/20)，行为条数 events_per_job × N；职位热度服从 Zipf(1.1)，用户活跃度服从对数正态，
behavior_type 浏览:收藏:投递 = 85:11:4，时间均匀落在 2026-05-01 ~ 2026-10-31。
输出 jobs_<N>.csv、events_<N>.parquet。数据只用于计时，不代表真实分布。
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEED_CSV = ROOT / "data" / "raw" / "jobs_raw.csv"
DEFAULT_OUT = ROOT / "experiments" / "data" / "scale"
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _perturb_salary(texts: pd.Series, factors: np.ndarray) -> pd.Series:
    out = []
    for text, f in zip(texts.tolist(), factors.tolist()):
        if not isinstance(text, str) or "面议" in text or text.startswith("-"):
            out.append(text)
            continue
        out.append(_NUM.sub(lambda m: f"{float(m.group()) * f:.1f}".rstrip("0").rstrip("."), text, count=2))
    return pd.Series(out, index=texts.index)


def generate_scaled(n_jobs: int, events_per_job: int = 10, out: Path = DEFAULT_OUT, seed: int = 2026) -> dict:
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed + n_jobs)
    base = pd.read_csv(SEED_CSV, dtype=str, keep_default_na=False)
    n_unique = int(round(n_jobs * 0.97))
    idx = rng.integers(0, len(base), size=n_unique)
    jobs = base.iloc[idx].reset_index(drop=True)
    jobs["company"] = jobs["company"] + "-" + pd.Series(np.arange(n_unique) // 7).astype(str)
    jobs["salary_text"] = _perturb_salary(jobs["salary_text"], rng.uniform(0.85, 1.15, size=n_unique).round(2))
    dup = jobs.iloc[rng.integers(0, n_unique, size=n_jobs - n_unique)]
    jobs = pd.concat([jobs, dup], ignore_index=True).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    jobs_path = out / f"jobs_{n_jobs}.csv"
    jobs.to_csv(jobs_path, index=False)

    n_users = max(200, n_jobs // 20)
    n_events = events_per_job * n_jobs
    ranks = rng.permutation(n_jobs)
    pop = 1.0 / np.power(np.arange(1, n_jobs + 1), 1.1)
    pop /= pop.sum()
    item = ranks[rng.choice(n_jobs, size=n_events, p=pop)]
    act = rng.lognormal(0.0, 1.0, size=n_users)
    act /= act.sum()
    user = rng.choice(n_users, size=n_events, p=act)
    btype = rng.choice(np.array([1, 2, 3], dtype=np.int8), size=n_events, p=[0.85, 0.11, 0.04])
    weight = np.select([btype == 1, btype == 2], [1, 3], 5).astype(np.int8)
    t0 = 1777564800  # 2026-05-01 00:00 +08
    ts = rng.integers(t0, t0 + 184 * 86400, size=n_events)
    events = pd.DataFrame({"user_id": user.astype(np.int32), "position_id": item.astype(np.int32),
                           "behavior_type": btype, "weight": weight, "ts": ts.astype(np.int64)})
    events_path = out / f"events_{n_jobs}.parquet"
    events.to_parquet(events_path, index=False)
    info = {
        "n_jobs": n_jobs, "n_unique_jobs": n_unique, "n_users": n_users, "n_events": n_events,
        "jobs_csv": str(jobs_path), "jobs_csv_mb": round(jobs_path.stat().st_size / 2**20, 1),
        "events_parquet": str(events_path), "events_parquet_mb": round(events_path.stat().st_size / 2**20, 1),
        "seconds": round(time.perf_counter() - started, 1),
    }
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=int, required=True)
    ap.add_argument("--events-per-job", type=int, default=10)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    print(generate_scaled(args.scale, args.events_per_job, args.out))


if __name__ == "__main__":
    main()
