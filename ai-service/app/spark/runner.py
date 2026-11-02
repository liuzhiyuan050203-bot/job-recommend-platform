"""一次批次内串行执行清洗、聚合、薪资回归或混合推荐。

调度方式（2026-11 稳定性改造）：
- 接口触发的批次进入单并发队列，由后台调度线程逐个执行，同一时刻只有一个批次在跑；
  相同任务组合已在排队时直接复用该批次号，队列满（SPARK_BATCH_QUEUE_MAX）才返回 409。
- 默认（SPARK_BATCH_ISOLATED=true）每个批次在独立子进程 ``python -m app.spark.batch_worker`` 中运行，
  子进程有自己的 Driver JVM，并以 nice（SPARK_BATCH_NICE）降低优先级；核数由 session.spark_master() 的
  local[N] / 集群 spark.cores.max 限制。这样批任务不会占用 ai-service 进程，CPU 紧张时让位给在线问答。
- 跨进程互斥用文件锁（/tmp/bishe-spark-batch.lock）：命令行 run_all 与服务触发的批次不会同时跑。
- 状态仍以 spark_task_log 为准；子进程异常退出时把未结束任务记为失败。
"""

from __future__ import annotations

import collections
import fcntl
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.spark.aggregate import run_aggregate
from app.spark.clean import run_clean
from app.spark.datasource import clear_source_cache
from app.spark.recommend import run_recommend
from app.spark.salary_model import run_salary_regression
from app.core.config import AI_SERVICE_DIR, settings
from app.spark.session import spark_info, spark_master, stop_spark

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

LOCK_PATH = Path(os.environ.get("SPARK_BATCH_LOCK", "/tmp/bishe-spark-batch.lock"))
LOG_DIR = AI_SERVICE_DIR.parent / "logs" / "spark-batch"

_cond = threading.Condition()
_queue: collections.deque = collections.deque()
_current: dict | None = None
_dispatcher: threading.Thread | None = None
_inproc_busy = False  # 进程内 SparkSession 正被预测/命令行批次占用
_shutdown = False


class SparkBusyError(RuntimeError):
    def __init__(self, msg: str = "已有任务运行中") -> None:
        super().__init__(msg)


# ---------------- 跨进程文件锁 ----------------


def _open_lock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    return open(LOCK_PATH, "a+")


def try_file_lock():
    """非阻塞拿批次文件锁；拿到返回文件对象（关闭即释放），否则 None。"""
    handle = _open_lock()
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle
    except OSError:
        handle.close()
        return None


def wait_file_lock():
    """阻塞等文件锁（批次子进程用：命令行批次没跑完时排队等待）。"""
    handle = _open_lock()
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def _file_lock_busy() -> bool:
    handle = try_file_lock()
    if handle is None:
        return True
    handle.close()
    return False


# ---------------- 状态 ----------------


def is_running() -> bool:
    with _cond:
        if _current is not None or _queue or _inproc_busy:
            return True
    return _file_lock_busy()


def queue_state() -> dict:
    """调度器快照：正在跑的批次、排队批次与资源限制配置，供 /spark/status 与测试轮询。"""
    with _cond:
        current = dict(_current) if _current else None
        queued = [dict(item) for item in _queue]
        inproc = _inproc_busy
    external = current is None and not inproc and _file_lock_busy()
    return {
        "running": bool(current or queued or inproc or external),
        "current": current,
        "queued": queued,
        "externalLock": external,
        "isolated": bool(settings.SPARK_BATCH_ISOLATED),
        "master": spark_master(),
        "nice": _nice_value(),
        "queueMax": int(settings.SPARK_BATCH_QUEUE_MAX),
    }


def batch_phase(batch_no: str) -> str | None:
    """QUEUED / RUNNING：仍在调度器里；None：调度器不认识（已结束或来自命令行）。"""
    with _cond:
        if _current and _current.get("batchNo") == batch_no:
            return "RUNNING"
        for item in _queue:
            if item.get("batchNo") == batch_no:
                return "QUEUED"
    return None


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


def _nice_value() -> int:
    return max(0, min(19, int(settings.SPARK_BATCH_NICE or 0)))


def run_blocking(tasks: list[str] | None = None) -> dict:
    """命令行入口（run_all）：当前进程内直接跑，跨进程互斥。"""
    global _inproc_busy
    names = normalize_tasks(tasks)
    lock = try_file_lock()
    if lock is None:
        raise SparkBusyError()
    with _cond:
        if _inproc_busy:
            lock.close()
            raise SparkBusyError()
        _inproc_busy = True
    try:
        return _run(new_batch_no(), names, stop_when_done=True)
    finally:
        with _cond:
            _inproc_busy = False
        lock.close()


