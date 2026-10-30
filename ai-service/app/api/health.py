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
