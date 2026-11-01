"""Pandas vs PySpark 扩展性压测（一条命令）：

    .venv/bin/python experiments/scale/run_scale_bench.py [--scales 10000 100000 500000 1000000] [--cores 1 2 4 8]

每个 (规模, 引擎/核数, 任务) 在独立子进程中运行，父进程每 0.1s 采样整个进程树（Python + JVM）的 RSS，
记录峰值内存。任务计时不含 SparkSession 启动（单独记为 startup_seconds）。
任务：clean = 生产清洗逻辑（去重 + classify_job 逐行解析 + 写 parquet）；
      aggregate = 省/市/方向三维薪资 count/mean/P25/P50/P75 + 月份×技能标签计数 + 省份汇总；
      als = 行为按 (用户, 职位) 汇总 log1p 后隐式 ALS（rank16, 10 iter）。Pandas 侧用 implicit 库。
本机 nproc=8，所以 local[8] 即 local[*]。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import FIGURES, RESULTS, env_info, save_json, setup_matplotlib  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "bin" / "python")
WORKER = str(Path(__file__).with_name("bench_worker.py"))
SCALE_DIR = REPO / "experiments" / "data" / "scale"
TMP = Path("/tmp/bishe-scale")


def tree_rss(proc: psutil.Process) -> int:
    total = 0
    try:
        procs = [proc] + proc.children(recursive=True)
    except psutil.Error:
        return 0
    for p in procs:
        try:
            total += p.memory_info().rss
        except psutil.Error:
            pass
    return total


def run_one(engine, cores, task, scale, timeout, driver_memory):
    cmd = [PY, WORKER, "--engine", engine, "--cores", str(cores), "--task", task, "--scale", str(scale),
           "--driver-memory", driver_memory]
    started = time.perf_counter()
    env = dict(os.environ, PYTHONPATH=str(REPO / "ai-service"), PYSPARK_PYTHON=PY, PYSPARK_DRIVER_PYTHON=PY)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(REPO), env=env)
    ps = psutil.Process(proc.pid)
    peak = [0]
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            peak[0] = max(peak[0], tree_rss(ps))
            time.sleep(0.1)

    th = threading.Thread(target=sample, daemon=True)
    th.start()
    try:
        out, err = proc.communicate(timeout=timeout)
        status = "ok" if proc.returncode == 0 else f"exit {proc.returncode}"
    except subprocess.TimeoutExpired:
        for p in ps.children(recursive=True):
            p.kill()
        proc.kill()
        out, err = proc.communicate()
        status = "timeout"
    stop.set()
    th.join()
    wall = time.perf_counter() - started
    rec = {"engine": engine, "cores": cores, "task": task, "scale": scale, "status": status,
           "process_wall_seconds": round(wall, 3), "peak_rss_mb": round(peak[0] / 2**20, 1)}
    if status == "ok":
        rec.update(json.loads(out.strip().splitlines()[-1]))
    else:
        tail = (err or "").strip().splitlines()[-8:]
        rec["error_tail"] = tail
        if any("OutOfMemory" in line or "Java heap" in line for line in (err or "").splitlines()):
            rec["status"] = "oom"
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scales", type=int, nargs="+", default=[10000, 100000, 500000, 1000000])
    ap.add_argument("--cores", type=int, nargs="+", default=[1, 2, 4, 8])
    ap.add_argument("--tasks", nargs="+", default=["clean", "aggregate", "als"])
    ap.add_argument("--reps-small", type=int, default=3, help="规模 <= 1e5 时重复次数")
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--driver-memory", default="3g")
    ap.add_argument("--merge", action="store_true", help="与已有 scale_bench.json 合并（只覆盖本次跑的条目）")
    args = ap.parse_args()
    out_path = RESULTS / "scale_bench.json"
    records = []
    if args.merge and out_path.exists():
        old = json.loads(out_path.read_text())
        records = [r for r in old["records"] if not (r["scale"] in args.scales and r["task"] in args.tasks)]
    gen_info = {}
    for scale in args.scales:
        jobs_csv = SCALE_DIR / f"jobs_{scale}.csv"
        if not jobs_csv.exists() or not (SCALE_DIR / f"events_{scale}.parquet").exists():
            res = subprocess.run([PY, str(REPO / "data" / "generate_demo_data.py"), "--scale", str(scale)],
                                 capture_output=True, text=True, check=True, cwd=str(REPO))
            print(res.stdout.strip(), flush=True)
        gen_info[scale] = {"jobs_csv_mb": round(jobs_csv.stat().st_size / 2**20, 1),
                           "events_parquet_mb": round((SCALE_DIR / f"events_{scale}.parquet").stat().st_size / 2**20, 1)}
        configs = [("pandas", 1)] + [("spark", c) for c in args.cores]
        reps = args.reps_small if scale <= 100000 else 1
        for task in args.tasks:
            if task == "aggregate" and not (SCALE_DIR / f"clean_{scale}.parquet").exists():
                r = run_one("pandas", 1, "clean", scale, args.timeout, args.driver_memory)
                shutil.copy(TMP / f"clean_pandas_{scale}.parquet", SCALE_DIR / f"clean_{scale}.parquet")
            task_configs = list(configs)
            if task == "als":
                task_configs = [("pandas", 1), ("pandas", 8)] + [("spark", c) for c in args.cores]
            for engine, cores in task_configs:
                for rep in range(reps):
                    rec = run_one(engine, cores, task, scale, args.timeout, args.driver_memory)
                    rec["rep"] = rep
                    records.append(rec)
                    print(f"{scale:>8} {task:9} {engine:6} cores={cores} rep={rep} {rec['status']:7} "
                          f"task={rec.get('task_seconds')}s startup={rec.get('startup_seconds')}s "
                          f"peak={rec['peak_rss_mb']}MB", flush=True)
                    out_path.write_text(json.dumps({"partial": True, "records": records}, ensure_ascii=False, indent=1))
                    if rec["status"] != "ok":
                        break
    save_json("scale_bench.json", {"env": env_info(), "records": records, "generated": gen_info})
    plot(records)


def plot(records):
    import pandas as pd

    plt = setup_matplotlib()
    df = pd.DataFrame([r for r in records if r["status"] == "ok"])
    if df.empty:
        return
    med = df.groupby(["task", "engine", "cores", "scale"]).agg(t=("task_seconds", "median"), m=("peak_rss_mb", "max"),
                                                           st=("startup_seconds", "median")).reset_index()
    med.to_csv(RESULTS / "scale_bench_summary.csv", index=False)
    titles = {"clean": "清洗（逐行解析）", "aggregate": "多维分位数聚合", "als": "隐式 ALS"}
    for metric, ylabel, fname in (("t", "任务耗时 / s（不含 Spark 启动）", "scale_time.png"), ("m", "进程树峰值 RSS / MB", "scale_memory.png")):
        fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
        for ax, task in zip(axes, ("clean", "aggregate", "als")):
            d = med[med["task"] == task]
            for (engine, cores), g in d.groupby(["engine", "cores"]):
                g = g.sort_values("scale")
                label = f"Pandas" if engine == "pandas" and cores == 1 else (f"implicit {cores}线程" if engine == "pandas" else f"Spark local[{cores}]")
                if task == "als" and engine == "pandas" and cores == 1:
                    label = "implicit 1线程"
                ax.plot(g["scale"], g[metric], marker="o", label=label, linestyle="--" if engine == "pandas" else "-")
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_xlabel("职位数（行为数 = 10×职位数）")
            ax.set_ylabel(ylabel)
            ax.set_title(titles[task])
            ax.grid(alpha=0.3, which="both")
            ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(FIGURES / fname, dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    main()