def submit_async(tasks: list[str] | None = None) -> dict:
    """入队并立即返回批次号。相同任务组合已在排队则复用；队列满抛 SparkBusyError（接口返回 409）。"""
    names = normalize_tasks(tasks)
    with _cond:
        if _shutdown:
            raise SparkBusyError("服务正在停止")
        for index, item in enumerate(_queue, 1):
            if item["tasks"] == names:
                return {"batchNo": item["batchNo"], "tasks": names, "status": "QUEUED", "position": index, "merged": True}
        if len(_queue) >= max(0, int(settings.SPARK_BATCH_QUEUE_MAX)) and (_current is not None or _queue):
            raise SparkBusyError("已有任务运行中，排队已满")
        job = {"batchNo": new_batch_no(), "tasks": names, "queuedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        busy = _current is not None or bool(_queue)
        _queue.append(job)
        position = len(_queue)
        _ensure_dispatcher()
        _cond.notify_all()
    status = "QUEUED" if busy else "SUBMITTED"
    return {"batchNo": job["batchNo"], "tasks": names, "status": status, "position": position if busy else 0}


def _ensure_dispatcher() -> None:
    global _dispatcher
    if _dispatcher is None or not _dispatcher.is_alive():
        _dispatcher = threading.Thread(target=_dispatch_loop, name="spark-dispatcher", daemon=True)
        _dispatcher.start()


def _dispatch_loop() -> None:
    global _current
    while True:
        with _cond:
            while not _queue and not _shutdown:
                _cond.wait()
            if _shutdown:
                return
            job = _queue.popleft()
            job["startedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _current = job
        try:
            if settings.SPARK_BATCH_ISOLATED:
                _run_subprocess(job)
            else:
                _run_in_thread(job)
        except Exception:
            logger.exception("Spark 批次 %s 调度异常", job["batchNo"])
        finally:
            with _cond:
                _current = None
                _cond.notify_all()
            _after_batch()


def _after_batch() -> None:
    try:
        from app.spark.recommend_online import invalidate_caches

        invalidate_caches()
    except Exception:
        logger.exception("刷新在线推荐缓存失败")


def _run_in_thread(job: dict) -> None:
    """SPARK_BATCH_ISOLATED=false：沿用进程内 SparkSession，仍受文件锁与队列约束。"""
    global _inproc_busy
    lock = wait_file_lock()
    with _cond:
        _inproc_busy = True
    try:
        _run(job["batchNo"], job["tasks"], stop_when_done=False)
    finally:
        with _cond:
            _inproc_busy = False
        lock.close()


def _run_subprocess(job: dict) -> None:
    batch_no, tasks = job["batchNo"], job["tasks"]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{batch_no}.log"
    cmd = [sys.executable, "-m", "app.spark.batch_worker", "--batch-no", batch_no, "--tasks", ",".join(tasks)]
    nice = _nice_value()
    if nice > 0 and shutil.which("nice"):
        cmd = ["nice", "-n", str(nice)] + cmd
    env = dict(os.environ)
    env["SPARK_MASTER"] = settings.SPARK_MASTER or "local[*]"
    env["PYTHONUNBUFFERED"] = "1"
    started = time.perf_counter()
    rc: int | None = None
    error = ""
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(
            cmd,
            cwd=str(AI_SERVICE_DIR),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # 自成进程组，超时或停服时连同 JVM 一起结束
        )
        with _cond:
            if _current is not None:
                _current["pid"] = proc.pid
                _current["log"] = str(log_path)
        logger.info("Spark 批次 %s 子进程 pid=%s nice=%s master=%s 任务=%s", batch_no, proc.pid, nice, spark_master(), tasks)
        try:
            rc = proc.wait(timeout=max(60, int(settings.SPARK_BATCH_TIMEOUT)))
        except subprocess.TimeoutExpired:
            error = f"批次超过 {settings.SPARK_BATCH_TIMEOUT}s 未结束，已终止"
            _kill_group(proc)
            rc = proc.returncode
    elapsed = round(time.perf_counter() - started, 1)
    if rc != 0 or error:
        error = error or f"批次子进程异常退出 rc={rc}，日志 {log_path}"
        logger.error("Spark 批次 %s 失败：%s", batch_no, error)
        try:
            from app.spark.db import fail_unfinished

            fail_unfinished(batch_no, {k: v[0] for k, v in TASKS.items()}, tasks, error)
        except Exception:
            logger.exception("回写批次失败状态时出错")
    else:
        logger.info("Spark 批次 %s 子进程结束，耗时 %ss", batch_no, elapsed)


def _kill_group(proc: subprocess.Popen, grace: float = 20.0) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def shutdown() -> None:
    """ai-service 停止时调用：清空队列，终止正在运行的批次子进程（未结束任务记为失败）。"""
    global _shutdown
    with _cond:
        _shutdown = True
        _queue.clear()
        current = dict(_current) if _current else None
        _cond.notify_all()
    if current and current.get("pid"):
        try:
            os.killpg(int(current["pid"]), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            from app.spark.db import fail_unfinished

            fail_unfinished(current["batchNo"], {k: v[0] for k, v in TASKS.items()}, current["tasks"], "ai-service 停止，批次被终止")
        except Exception:
            logger.exception("停服时回写批次状态失败")


def call_exclusive(func):
    """预测用进程内 SparkSession；批次运行或排队时返回 None，调用方改读最近批次结果。"""
    global _inproc_busy
    with _cond:
        if _inproc_busy or _current is not None or _queue:
            return None
        _inproc_busy = True
    try:
        if _file_lock_busy():
            return None
        return func()
    finally:
        with _cond:
            _inproc_busy = False
