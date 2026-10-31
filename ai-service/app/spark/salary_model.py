"""Spark MLlib 随机森林薪资回归，并把网格预测写入 spark_salary_predict。"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

from pyspark.ml import Pipeline
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml.feature import CountVectorizer, OneHotEncoder, StringIndexer, VectorAssembler
from pyspark.ml.regression import RandomForestRegressor
from pyspark.sql import functions as F

from app.spark.datasource import load_sources
from app.spark.db import publish
from app.spark.dicts import EDU_YEARS, EXP_REQ_YEARS, city_tier, job_type_for_experience
from app.spark.features import build_feature_frame
from app.spark.paths import METRICS_PATH, MODEL_DIR
from app.spark.session import get_spark

PREDICT_COLUMNS = [
    "batch_no",
    "user_id",
    "position_id",
    "province",
    "city",
    "tech_direction",
    "education",
    "experience_years",
    "predicted_salary",
    "ci_low",
    "ci_high",
    "model_version",
    "feature_json",
    "is_latest",
    "deleted",
]
GRID_EDUCATION = (1, 2, 3, 4)
GRID_EXPERIENCE = (0.0, 1.0, 3.0, 5.0)


def _prepare(df):
    experience = F.lit(EXP_REQ_YEARS[0])
    for code, years in EXP_REQ_YEARS.items():
        experience = F.when(F.col("experience_req") == code, float(years)).otherwise(experience)
    education = F.lit(EDU_YEARS[0])
    for code, years in EDU_YEARS.items():
        education = F.when(F.col("education") == code, float(years)).otherwise(education)
    tier = (
        F.when(F.col("city").isin("北京", "上海", "深圳", "广州"), 1.0)
        .when(F.col("city").isin("杭州", "南京", "苏州", "厦门", "成都", "武汉", "西安", "天津"), 2.0)
        .otherwise(3.0)
    )
    return (
        df.withColumn("edu_years", education)
        .withColumn("exp_years", experience)
        .withColumn("city_tier", tier)
        .withColumn("job_type_num", F.col("job_type").cast("double"))
        .filter(F.col("job_type_num").isNotNull())
    )


def _pipeline() -> Pipeline:
    city_indexer = StringIndexer(
        inputCol="city", outputCol="city_idx", handleInvalid="keep", stringOrderType="alphabetAsc"
    )
    direction_indexer = StringIndexer(
        inputCol="tech_direction", outputCol="dir_idx", handleInvalid="keep", stringOrderType="alphabetAsc"
    )
    city_encoder = OneHotEncoder(inputCols=["city_idx"], outputCols=["city_vec"], handleInvalid="keep", dropLast=False)
    direction_encoder = OneHotEncoder(
        inputCols=["dir_idx"], outputCols=["dir_vec"], handleInvalid="keep", dropLast=False
    )
    skills = CountVectorizer(inputCol="skill_arr", outputCol="skill_vec", minDF=1.0, vocabSize=64)
    assembler = VectorAssembler(
        inputCols=["city_vec", "dir_vec", "edu_years", "exp_years", "city_tier", "job_type_num", "skill_vec"],
        outputCol="features",
        handleInvalid="keep",
    )
    regressor = RandomForestRegressor(
        featuresCol="features",
        labelCol="avg_salary",
        numTrees=60,
        maxDepth=12,
        seed=42,
        subsamplingRate=0.9,
        featureSubsetStrategy="all",
        minInstancesPerNode=1,
    )
    return Pipeline(
        stages=[city_indexer, direction_indexer, city_encoder, direction_encoder, skills, assembler, regressor]
    )


def _score(frame, name: str) -> float:
    evaluator = RegressionEvaluator(labelCol="avg_salary", predictionCol="prediction", metricName=name)
    return float(evaluator.evaluate(frame))


def run_salary_regression(batch_no: str) -> dict:
    spark = get_spark()
    jobs, _tags = load_sources(spark)
    prepared = _prepare(jobs).cache()
    total = prepared.count()
    if total < 20:
        prepared.unpersist()
        raise RuntimeError(f"可用于回归的职位只有 {total} 条")
    train, test = prepared.randomSplit([0.8, 0.2], seed=42)
    train = train.cache()
    test = test.cache()
    train_count = train.count()
    test_count = test.count()
    if train_count == 0 or test_count == 0:
        prepared.unpersist()
        raise RuntimeError("训练集或测试集为空")
    model = _pipeline().fit(train)
    predicted = model.transform(test)
    rmse = round(_score(predicted, "rmse"), 2)
    mae = round(_score(predicted, "mae"), 2)
    r2 = round(_score(predicted, "r2"), 4)
    version = f"rf-{batch_no}"
    if len(version) > 32:
        raise RuntimeError(f"model_version 超过 32 字符: {version}")

    pair_rows = prepared.select("city", "province", "tech_direction").distinct().collect()
    skill_bag: dict[str, Counter] = defaultdict(Counter)
    for row in prepared.select("tech_direction", "skill_arr").collect():
        skill_bag[row["tech_direction"]].update([name for name in (row["skill_arr"] or []) if name])
    direction_skills = {
        direction: [name for name, _count in counter.most_common(4)]
        for direction, counter in skill_bag.items()
    }
    city_province = {}
    records = []
    for row in pair_rows:
        city_province[row["city"]] = row["province"]
        for education in GRID_EDUCATION:
            for years in GRID_EXPERIENCE:
                records.append(
                    {
                        "city": row["city"],
                        "province": row["province"],
                        "tech_direction": row["tech_direction"],
                        "education": education,
                        "edu_years": EDU_YEARS[education],
                        "exp_years": years,
                        "city_tier": city_tier(row["city"]),
                        "job_type_num": job_type_for_experience(years),
                        "skills": direction_skills.get(row["tech_direction"], []),
                    }
                )
    grid = build_feature_frame(spark, records)
    scored = model.transform(grid).select(
        "province", "city", "tech_direction", "education", "exp_years", "prediction", "feature_json"
    )
    insert_rows = []
    for row in scored.collect():
        value = row["prediction"]
        if value is None:
            continue
        salary = round(float(value), 2)
        if salary != salary:  # NaN
            continue
        low = round(max(0.0, salary - rmse), 2)
        high = round(salary + rmse, 2)
        insert_rows.append(
            (
                batch_no,
                None,
                None,
                row["province"],
                row["city"],
                row["tech_direction"],
                int(row["education"]),
                round(float(row["exp_years"]), 1),
                salary,
                low,
                high,
                version,
                row["feature_json"],
                1,
                0,
            )
        )
    if not insert_rows:
        raise RuntimeError("薪资网格预测没有产出")

    MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
    model.write().overwrite().save(str(MODEL_DIR))
    metrics = {
        "batchNo": batch_no,
        "modelVersion": version,
        "rmse": rmse,
        "mae": mae,
        "r2": r2,
        "trainCount": train_count,
        "testCount": test_count,
        "jobType": 3,
        "cityProvince": city_province,
        "directionSkills": direction_skills,
    }
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False), encoding="utf-8")
    from app.spark.predict import invalidate_cache

    invalidate_cache()
    counts = publish(batch_no, [("spark_salary_predict", PREDICT_COLUMNS, insert_rows)])
    prepared.unpersist()
    train.unpersist()
    test.unpersist()
    message = f"RMSE={rmse} MAE={mae} R2={r2} 训练{train_count} 测试{test_count} 预测{counts['spark_salary_predict']}"
    return {
        "taskCode": "salary_regression",
        "inputCount": total,
        "outputCount": counts["spark_salary_predict"],
        "resultMsg": message,
        "params": metrics,
    }
