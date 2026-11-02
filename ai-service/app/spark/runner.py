"""一次批次内串行执行清洗、聚合、薪资回归或混合推荐。进程内只允许一轮在跑。"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime

from app.spark.aggregate import run_aggregate
from app.spark.clean import run_clean
from app.spark.datasource import clear_source_cache
from app.spark.recommend import run_recommend
from app.spark.salary_model import run_salary_regression
from app.spark.session import spark_info, stop_spark

logger = logging.getLogger(__name__)

# 默认批次保持第三阶段的三项。recommend 需显式指定，避免拖慢分析触发。
CANONICAL = ("clean", "aggregate", "salary_regression")
TASK_ORDER = ("clean", "aggregate", "salary_regression", "recommend")
TASKS = {
    "clean": ("招聘数据清洗", run_clean),
    "aggregate": ("薪资与趋势聚合", run_aggregate),
    "salary_regression": ("薪资回归", run_salary_regression),
    "recommend": ("混合职位推荐", run_recommend),
}

_state = threading.Lock()
_running = False


class SparkBusyError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("已有任务运行中")


def is_running() -> bool:
    with _state:
        return _running


def _acquire() -> bool:
    global _running
    with _state:
        if _running:
            return False
        _running = True
        return True


def _release() -> None:
    global _running
    with _state:
        _running = False


def normalize_tasks(tasks: list[str] | None) -> list[str]:
    if not tasks:
        return list(CANONICAL)
    unknown = [item for item in tasks if item not in TASKS]
    if unknown:
        raise ValueError("不支持的任务: " + "、".join(unknown))
    wanted = set(tasks)
    return [name for name in TASK_ORDER if name in wanted]


def new_batch_no() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:4]


def _one(batch_no: str, task_code: str) -> dict:
    from app.spark.db import finish_task, start_task

    task_name, func = TASKS[task_code]
    started = time.perf_counter()
    task_id = start_task(batch_no, task_code, task_name, {"batchNo": batch_no, "taskCode": task_code})
    try:
        outcome = func(batch_no)
        elapsed = round(time.perf_counter() - started, 3)
        params = dict(outcome.get("params") or {})
        params["elapsedSeconds"] = elapsed
        info = spark_info()
        params["sparkMaster"] = info.get("master")
        params["sparkAppId"] = info.get("appId")
        finish_task(
            task_id,
            1,
            input_count=outcome.get("inputCount"),
            output_count=outcome.get("outputCount"),
            result_msg=outcome.get("resultMsg"),
            params=params,
        )
        logger.info("%s 完成，耗时 %ss，%s", task_code, elapsed, outcome.get("resultMsg"))
        return {
            "taskCode": task_code,
            "taskName": task_name,
            "status": 1,
            "elapsedSeconds": elapsed,
            "inputCount": outcome.get("inputCount"),
            "outputCount": outcome.get("outputCount"),
            "resultMsg": outcome.get("resultMsg"),
            "params": params,
        }
    except Exception as exc:
        elapsed = round(time.perf_counter() - started, 3)
        logger.exception("%s 失败", task_code)
        try:
            finish_task(task_id, 2, error_msg=str(exc), params={"batchNo": batch_no, "elapsedSeconds": elapsed})
        except Exception:
            logger.exception("回写任务失败状态时出错")
        return {
            "taskCode": task_code,
            "taskName": task_name,
            "status": 2,
            "elapsedSeconds": elapsed,
            "errorMsg": str(exc),
        }


def _run(batch_no: str, tasks: list[str], stop_when_done: bool) -> dict:
    started = time.perf_counter()
    results = []
    try:
        for task_code in tasks:
            results.append(_one(batch_no, task_code))
        return {
            "batchNo": batch_no,
            "elapsedSeconds": round(time.perf_counter() - started, 3),
            "tasks": results,
        }
    finally:
        if stop_when_done:
            clear_source_cache()
            stop_spark()


def run_blocking(tasks: list[str] | None = None) -> dict:
    names = normalize_tasks(tasks)
    if not _acquire():
        raise SparkBusyError()
    try:
        return _run(new_batch_no(), names, stop_when_done=True)
    finally:
        _release()


def submit_async(tasks: list[str] | None = None) -> dict:
    names = normalize_tasks(tasks)
    if not _acquire():
        raise SparkBusyError()
    batch_no = new_batch_no()

    def worker() -> None:
        try:
            _run(batch_no, names, stop_when_done=False)
        except Exception:
            logger.exception("Spark 后台任务异常")
        finally:
            _release()

    threading.Thread(target=worker, name=f"spark-{batch_no}", daemon=True).start()
    return {"batchNo": batch_no, "tasks": names, "status": "SUBMITTED"}


def call_exclusive(func):
    """预测与训练共用 SparkSession，避免并发。拿不到锁时返回 None。"""
    if not _acquire():
        return None
    try:
        return func()
    finally:
        _release()
