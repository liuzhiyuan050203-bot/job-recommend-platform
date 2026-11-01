"""加载已保存的薪资模型做实时预测，模型不存在时回退到最近批次。"""

from __future__ import annotations

import json
import math

from app.core.response import AppException
from app.spark.db import find_salary_predict, latest_regression_metrics
from app.spark.dicts import CITY_PROVINCE, EDU_YEARS, city_tier, job_type_for_experience
from app.spark.features import build_feature_frame
from app.spark.paths import METRICS_PATH, MODEL_DIR

_model = None
_metrics = None


def invalidate_cache() -> None:
    global _model, _metrics
    _model = None
    _metrics = None


def model_ready() -> bool:
    return MODEL_DIR.is_dir() and METRICS_PATH.is_file()


def validate_query(city: str | None, tech_direction: str | None, education, experience_years, skills: str | None):
    if city is None or not str(city).strip():
        raise AppException("城市不能为空", code=400)
    if tech_direction is None or not str(tech_direction).strip():
        raise AppException("技术方向不能为空", code=400)
    if education is None:
        raise AppException("学历不能为空", code=400)
    try:
        education = int(education)
    except (TypeError, ValueError):
        raise AppException("学历取值应为1到4", code=400) from None
    if education not in (1, 2, 3, 4):
        raise AppException("学历取值应为1到4", code=400)
    if experience_years is None or experience_years == "":
        raise AppException("工作年限不能为空", code=400)
    try:
        experience_years = float(experience_years)
    except (TypeError, ValueError):
        raise AppException("工作年限不合法", code=400) from None
    if math.isnan(experience_years) or experience_years < 0 or experience_years > 40:
        raise AppException("工作年限不合法", code=400)
    if skills is not None and len(str(skills)) > 200:
        raise AppException("技能参数过长", code=400)
    return str(city).strip(), str(tech_direction).strip(), education, experience_years


def _split_skills(skills: str | None) -> list[str]:
    if not skills:
        return []
    parts = []
    for chunk in str(skills).replace("，", ",").replace("、", ",").replace("/", ",").split(","):
        name = chunk.strip()
        if name:
            parts.append(name)
    return parts


def _load():
    global _model, _metrics
    if _model is not None and _metrics is not None:
        return _model, _metrics
    from pyspark.ml import PipelineModel

    from app.spark.session import get_spark

    get_spark()
    _model = PipelineModel.load(str(MODEL_DIR))
    _metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    return _model, _metrics


def _band(salary: float, rmse: float | None) -> tuple[float, float]:
    if rmse is None:
        delta = max(500.0, salary * 0.15)
    else:
        delta = float(rmse)
    return round(max(0.0, salary - delta), 2), round(salary + delta, 2)


def _from_model(city: str, tech_direction: str, education: int, experience_years: float, skills: str | None) -> dict:
    model, metrics = _load()
    provinces = metrics.get("cityProvince") or {}
    province = provinces.get(city) or CITY_PROVINCE.get(city)
    if not province:
        raise AppException("暂不支持该城市", code=400)
    chosen = _split_skills(skills)
    if not chosen:
        chosen = list((metrics.get("directionSkills") or {}).get(tech_direction) or [])
    spark = __import__("app.spark.session", fromlist=["get_spark"]).get_spark()
    frame = build_feature_frame(
        spark,
        [
            {
                "city": city,
                "province": province,
                "tech_direction": tech_direction,
                "education": education,
                "edu_years": EDU_YEARS[education],
                "exp_years": float(experience_years),
                "city_tier": city_tier(city),
                "job_type_num": job_type_for_experience(experience_years),
                "data_year": float((metrics.get("predictYear") or 2023)),
                "skills": chosen,
            }
        ],
    )
    row = model.transform(frame).select("prediction").collect()[0]
    salary = round(float(row["prediction"]), 2)
    low, high = _band(salary, metrics.get("rmse"))
    return {
        "city": city,
        "province": province,
        "techDirection": tech_direction,
        "education": education,
        "experienceYears": experience_years,
        "skills": chosen,
        "jobType": 3,
        "predictedSalary": salary,
        "ciLow": low,
        "ciHigh": high,
        "modelVersion": metrics.get("modelVersion"),
        "metrics": {
            "rmse": metrics.get("rmse"),
            "mae": metrics.get("mae"),
            "r2": metrics.get("r2"),
        },
        "source": "model",
    }


def _from_table(city: str, tech_direction: str, education: int, experience_years: float) -> dict | None:
    row = find_salary_predict(city, tech_direction, education, experience_years)
    if not row:
        return None
    feature = row.get("feature_json")
    if isinstance(feature, str):
        try:
            feature = json.loads(feature)
        except json.JSONDecodeError:
            feature = None
    skills = []
    if isinstance(feature, dict):
        skills = feature.get("skills") or []
    logged = latest_regression_metrics(row.get("batch_no")) or {}
    return {
        "city": row["city"],
        "province": row["province"],
        "techDirection": row["tech_direction"],
        "education": int(row["education"]),
        "experienceYears": float(row["experience_years"]),
        "skills": skills,
        "jobType": 3,
        "predictedSalary": round(float(row["predicted_salary"]), 2),
        "ciLow": None if row["ci_low"] is None else round(float(row["ci_low"]), 2),
        "ciHigh": None if row["ci_high"] is None else round(float(row["ci_high"]), 2),
        "modelVersion": row["model_version"],
        "metrics": {
            "rmse": logged.get("rmse"),
            "mae": logged.get("mae"),
            "r2": logged.get("r2"),
        },
        "source": "table",
    }


def predict_salary(city, tech_direction, education, experience_years, skills=None, allow_model: bool = True) -> dict:
    city, tech_direction, education, experience_years = validate_query(
        city, tech_direction, education, experience_years, skills
    )
    if allow_model and model_ready():
        try:
            return _from_model(city, tech_direction, education, experience_years, skills)
        except AppException:
            raise
        except Exception as exc:
            fallback = _from_table(city, tech_direction, education, experience_years)
            if fallback:
                fallback["source"] = "table"
                return fallback
            raise AppException(f"薪资预测失败: {exc}", code=500) from exc
    fallback = _from_table(city, tech_direction, education, experience_years)
    if fallback:
        return fallback
    raise AppException("未找到薪资预测结果，请先运行薪资回归任务", code=404)
