"""构造回归特征 DataFrame。"""

from __future__ import annotations

import json

from pyspark.sql.types import ArrayType, DoubleType, IntegerType, StringType, StructField, StructType

FEATURE_SCHEMA = StructType(
    [
        StructField("city", StringType(), False),
        StructField("province", StringType(), False),
        StructField("tech_direction", StringType(), False),
        StructField("education", IntegerType(), False),
        StructField("edu_years", DoubleType(), False),
        StructField("exp_years", DoubleType(), False),
        StructField("city_tier", DoubleType(), False),
        StructField("job_type_num", DoubleType(), False),
        StructField("skill_arr", ArrayType(StringType()), False),
        StructField("feature_json", StringType(), False),
    ]
)


def build_feature_frame(spark, records: list[dict]):
    rows = []
    for item in records:
        skills = [str(name) for name in item.get("skills") or [] if str(name).strip()]
        payload = {
            "city": item["city"],
            "province": item["province"],
            "techDirection": item["tech_direction"],
            "education": int(item["education"]),
            "eduYears": float(item["edu_years"]),
            "experienceYears": float(item["exp_years"]),
            "cityTier": int(item["city_tier"]),
            "jobType": int(item.get("job_type_num") or 3),
            "skills": skills,
        }
        rows.append(
            (
                item["city"],
                item["province"],
                item["tech_direction"],
                int(item["education"]),
                float(item["edu_years"]),
                float(item["exp_years"]),
                float(item["city_tier"]),
                float(item["job_type_num"]),
                skills,
                item.get("feature_json") or json.dumps(payload, ensure_ascii=False),
            )
        )
    return spark.createDataFrame(rows, FEATURE_SCHEMA)
