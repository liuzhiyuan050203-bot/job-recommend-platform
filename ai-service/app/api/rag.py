"""RAG 向量知识库 API 路由."""

from fastapi import APIRouter, Query

from app.core.response import success
from app.services.rag_service import rag_service

router = APIRouter(prefix="/rag", tags=["RAG Knowledge"])


@router.get("", summary="RAG 模块基本信息")
@router.get("/", summary="RAG 模块基本信息")
async def get_rag_info():
    """获取 RAG 模块概览与向量库配置."""
    return success(data=rag_service.get_status(), msg="RAG service status retrieved")


@router.get("/status", summary="RAG 向量库状态")
async def get_rag_status():
    """查询 Chroma 向量库连接与集合状态."""
    return success(data=rag_service.get_status(), msg="RAG service status retrieved")


@router.get("/search", summary="知识库检索")
async def search_knowledge(
    q: str = Query(default="校招政策", description="检索问题或关键字"),
    top_k: int = Query(default=3, ge=1, le=10, description="返回最相似文档数"),
):
    """基于向量相似度检索就业政策、面经与校招指南."""
    results = rag_service.search_knowledge(query=q, top_k=top_k)
    return success(data=results, msg="Knowledge base search completed")
