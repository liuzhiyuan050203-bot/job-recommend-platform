#!/usr/bin/env python3
"""Spark Standalone 伪分布式集群取证与对照。

前提：bash scripts/start-spark-cluster.sh 已拉起 Master(7077, UI 8081) 与 Worker。
一条命令：
    .venv/bin/python experiments/spark_cluster/run_cluster_bench.py \
        --service-batches 202611021945302bc9,202611021946204d73

做的事（全部真实执行，结果写 results/spark_cluster.json）：
1. 记录 Master /json（Worker 数、核数、内存）。
2. 每次提交到集群前先等 Master 上 coresused=0（避免 ai-service 常驻会话占核造成排队），同一份数据上，生产 CLI `python -m app.spark.run_all` 分别以 SPARK_MASTER=spark://127.0.0.1:7077
   与 local[*] 运行 clean,aggregate,salary_regression 和 recommend，记录墙钟、各任务秒数与产出，
   并核对两种 master 的产出（行数、R2、NDCG）是否一致。
3. 可选：experiments/scale 的 1e6 行 clean / aggregate / ALS 分别在集群（cores.max=4）与 local[4] 上跑一次。
4. 从 spark_task_log 读出通过平台接口触发的批次（--service-batches），附上 sparkMaster / sparkAppId。
5. 再记一次 Master /json 的 completedapps（应用 ID、核数、每 Executor 内存、时长）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "ai-service"))

from common import env_info, save_json  # noqa: E402

PY = str(ROOT / ".venv" / "bin" / "python")
CLUSTER = "spark://127.0.0.1:7077"
UI = "http://127.0.0.1:8081/json/"
TASK_LINE = re.compile(r"^\s+\[(\w+)\] ([\d.]+)s in=(\S+) out=(\S+) (.*)$")


def master_json() -> dict:
    with urllib.request.urlopen(UI, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def master_summary(data: dict) -> dict:
    return {
        "url": data.get("url"),
        "status": data.get("status"),
        "aliveworkers": data.get("aliveworkers"),
        "cores": data.get("cores"),
        "memoryMB": data.get("memory"),
        "workers": [
            {"id": w.get("id"), "host": w.get("host"), "cores": w.get("cores"), "memoryMB": w.get("memory"), "state": w.get("state")}
            for w in data.get("workers", [])
        ],
    }


def wait_cluster_idle(limit: float = 300.0) -> float:
    """等集群核数全部空闲（ai-service 常驻会话靠动态分配在空闲 60–120s 后归还 Executor），返回等待秒数。"""
    started = time.perf_counter()
    while time.perf_counter() - started < limit:
        if int(master_json().get("coresused") or 0) == 0:
            break
        time.sleep(2)
    return round(time.perf_counter() - started, 1)


def run_cli(master: str, tasks: str) -> dict:
    waited = wait_cluster_idle() if master.startswith("spark://") else 0.0
    env = dict(os.environ, SPARK_MASTER=master)
    started = time.perf_counter()
    proc = subprocess.run(
        [PY, "-m", "app.spark.run_all", "--tasks", tasks],
        cwd=ROOT / "ai-service", env=env, capture_output=True, text=True,
    )
    wall = time.perf_counter() - started
    tasks_out = []
    batch = None
    for line in proc.stdout.splitlines():
        m = re.match(r"batch_no=(\S+) 总耗时 ([\d.]+)s", line)
        if m:
            batch = m.group(1)
        m = TASK_LINE.match(line)
        if m:
            tasks_out.append({
                "task": m.group(1), "seconds": float(m.group(2)),
                "input": m.group(3), "output": m.group(4), "result": m.group(5),
            })
    return {
        "master": master, "tasks": tasks, "returncode": proc.returncode, "batchNo": batch,
        "waitedForIdleSeconds": waited,
        "wallSeconds": round(wall, 3), "taskResults": tasks_out,
        "stderrTail": proc.stderr.splitlines()[-5:] if proc.returncode else [],
    }


def run_scale(master: str | None, task: str, scale: int, cores: int) -> dict:
    cmd = [PY, str(ROOT / "experiments" / "scale" / "bench_worker.py"), "--engine", "spark",
           "--cores", str(cores), "--task", task, "--scale", str(scale), "--driver-memory", "2g"]
    waited = 0.0
    if master:
        cmd += ["--master", master]
        waited = wait_cluster_idle()
    started = time.perf_counter()
    # local 模式的 Python worker 不继承 sys.path 改动，需要 PYTHONPATH 才能 import app.spark（clean 的 UDF）
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT / "ai-service"), str(ROOT / "experiments")]))
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    wall = time.perf_counter() - started
    last = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    out = json.loads(last[-1]) if last else {}
    return {
        "master": master or f"local[{cores}]", "task": task, "scale": scale, "returncode": proc.returncode,
        "wallSeconds": round(wall, 3), "waitedForIdleSeconds": waited, **out,
        "stderrTail": proc.stderr.splitlines()[-5:] if proc.returncode else [],
    }


def service_rows(batches: list[str]) -> list[dict]:
    if not batches:
        return []
    from app.spark.db import connect

    conn = connect()
    try:
        with conn.cursor() as cur:
            marks = ",".join(["%s"] * len(batches))
            cur.execute(
                f"SELECT batch_no, task_code, status, start_time, end_time, input_count, output_count, params_json "
                f"FROM spark_task_log WHERE batch_no IN ({marks}) ORDER BY id",
                batches,
            )
            rows = []
            for row in cur.fetchall():
                params = json.loads(row["params_json"] or "{}")
                rows.append({
                    "batchNo": row["batch_no"], "task": row["task_code"], "status": row["status"],
                    "start": str(row["start_time"]), "end": str(row["end_time"]),
                    "input": row["input_count"], "output": row["output_count"],
                    "elapsedSeconds": params.get("elapsedSeconds"),
                    "sparkMaster": params.get("sparkMaster"), "sparkAppId": params.get("sparkAppId"),
                })
            return rows
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Spark Standalone 集群取证")
    ap.add_argument("--service-batches", default="", help="平台接口触发的批次号，逗号分隔")
    ap.add_argument("--scale", type=int, default=1000000, help="扩展性规模；0 表示跳过")
    ap.add_argument("--scale-cores", type=int, default=4)
    args = ap.parse_args()

    before = master_json()
    print(f"Master {before.get('url')} workers={before.get('aliveworkers')} cores={before.get('cores')}", flush=True)
    runs = []
    for master in (CLUSTER, "local[*]"):
        for tasks in ("clean,aggregate,salary_regression", "recommend"):
            print(f"== run_all {tasks} @ {master}", flush=True)
            result = run_cli(master, tasks)
            print(f"   rc={result['returncode']} wall={result['wallSeconds']}s "
                  + " ".join(f"{t['task']}={t['seconds']}s" for t in result["taskResults"]), flush=True)
            runs.append(result)

    consistency = {}
    for tasks in ("clean,aggregate,salary_regression", "recommend"):
        pair = [r for r in runs if r["tasks"] == tasks]
        a = {t["task"]: (t["input"], t["output"], t["result"]) for t in pair[0]["taskResults"]}
        b = {t["task"]: (t["input"], t["output"], t["result"]) for t in pair[1]["taskResults"]}
        consistency[tasks] = {task: a.get(task) == b.get(task) for task in sorted(set(a) | set(b))}

    scale_runs = []
    if args.scale > 0:
        for task in ("clean", "aggregate", "als"):
            for master in (CLUSTER, None):
                print(f"== scale {task} {args.scale} @ {master or f'local[{args.scale_cores}]'}", flush=True)
                result = run_scale(master, task, args.scale, args.scale_cores)
                print(f"   rc={result['returncode']} task={result.get('task_seconds')}s startup={result.get('startup_seconds')}s", flush=True)
                scale_runs.append(result)

    after = master_json()
    apps = [
        {"id": a.get("id"), "name": a.get("name"), "cores": a.get("cores"),
         "memoryPerExecutorMB": a.get("memoryperexecutor", a.get("memoryperslave")),
         "durationMs": a.get("duration"), "state": a.get("state")}
        for a in after.get("completedapps", []) + after.get("activeapps", [])
    ]
    payload = {
        "env": env_info(),
        "deployment": {
            "mode": "Spark Standalone 伪分布式（单机 1 Master + 多 Worker，Driver 为 client 模式）",
            "master": CLUSTER, "masterWebUI": "http://127.0.0.1:8081",
            "scripts": ["scripts/start-spark-cluster.sh", "scripts/stop-spark-cluster.sh", "scripts/start-all.sh --spark-cluster"],
            "serviceConfig": "SPARK_MASTER / SPARK_EXECUTOR_MEMORY / SPARK_EXECUTOR_CORES / SPARK_CORES_MAX，集群模式开启动态分配（空闲 60–120s 归还 Executor）",
        },
        "masterBefore": master_summary(before),
        "cliRuns": runs,
        "clusterVsLocalSameOutput": consistency,
        "scaleRuns": scale_runs,
        "serviceTriggered": service_rows([b for b in args.service_batches.split(",") if b]),
        "masterApps": apps,
        "notes": (
            "同一台 8 vCPU 机器上，集群模式只有 2 Worker × 2 核，local[*] 可用 8 线程，"
            "且集群多了 Executor 进程间序列化与调度开销，因此单机伪分布式不以提速为目的，"
            "用于验证同一套 PySpark 作业可以不改代码提交到 Standalone 集群。"
        ),
    }
    save_json("spark_cluster.json", payload)
    print("完成", flush=True)


if __name__ == "__main__":
    main()
