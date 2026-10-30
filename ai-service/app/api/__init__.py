"""API 路由导出."""

from app.api.agent import router as agent_router
from app.api.health import router as health_router
from app.api.rag import router as rag_router
from app.api.recommend import router as recommend_router
from app.api.spark import router as spark_router

__all__ = [
    "health_router",
    "spark_router",
    "recommend_router",
    "rag_router",
    "agent_router",
]
