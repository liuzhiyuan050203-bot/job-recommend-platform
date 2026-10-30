"""推荐算法 API 路由."""

from fastapi import APIRouter, Query

from app.core.response import success
from app.services.recommend_service import recommend_service

router = APIRouter(prefix="/recommend", tags=["Recommendation"])


@router.get("", summary="推荐模块基本信息")
@router.get("/", summary="推荐模块基本信息")
async def get_recommend_info():
    """获取推荐引擎模块概览."""
    return success(data=recommend_service.get_status(), msg="Recommend service status retrieved")


@router.get("/status", summary="推荐模块状态")
async def get_recommend_status():
    """查询推荐模块就绪状态."""
    return success(data=recommend_service.get_status(), msg="Recommend service status retrieved")


@router.get("/jobs", summary="学生岗位推荐列表")
async def get_job_recommendations(
    student_id: int = Query(default=1, description="学生ID"),
    top_k: int = Query(default=10, ge=1, le=50, description="推荐数量"),
):
    """基于协同过滤与技能标签为学生生成岗位推荐列表."""
    result = recommend_service.get_recommendations(student_id=student_id, top_k=top_k)
    return success(data=result, msg="Job recommendations generated successfully")


@router.get("/radar", summary="学生技能雷达图数据")
async def get_skill_radar(student_id: int = Query(default=1, description="学生ID")):
    """获取指定学生的技能维度得分与雷达图数据."""
    radar_data = recommend_service.calculate_skill_radar(student_id=student_id)
    return success(data=radar_data, msg="Skill radar data retrieved successfully")
