"""可复用的本地 SparkSession。"""

from __future__ import annotations

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


def get_spark():
    """local[*]，driver 2g，关闭 UI。同一进程内复用。"""
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
            .master("local[*]")
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
        _spark = builder.getOrCreate()
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
