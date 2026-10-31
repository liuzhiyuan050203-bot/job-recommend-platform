"""仓库内路径与 JDBC 驱动定位。"""

from __future__ import annotations

import os
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = AI_ROOT.parent
CSV_PATH = REPO_ROOT / "data" / "raw" / "jobs_raw.csv"
DATA_DIR = AI_ROOT / "data"
CLEAN_PARQUET = DATA_DIR / "clean" / "jobs_clean.parquet"
MODEL_DIR = DATA_DIR / "models" / "salary_model"
METRICS_PATH = DATA_DIR / "models" / "salary_metrics.json"
RECOMMEND_DIR = DATA_DIR / "recommend"
RECOMMEND_MODEL_PATH = RECOMMEND_DIR / "cf_model.pkl"
RECOMMEND_EVAL_PATH = RECOMMEND_DIR / "eval_metrics.json"

DEFAULT_JDBC_JAR = (
    Path.home() / ".m2/repository/com/mysql/mysql-connector-j/8.3.0/mysql-connector-j-8.3.0.jar"
)


def jdbc_jar() -> str:
    """优先 SPARK_JDBC_JAR，否则使用本机 Maven 仓库里的 MySQL 驱动。"""
    configured = os.environ.get("SPARK_JDBC_JAR", "").strip()
    if configured:
        path = Path(configured).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"环境变量 SPARK_JDBC_JAR 指向的文件不存在: {path}")
        return str(path)
    if DEFAULT_JDBC_JAR.is_file():
        return str(DEFAULT_JDBC_JAR)
    raise FileNotFoundError(
        "未找到 MySQL JDBC 驱动。请设置环境变量 SPARK_JDBC_JAR，"
        f"或将 mysql-connector-j 放到 {DEFAULT_JDBC_JAR}"
    )
