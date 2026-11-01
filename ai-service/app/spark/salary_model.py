"""Spark MLlib 随机森林薪资回归（训练在公开真实薪资数据上）。

训练数据：data/real_salary/{boss_2023,job51_2018}.csv（MIT，见 data/REAL_DATA.md）。
平台库里的 DEMO/REAL 职位薪资是估算值，不作为回归真值。
特征：城市 one-hot、方向 one-hot、city_tier、edu_years、exp_years、data_year、技能 CountVectorizer。
预测时 data_year 固定为 2023，吸收 2018/2023 水平漂移。API（predict_salary / 网格表）不变。
生产流水线仍是 PySpark MLlib，不换 Pandas。
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from pyspark.ml import Pipeline
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml.feature import CountVectorizer, OneHotEncoder, StringIndexer, VectorAssembler
from pyspark.ml.regression import RandomForestRegressor
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, DoubleType, IntegerType, StringType, StructField, StructType

from app.spark.datasource import load_sources
from app.spark.db import publish
from app.spark.dicts import CITY_PROVINCE, EDU_YEARS, city_tier, job_type_for_experience
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
PREDICT_YEAR = 2023.0
REAL_DIR = Path(__file__).resolve().parents[3] / "data" / "real_salary"

_TRAIN_SCHEMA = StructType(
    [
        StructField("city", StringType(), False),
        StructField("province", StringType(), False),
        StructField("tech_direction", StringType(), False),
        StructField("education", IntegerType(), False),
        StructField("edu_years", DoubleType(), False),
        StructField("exp_years", DoubleType(), False),
        StructField("city_tier", DoubleType(), False),
        StructField("data_year", DoubleType(), False),
        StructField("skill_arr", ArrayType(StringType()), False),
        StructField("avg_salary", DoubleType(), False),
        StructField("source", StringType(), False),
    ]
)


def _edu_years(code: int) -> float:
    return float(EDU_YEARS.get(int(code), EDU_YEARS[2]))


def _load_real(spark):
    """合并 BOSS 2023 与 51job 2018，附 data_year；技能按逗号拆。"""
    frames = []
    for name, year in (("boss_2023.csv", 2023.0), ("job51_2018.csv", 2018.0)):
        path = REAL_DIR / name
        if not path.is_file():
            raise FileNotFoundError(
                f"缺少真实薪资数据 {path}，请先运行 experiments/salary/prepare_real_salary.py"
            )
        raw = (
            spark.read.option("header", True)
            .option("encoding", "UTF-8")
            .option("escape", '"')
            .csv(str(path))
        )
        framed = (
            raw.select(
                F.col("city").cast("string"),
                F.col("province").cast("string"),
                F.col("tech_direction").cast("string"),
                F.col("education").cast("int"),
                F.col("exp_years").cast("double"),
                F.col("city_tier").cast("double"),
                F.col("avg_salary").cast("double"),
                F.col("skills").cast("string"),
                F.lit(year).alias("data_year"),
                F.lit(name.split("_")[0]).alias("source"),
            )
            .filter(F.col("avg_salary").isNotNull() & (F.col("avg_salary") > 0))
            .filter(F.col("city").isNotNull() & F.col("tech_direction").isNotNull())
            .withColumn(
                "skill_arr",
                F.when(
                    F.col("skills").isNull() | (F.length(F.trim("skills")) == 0),
                    F.array().cast(ArrayType(StringType())),
                ).otherwise(F.split(F.regexp_replace(F.col("skills"), r"[、;/|]+", ","), ",")),
            )
            .withColumn("skill_arr", F.expr("filter(transform(skill_arr, x -> trim(x)), x -> x <> '')"))
            .withColumn(
                "edu_years",
                F.when(F.col("education") == 0, float(EDU_YEARS[0]))
                .when(F.col("education") == 1, float(EDU_YEARS[1]))
                .when(F.col("education") == 2, float(EDU_YEARS[2]))
                .when(F.col("education") == 3, float(EDU_YEARS[3]))
                .when(F.col("education") == 4, float(EDU_YEARS[4]))
                .otherwise(float(EDU_YEARS[2])),
            )
            .select(
                "city",
                "province",
                "tech_direction",
                "education",
                "edu_years",
                "exp_years",
                "city_tier",
                "data_year",
                "skill_arr",
                "avg_salary",
                "source",
            )
        )
        frames.append(framed)
    out = frames[0]
    for part in frames[1:]:
        out = out.unionByName(part)
    return out


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
    skills = CountVectorizer(inputCol="skill_arr", outputCol="skill_vec", minDF=5.0, vocabSize=128)
    assembler = VectorAssembler(
        inputCols=["city_vec", "dir_vec", "edu_years", "exp_years", "city_tier", "data_year", "skill_vec"],
        outputCol="features",
        handleInvalid="keep",
    )
    regressor = RandomForestRegressor(
        featuresCol="features",
        labelCol="avg_salary",
        numTrees=100,
        maxDepth=10,
        seed=42,
        subsamplingRate=0.8,
        featureSubsetStrategy="onethird",
        minInstancesPerNode=3,
    )
    return Pipeline(
        stages=[city_indexer, direction_indexer, city_encoder, direction_encoder, skills, assembler, regressor]
    )


def _score(frame, name: str) -> float:
    evaluator = RegressionEvaluator(labelCol="avg_salary", predictionCol="prediction", metricName=name)
    return float(evaluator.evaluate(frame))


def run_salary_regression(batch_no: str) -> dict:
    spark = get_spark()
    prepared = _load_real(spark).cache()
    total = prepared.count()
    if total < 20:
        prepared.unpersist()
        raise RuntimeError(f"可用于回归的真实薪资样本只有 {total} 条")
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
    version = f"rf-real-{batch_no}"
    if len(version) > 32:
        version = f"rf-r-{batch_no}"[:32]

    # 网格仍按平台在架职位的城市×方向展开，保证看板有覆盖；技能取各方向在真实数据上的高频标签。
    jobs, _tags = load_sources(spark)
    pair_rows = jobs.select("city", "province", "tech_direction").distinct().collect()
    if not pair_rows:
        pair_rows = [
            type("R", (), {"city": c, "province": p, "tech_direction": d})()
            for c, p in list(CITY_PROVINCE.items())[:8]
            for d in ("后端开发", "前端开发", "人工智能", "算法工程")
        ]
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
                        "data_year": PREDICT_YEAR,
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
        if salary != salary:
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
        "trainSource": "pooled_real(boss_2023+job51_2018)",
        "predictYear": PREDICT_YEAR,
        "jobType": 3,
        "cityProvince": city_province,
        "directionSkills": direction_skills,
        "note": "平台职位薪资为估算，训练用 MIT 公开真实月薪；预测 data_year=2023",
    }
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False), encoding="utf-8")
    from app.spark.predict import invalidate_cache

    invalidate_cache()
    counts = publish(batch_no, [("spark_salary_predict", PREDICT_COLUMNS, insert_rows)])
    prepared.unpersist()
    train.unpersist()
    test.unpersist()
    message = (
        f"真实薪资 RF R2={r2} RMSE={rmse} MAE={mae} 训练{train_count} 测试{test_count} "
        f"预测{counts['spark_salary_predict']}（data_year={int(PREDICT_YEAR)}）"
    )
    return {
        "taskCode": "salary_regression",
        "inputCount": total,
        "outputCount": counts["spark_salary_predict"],
        "resultMsg": message,
        "params": metrics,
    }
