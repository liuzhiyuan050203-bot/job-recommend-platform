"""可复用的 SparkSession。

master 取 settings.SPARK_MASTER（环境变量 SPARK_MASTER），默认 local[*]，
并按 SPARK_LOCAL_CORES（默认 4）改写成 local[4]，给同机的大模型和 API 留出 CPU；
设为 spark://127.0.0.1:7077 时连接 scripts/start-spark-cluster.sh 拉起的 Standalone 伪分布式集群，
Driver 在 ai-service 进程内（client 模式），Executor 在各 Worker 上。
"""

from __future__ import annotations

import logging
import os
import sys
import threading

os.environ.setdefault("JAVA_HOME", "/usr/lib/jvm/java-21-openjdk-amd64")
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
os.environ.setdefault("SPARK_DRIVER_MEMORY", "2g")
_java_bin = os.path.join(os.environ["JAVA_HOME"], "bin")
if _java_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _java_bin + os.pathsep + os.environ.get("PATH", "")

from app.core.config import settings
from app.spark.paths import DATA_DIR, jdbc_jar

_lock = threading.Lock()
_spark = None


def jdbc_url() -> str:
    return (
        f"jdbc:mysql://{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}"
        "?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai"
        "&useSSL=false&allowPublicKeyRetrieval=true"
    )


def spark_master() -> str:
    """local[*] 会占满全部核，与同机的大模型推理抢 CPU；SPARK_LOCAL_CORES>0 时改写成 local[N]。

    显式写了 local[2] 这类核数或 spark:// 集群地址时原样使用（集群核数由 SPARK_CORES_MAX 限制）。
    """
    master = (settings.SPARK_MASTER or "local[*]").strip() or "local[*]"
    cores = int(settings.SPARK_LOCAL_CORES or 0)
    if master in ("local[*]", "local") and cores > 0:
        return f"local[{min(cores, os.cpu_count() or cores)}]"
    return master


def is_cluster() -> bool:
    return spark_master().startswith("spark://")


def spark_info() -> dict:
    """当前会话的 master / applicationId / 并行度，用于任务日志和集群取证。"""
    spark = _spark
    if spark is None:
        return {"master": spark_master(), "appId": None}
    sc = spark.sparkContext
    return {"master": sc.master, "appId": sc.applicationId, "defaultParallelism": sc.defaultParallelism}


def get_spark():
    """driver 2g，关闭 UI，同一进程内复用。master 见 spark_master()。"""
    global _spark
    with _lock:
        if _spark is not None:
            return _spark
        jar = jdbc_jar()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        warehouse = "/tmp/bishe-spark-warehouse"
        os.makedirs(warehouse, exist_ok=True)
        os.makedirs("/tmp/bishe-spark-derby", exist_ok=True)
        from pyspark.sql import SparkSession

        builder = (
            SparkSession.builder.appName("JobPlatform-SparkEngine")
            .master(spark_master())
            .config("spark.driver.memory", "2g")
            .config("spark.sql.shuffle.partitions", "8")
            .config("spark.ui.enabled", "false")
            .config("spark.ui.showConsoleProgress", "false")
            .config("spark.sql.adaptive.enabled", "false")
            .config("spark.sql.session.timeZone", "Asia/Shanghai")
            .config("spark.driver.host", "127.0.0.1")
            .config("spark.driver.bindAddress", "127.0.0.1")
            .config("spark.jars", jar)
            .config("spark.driver.extraClassPath", jar)
            .config("spark.executor.extraClassPath", jar)
            .config("spark.sql.warehouse.dir", warehouse)
            .config("spark.driver.extraJavaOptions", "-Dderby.system.home=/tmp/bishe-spark-derby")
        )
        if is_cluster():
            ai_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            builder = (
                builder.config("spark.executor.memory", settings.SPARK_EXECUTOR_MEMORY)
                .config("spark.executor.cores", str(settings.SPARK_EXECUTOR_CORES))
                .config("spark.cores.max", str(settings.SPARK_CORES_MAX))
                .config("spark.pyspark.python", sys.executable)
                .config("spark.pyspark.driver.python", sys.executable)
                # Executor 上的 Python worker 要能 import app.spark.*（clean 的 UDF）
                .config("spark.executorEnv.PYTHONPATH", ai_root)
                .config("spark.executorEnv.JAVA_HOME", os.environ["JAVA_HOME"])
                # ai-service 常驻持有会话；空闲时归还 Executor，避免长期占满集群核数
                .config("spark.dynamicAllocation.enabled", "true")
                .config("spark.dynamicAllocation.shuffleTracking.enabled", "true")
                .config("spark.dynamicAllocation.shuffleTracking.timeout", "120s")
                .config("spark.dynamicAllocation.executorIdleTimeout", "60s")
                .config("spark.dynamicAllocation.cachedExecutorIdleTimeout", "120s")
                .config("spark.dynamicAllocation.minExecutors", "0")
                .config(
                    "spark.dynamicAllocation.maxExecutors",
                    str(max(1, int(settings.SPARK_CORES_MAX) // max(1, int(settings.SPARK_EXECUTOR_CORES)))),
                )
            )
        _spark = builder.getOrCreate()
        sc = _spark.sparkContext
        logging.getLogger(__name__).info(
            "SparkSession master=%s appId=%s defaultParallelism=%s", sc.master, sc.applicationId, sc.defaultParallelism
        )
        _spark.sparkContext.setLogLevel("WARN")
        return _spark


def stop_spark() -> None:
    global _spark
    with _lock:
        spark = _spark
        _spark = None
    if spark is not None:
        spark.stop()


def read_query(spark, sql: str):
    return (
        spark.read.format("jdbc")
        .option("url", jdbc_url())
        .option("driver", "com.mysql.cj.jdbc.Driver")
        .option("user", settings.MYSQL_USER)
        .option("password", settings.MYSQL_PASSWORD)
        .option("dbtable", f"({sql}) t")
        .option("fetchsize", "2000")
        .load()
    )
