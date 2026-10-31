"""清洗爬虫 CSV，并加载 JDBC 主数据。"""

from __future__ import annotations

from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType

from app.spark.datasource import load_sources
from app.spark.parsing import classify_job
from app.spark.paths import CLEAN_PARQUET, CSV_PATH
from app.spark.session import get_spark

_PARSE_SCHEMA = StructType(
    [
        StructField("status", StringType(), False),
        StructField("city", StringType(), True),
        StructField("province", StringType(), True),
        StructField("salary_min", DoubleType(), True),
        StructField("salary_max", DoubleType(), True),
        StructField("salary_avg", DoubleType(), True),
        StructField("salary_months", IntegerType(), True),
        StructField("education", IntegerType(), True),
        StructField("experience_req", IntegerType(), True),
        StructField("publish_date", StringType(), True),
        StructField("direction", StringType(), True),
    ]
)


def _parse_row(salary_text, city, education_text, experience_text, publish_date, direction):
    parsed = classify_job(salary_text, city, education_text, experience_text, publish_date, direction)
    return (
        parsed.get("status") or "anomaly",
        parsed.get("city"),
        parsed.get("province"),
        parsed.get("salary_min"),
        parsed.get("salary_max"),
        parsed.get("salary_avg"),
        parsed.get("salary_months"),
        parsed.get("education"),
        parsed.get("experience_req"),
        parsed.get("publish_date"),
        parsed.get("direction"),
    )


def run_clean(batch_no: str) -> dict:
    if not CSV_PATH.is_file():
        raise FileNotFoundError(f"找不到原始 CSV: {CSV_PATH}")
    spark = get_spark()
    raw = (
        spark.read.option("header", True)
        .option("encoding", "UTF-8")
        .option("escape", '"')
        .csv(str(CSV_PATH))
    )
    raw_count = raw.count()
    exact = raw.dropDuplicates()
    keyed = exact.dropDuplicates(["title", "company", "city"])
    parse = F.udf(_parse_row, _PARSE_SCHEMA)
    parsed = keyed.withColumn(
        "parsed",
        parse(
            F.col("salary_text"),
            F.col("city"),
            F.col("education_text"),
            F.col("experience_text"),
            F.col("publish_date"),
            F.col("direction"),
        ),
    ).withColumn("clean_status", F.col("parsed.status"))
    parsed = parsed.cache()
    status_rows = parsed.groupBy("clean_status").count().collect()
    counts = {row["clean_status"]: int(row["count"]) for row in status_rows}
    keyed_count = sum(counts.values())
    duplicate_count = raw_count - keyed_count
    negotiable_count = counts.get("negotiable", 0)
    anomaly_count = counts.get("anomaly", 0)
    valid_count = counts.get("valid", 0)
    valid = parsed.filter(F.col("clean_status") == "valid").select(
        F.col("title"),
        F.col("company"),
        F.col("parsed.city").alias("city"),
        F.col("parsed.province").alias("province"),
        F.col("parsed.salary_min").alias("salary_min"),
        F.col("parsed.salary_max").alias("salary_max"),
        F.col("parsed.salary_avg").alias("salary_avg"),
        F.col("parsed.salary_months").alias("salary_months"),
        F.col("parsed.education").alias("education"),
        F.col("parsed.experience_req").alias("experience_req"),
        F.col("parsed.publish_date").alias("publish_date"),
        F.col("parsed.direction").alias("direction"),
        F.col("tags"),
    )
    if valid_count > 0:
        CLEAN_PARQUET.parent.mkdir(parents=True, exist_ok=True)
        valid.write.mode("overwrite").parquet(str(CLEAN_PARQUET))
    parsed.unpersist()

    jobs, _tags = load_sources(spark)
    jdbc_count = jobs.count()
    params = {
        "batchNo": batch_no,
        "rawCount": raw_count,
        "duplicateCount": duplicate_count,
        "negotiableCount": negotiable_count,
        "anomalyCount": anomaly_count,
        "validCount": valid_count,
        "jdbcJobCount": jdbc_count,
        "parquet": str(CLEAN_PARQUET) if valid_count else None,
    }
    message = (
        f"原始{raw_count}行，重复{duplicate_count}，面议{negotiable_count}，"
        f"异常{anomaly_count}，有效{valid_count}，主数据职位{jdbc_count}"
    )
    return {
        "taskCode": "clean",
        "inputCount": raw_count,
        "outputCount": valid_count,
        "resultMsg": message,
        "params": params,
    }
