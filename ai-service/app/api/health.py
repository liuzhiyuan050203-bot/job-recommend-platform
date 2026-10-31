"""服务健康检查接口."""

from fastapi import APIRouter

from app.core.config import settings
from app.core.response import success

router = APIRouter(tags=["Health"])


@router.get("/health", summary="健康检查接口")
async def health_check():
    """返回服务运行状态及基本配置信息."""
    return success(
        data={
            "status": "UP",
            "service": settings.APP_NAME,
            "env": settings.APP_ENV,
            "port": settings.PORT,
        },
        msg="Service is healthy and ready",
    )


@router.get("/ai/llm/health", summary="LLM 与 Embedding 健康检查接口")
@router.get("/health/llm", summary="LLM 与 Embedding 健康检查接口 (别名)")
async def llm_health_check():
    """返回大模型基础设施及向量嵌入模型的健康探活状态与元信息."""
    from app.core.embedding import health as get_embedding_health
    from app.core.llm import health as get_llm_health

    l_health = get_llm_health()
    e_health = get_embedding_health()

    is_healthy = l_health.get("available", False) and e_health.get("available", False)
    status_str = "UP" if is_healthy else ("DEGRADED" if e_health.get("available") else "DOWN")

    return success(
        data={
            "status": status_str,
            "service": settings.APP_NAME,
            "llm": l_health,
            "embedding": e_health,
        },
        msg="LLM and embedding infrastructure status retrieved",
    )
