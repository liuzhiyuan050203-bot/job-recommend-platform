"""按城市/方向、月份/技能、省份聚合，并切换 latest 批次。"""

from __future__ import annotations

from pyspark.sql import functions as F

from app.spark.datasource import load_sources
from app.spark.db import publish
from app.spark.dicts import PROVINCE_ADCODE
from app.spark.session import get_spark

SALARY_COLUMNS = [
    "batch_no",
    "province",
    "city",
    "tech_direction",
    "job_count",
    "avg_salary",
    "median_salary",
    "min_salary",
    "max_salary",
    "p25_salary",
    "p75_salary",
    "is_latest",
    "deleted",
]
TREND_COLUMNS = [
    "batch_no",
    "stat_month",
    "tag_name",
    "tech_direction",
    "demand_count",
    "avg_salary",
    "mom_rate",
    "is_latest",
    "deleted",
]
REGION_COLUMNS = [
    "batch_no",
    "province_name",
    "adcode",
    "job_count",
    "company_count",
    "avg_salary",
    "apply_count",
    "is_latest",
    "deleted",
]


def _money(value) -> float:
    return round(float(value), 2)


def _mom(rows: list[dict]) -> None:
    months = sorted({row["stat_month"] for row in rows})
    previous = {month: months[index - 1] for index, month in enumerate(months) if index}
    demand = {(row["stat_month"], row["tag_name"]): row["demand_count"] for row in rows}
    for row in rows:
        prior = previous.get(row["stat_month"])
        if not prior:
            row["mom_rate"] = None
            continue
        before = demand.get((prior, row["tag_name"]), 0)
        if not before:
            row["mom_rate"] = None
            continue
        rate = (row["demand_count"] - before) / before
        row["mom_rate"] = None if abs(rate) > 9999 else round(rate, 4)


def run_aggregate(batch_no: str) -> dict:
    spark = get_spark()
    jobs, tags = load_sources(spark)
    input_count = jobs.count()
    if input_count == 0:
        raise RuntimeError("没有已审核职位，无法聚合")

    salary = jobs.groupBy("province", "city", "tech_direction").agg(
        F.count("*").alias("job_count"),
        F.avg("avg_salary").alias("avg_salary"),
        F.min("avg_salary").alias("min_salary"),
        F.max("avg_salary").alias("max_salary"),
        F.expr("percentile_approx(avg_salary, 0.25, 10000)").alias("p25_salary"),
        F.expr("percentile_approx(avg_salary, 0.5, 10000)").alias("median_salary"),
        F.expr("percentile_approx(avg_salary, 0.75, 10000)").alias("p75_salary"),
    )
    salary_rows = []
    for row in salary.collect():
        salary_rows.append(
            (
                batch_no,
                row["province"],
                row["city"],
                row["tech_direction"],
                int(row["job_count"]),
                _money(row["avg_salary"]),
                _money(row["median_salary"]),
                _money(row["min_salary"]),
                _money(row["max_salary"]),
                _money(row["p25_salary"]),
                _money(row["p75_salary"]),
                1,
                0,
            )
        )

    job_keys = jobs.select("id", "publish_time", "avg_salary")
    trend_source = (
        tags.join(job_keys, tags.position_id == job_keys.id, "inner")
        .filter(F.col("publish_time").isNotNull())
        .withColumn("stat_month", F.date_format("publish_time", "yyyy-MM"))
        .groupBy("stat_month", "tag_name")
        .agg(
            F.first("tag_direction").alias("tech_direction"),
            F.countDistinct("position_id").alias("demand_count"),
            F.avg("avg_salary").alias("avg_salary"),
        )
    )
    trend_dicts = []
    for row in trend_source.collect():
        trend_dicts.append(
            {
                "stat_month": row["stat_month"],
                "tag_name": row["tag_name"],
                "tech_direction": row["tech_direction"] or "未分类",
                "demand_count": int(row["demand_count"]),
                "avg_salary": _money(row["avg_salary"]) if row["avg_salary"] is not None else None,
            }
        )
    _mom(trend_dicts)
    trend_rows = [
        (
            batch_no,
            item["stat_month"],
            item["tag_name"],
            item["tech_direction"],
            item["demand_count"],
            item["avg_salary"],
            item["mom_rate"],
            1,
            0,
        )
        for item in trend_dicts
    ]

    region = jobs.groupBy("province").agg(
        F.count("*").alias("job_count"),
        F.countDistinct("company_id").alias("company_count"),
        F.avg("avg_salary").alias("avg_salary"),
        F.sum("apply_count").alias("apply_count"),
    )
    region_rows = []
    skipped = []
    for row in region.collect():
        name = (row["province"] or "").strip()
        adcode = PROVINCE_ADCODE.get(name)
        if not adcode:
            skipped.append(name or "空")
            continue
        region_rows.append(
            (
                batch_no,
                name,
                adcode,
                int(row["job_count"]),
                int(row["company_count"]),
                _money(row["avg_salary"]) if row["avg_salary"] is not None else None,
                int(row["apply_count"] or 0),
                1,
                0,
            )
        )
    if not region_rows:
        raise RuntimeError("地区聚合没有可映射的省份: " + ",".join(skipped))

    counts = publish(
        batch_no,
        [
            ("spark_salary_stat", SALARY_COLUMNS, salary_rows),
            ("spark_tech_trend", TREND_COLUMNS, trend_rows),
            ("spark_region_dist", REGION_COLUMNS, region_rows),
        ],
    )
    output_count = sum(counts.values())
    message = (
        f"薪资统计{counts.get('spark_salary_stat', 0)}，"
        f"技术趋势{counts.get('spark_tech_trend', 0)}，"
        f"地区分布{counts.get('spark_region_dist', 0)}"
    )
    if skipped:
        message += "，未映射省份" + ",".join(skipped)
    return {
        "taskCode": "aggregate",
        "inputCount": input_count,
        "outputCount": output_count,
        "resultMsg": message,
        "params": {
            "batchNo": batch_no,
            "salaryStat": counts.get("spark_salary_stat", 0),
            "techTrend": counts.get("spark_tech_trend", 0),
            "regionDist": counts.get("spark_region_dist", 0),
            "skippedProvinces": skipped,
            "provinceAdcodes": len(PROVINCE_ADCODE),
        },
    }
