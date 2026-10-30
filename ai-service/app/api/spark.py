"""Spark 离线分析与特征计算 API 路由."""

from fastapi import APIRouter

from app.core.response import success
from app.services.spark_service import spark_service

router = APIRouter(prefix="/spark", tags=["Spark Analysis"])


@router.get("", summary="Spark 模块基本信息")
@router.get("/", summary="Spark 模块基本信息")
async def get_spark_info():
    """获取 Spark 离线计算模块的概览与状态."""
    return success(data=spark_service.get_status(), msg="Spark service status retrieved")


@router.get("/status", summary="Spark 状态查询")
async def get_spark_status():
    """获取 Spark 任务引擎详细状态."""
    return success(data=spark_service.get_status(), msg="Spark service status retrieved")


@router.get("/jobs", summary="获取离线任务列表")
async def list_jobs():
    """获取所有预置的 PySpark 离线清洗、聚合与推荐训练任务."""
    return success(data=spark_service.list_jobs(), msg="Spark offline jobs retrieved")
