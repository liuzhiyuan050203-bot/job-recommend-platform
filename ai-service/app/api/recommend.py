"""推荐算法 API。"""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.response import AppException, success
from app.services.recommend_service import recommend_service
from app.spark.runner import SparkBusyError, submit_async

router = APIRouter(prefix="/recommend", tags=["Recommendation"])


class RunBody(BaseModel):
    tasks: Optional[list[str]] = Field(default=None, description="保留字段，当前只跑 recommend")


@router.get("", summary="推荐模块基本信息")
@router.get("/", summary="推荐模块基本信息")
async def get_recommend_info():
    return success(data=recommend_service.get_status(), msg="Recommend service status retrieved")


@router.get("/status", summary="推荐模块状态")
async def get_recommend_status():
    return success(data=recommend_service.get_status(), msg="Recommend service status retrieved")


@router.post("/run", summary="提交混合推荐")
async def run_recommend(body: Optional[RunBody] = None):
    """后台执行混合推荐，立即返回批次号。已有任务时返回 409。"""
    del body
    try:
        payload = submit_async(["recommend"])
    except SparkBusyError as exc:
        raise AppException(str(exc), code=409) from exc
    except ValueError as exc:
        raise AppException(str(exc), code=400) from exc
    return success(data=payload, msg="推荐任务已提交")


@router.get("/user/{user_id}", summary="单用户实时推荐")
def recommend_user(
    user_id: int,
    top_k: int = Query(default=10, ge=1, le=50, description="推荐条数"),
):
    """用最近一批协同过滤矩阵加实时内容匹配，适合还没有离线结果的学生。"""
    if user_id <= 0:
        raise AppException("学生编号不合法", code=400)
    data = recommend_service.recommend_user(user_id, top_k)
    return success(data=data, msg="推荐完成")


@router.get("/eval", summary="最近一次离线评估")
def recommend_eval():
    return success(data=recommend_service.evaluation(), msg="推荐评估")


@router.get("/similar/{job_id}", summary="相似职位")
def recommend_similar(
    job_id: int,
    top_k: int = Query(default=6, ge=1, le=50, description="返回条数"),
):
    if job_id <= 0:
        raise AppException("职位编号不合法", code=400)
    data = recommend_service.similar(job_id, top_k)
    return success(data=data, msg="相似职位")


@router.get("/jobs", summary="学生岗位推荐列表")
def get_job_recommendations(
    student_id: int = Query(default=1, ge=1, description="学生ID"),
    top_k: int = Query(default=10, ge=1, le=50, description="推荐数量"),
):
    """与 /recommend/user/{id} 相同，保留原路径。"""
    result = recommend_service.recommend_user(student_id, top_k)
    return success(data=result, msg="Job recommendations generated successfully")


@router.get("/radar", summary="学生技能雷达图数据")
def get_skill_radar(student_id: int = Query(default=1, ge=1, description="学生ID")):
    radar_data = recommend_service.calculate_skill_radar(student_id)
    return success(data=radar_data, msg="Skill radar data retrieved successfully")
