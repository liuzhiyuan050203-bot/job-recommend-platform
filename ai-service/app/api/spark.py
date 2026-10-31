"""Spark 离线分析与薪资预测 API。"""

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.response import AppException, success
from app.services.spark_service import spark_service
from app.spark.db import list_tasks, tasks_of_batch
from app.spark.predict import predict_salary
from app.spark.runner import SparkBusyError, call_exclusive, is_running, normalize_tasks, submit_async

router = APIRouter(prefix="/spark", tags=["Spark Analysis"])


class RunBody(BaseModel):
    tasks: Optional[List[str]] = Field(default=None, description="clean、aggregate、salary_regression")


def _status_payload() -> dict:
    data = spark_service.get_status()
    data["running"] = is_running()
    return data


@router.get("", summary="Spark 模块基本信息")
@router.get("/", summary="Spark 模块基本信息")
async def get_spark_info():
    """获取 Spark 离线计算模块的概览与状态."""
    return success(data=_status_payload(), msg="Spark service status retrieved")


@router.get("/status", summary="Spark 状态查询")
async def get_spark_status():
    """获取 Spark 任务引擎详细状态."""
    return success(data=_status_payload(), msg="Spark service status retrieved")


@router.get("/jobs", summary="获取离线任务列表")
async def list_jobs():
    """获取所有预置的 PySpark 离线清洗、聚合与推荐训练任务."""
    return success(data=spark_service.list_jobs(), msg="Spark offline jobs retrieved")


@router.post("/run", summary="提交离线分析")
async def run_spark(body: Optional[RunBody] = None):
    """后台执行清洗、聚合或薪资回归，立即返回批次号。"""
    raw_tasks = None if body is None else body.tasks
    try:
        names = normalize_tasks(raw_tasks)
        payload = submit_async(names)
    except ValueError as exc:
        raise AppException(str(exc), code=400) from exc
    except SparkBusyError as exc:
        raise AppException(str(exc), code=409) from exc
    return success(data=payload, msg="分析任务已提交")


@router.get("/tasks", summary="任务日志分页")
def list_spark_tasks(current: int = 1, size: int = 10, batch_no: Optional[str] = None):
    """按批次过滤任务日志，默认最近一页。"""
    if current < 1 or size < 1:
        raise AppException("分页参数不合法", code=400)
    return success(data=list_tasks(current, size, batch_no))


@router.get("/tasks/{batch_no}", summary="按批次查看任务")
def get_spark_batch(batch_no: str):
    rows = tasks_of_batch(batch_no)
    if not rows:
        raise AppException("批次不存在", code=404)
    return success(data={"batchNo": batch_no, "tasks": rows})


@router.get("/salary/predict", summary="薪资预测")
def salary_predict(
    city: str = "",
    tech_direction: str = "",
    education: Optional[int] = None,
    experience_years: Optional[float] = None,
    skills: Optional[str] = None,
):
    """优先用已保存模型预测；模型不存在或任务占用 Spark 时回退最近批次。"""

    def invoke(allow_model: bool):
        return predict_salary(city, tech_direction, education, experience_years, skills, allow_model=allow_model)

    try:
        data = call_exclusive(lambda: invoke(True))
    except AppException:
        raise
    if data is None:
        try:
            data = invoke(False)
        except AppException as exc:
            if exc.code == 404:
                raise AppException("已有任务运行中", code=409) from exc
            raise
    return success(data=data, msg="薪资预测完成")
