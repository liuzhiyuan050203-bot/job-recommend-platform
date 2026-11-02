"""Spark 批次子进程入口：python -m app.spark.batch_worker --batch-no X --tasks recommend

由 runner 的调度线程以 nice 低优先级拉起，自带 Driver JVM，与 ai-service 的事件循环和大模型推理隔离。
先阻塞等待跨进程文件锁（命令行批次没跑完时排队），再按 runner._run 串行执行并写 spark_task_log。
任一任务失败时退出码为 1；调度线程据此兜底回写未结束的任务。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Spark 批次子进程")
    parser.add_argument("--batch-no", required=True)
    parser.add_argument("--tasks", required=True, help="逗号分隔任务代码")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    for noisy in ("py4j", "httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    log = logging.getLogger("spark-batch")

    from app.spark.runner import _run, normalize_tasks, wait_file_lock
    from app.spark.session import spark_master

    tasks = normalize_tasks([item.strip() for item in args.tasks.split(",") if item.strip()])
    lock = wait_file_lock()
    try:
        log.info("批次 %s 开始 master=%s 任务=%s", args.batch_no, spark_master(), tasks)
        result = _run(args.batch_no, tasks, stop_when_done=True)
    finally:
        lock.close()
    print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
    return 0 if all(int(task.get("status", 2)) == 1 for task in result["tasks"]) else 1


if __name__ == "__main__":
    sys.exit(main())
