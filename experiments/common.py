"""实验公共工具：路径、结果落盘、绘图中文字体、Spark 会话。"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

EXP_DIR = Path(__file__).resolve().parent
REPO = EXP_DIR.parent
RESULTS = EXP_DIR / "results"
FIGURES = EXP_DIR / "figures"
DATA = EXP_DIR / "data"
AI_SERVICE = REPO / "ai-service"
for p in (RESULTS, FIGURES, DATA):
    p.mkdir(parents=True, exist_ok=True)
if str(AI_SERVICE) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE))

os.environ.setdefault("JAVA_HOME", "/usr/lib/jvm/java-21-openjdk-amd64")
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable


def env_info() -> dict:
    import multiprocessing

    info = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": multiprocessing.cpu_count(),
        "time": time.strftime("%Y-%m-%d %H:%M:%S %z"),
    }
    try:
        import pyspark

        info["pyspark"] = pyspark.__version__
    except Exception:
        pass
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith(("MemTotal", "MemAvailable")):
                    k, v = line.split(":")
                    info[k] = v.strip()
    except OSError:
        pass
    return info


def save_json(name: str, payload) -> Path:
    path = RESULTS / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[saved] {path.relative_to(REPO)}")
    return path


def setup_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    for fam in ("Noto Sans CJK SC", "Noto Sans CJK JP", "WenQuanYi Zen Hei", "SimHei"):
        if any(fam == f.name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.sans-serif"] = [fam]
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 120
    return plt


def spark_session(master: str = "local[*]", driver_memory: str = "2g", app: str = "bishe-experiments", extra: dict | None = None):
    from pyspark.sql import SparkSession

    os.makedirs("/tmp/bishe-exp-warehouse", exist_ok=True)
    builder = (
        SparkSession.builder.appName(app)
        .master(master)
        .config("spark.driver.memory", driver_memory)
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.ui.enabled", "false")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.sql.warehouse.dir", "/tmp/bishe-exp-warehouse")
        .config("spark.sql.session.timeZone", "Asia/Shanghai")
    )
    for k, v in (extra or {}).items():
        builder = builder.config(k, v)
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark
