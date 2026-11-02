"""从 MySQL 读取已审核职位，作为聚合和回归的主数据。"""

from __future__ import annotations

from pyspark.sql import functions as F

from app.spark.session import read_query

_CACHE: dict = {"jobs": None, "tags": None}

JOB_SQL = """
SELECT p.id AS id,
       p.company_id AS company_id,
       p.tech_direction AS tech_direction,
       p.province AS province,
       p.city AS city,
       p.salary_min AS salary_min,
       p.salary_max AS salary_max,
       (p.salary_min + p.salary_max) / 2.0 AS avg_salary,
       p.education AS education,
       p.experience_req AS experience_req,
       p.job_type AS job_type,
       p.publish_time AS publish_time
FROM job_position p
INNER JOIN ent_company c ON c.id = p.company_id AND c.deleted = 0
WHERE p.deleted = 0 AND p.audit_status = 1
  AND p.salary_max >= p.salary_min
"""

TAG_SQL = """
SELECT pt.position_id AS position_id,
       st.name AS tag_name,
       st.direction AS tag_direction
FROM job_position_tag pt
INNER JOIN skill_tag st ON st.id = pt.tag_id AND st.deleted = 0
INNER JOIN job_position p ON p.id = pt.position_id AND p.deleted = 0 AND p.audit_status = 1
WHERE pt.deleted = 0
"""

APPLY_SQL = """
SELECT a.position_id AS position_id, COUNT(*) AS apply_count
FROM job_application a
INNER JOIN job_position p ON p.id = a.position_id AND p.deleted = 0 AND p.audit_status = 1
WHERE a.deleted = 0
GROUP BY a.position_id
"""


def load_sources(spark):
    """返回 (职位 DataFrame, 技能标签 DataFrame)，进程内缓存。"""
    if _CACHE["jobs"] is not None:
        return _CACHE["jobs"], _CACHE["tags"]
    jobs = read_query(spark, JOB_SQL)
    tags = read_query(spark, TAG_SQL)
    applies = read_query(spark, APPLY_SQL).withColumnRenamed("position_id", "apply_position_id")
    skills = (
        tags.groupBy("position_id")
        .agg(F.collect_list("tag_name").alias("skill_arr"))
        .withColumnRenamed("position_id", "skill_position_id")
    )
    frame = jobs.join(skills, jobs.id == skills.skill_position_id, "left").drop("skill_position_id")
    frame = frame.join(applies, jobs.id == applies.apply_position_id, "left").drop("apply_position_id")
    frame = frame.fillna({"apply_count": 0})
    frame = frame.withColumn("avg_salary", F.col("avg_salary").cast("double"))
    frame = frame.withColumn("apply_count", F.col("apply_count").cast("int"))
    frame = frame.filter(
        F.col("city").isNotNull()
        & F.col("tech_direction").isNotNull()
        & F.col("province").isNotNull()
        & (F.col("avg_salary") >= 1000)
        & (F.col("avg_salary") <= 200000)
    )
    empty_skills = F.expr("cast(array() as array<string>)")
    frame = frame.withColumn(
        "skill_arr",
        F.when(F.col("skill_arr").isNull(), empty_skills).otherwise(F.col("skill_arr")),
    )
    frame = frame.cache()
    tags = tags.cache()
    frame.count()
    tags.count()
    _CACHE["jobs"] = frame
    _CACHE["tags"] = tags
    return frame, tags


def clear_source_cache() -> None:
    jobs = _CACHE.get("jobs")
    tags = _CACHE.get("tags")
    _CACHE["jobs"] = None
    _CACHE["tags"] = None
    for frame in (jobs, tags):
        if frame is not None:
            try:
                frame.unpersist()
            except Exception:
                pass
