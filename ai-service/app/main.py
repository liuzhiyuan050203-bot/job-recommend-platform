"""FastAPI 算法与智能体服务入口主程序.

包含应用生命周期管理、CORS 跨域配置、统一异常拦截与模块路由挂载.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent_router, health_router, rag_router, recommend_router, spark_router
from app.core.config import settings
from app.core.response import register_exception_handlers, success

# 日志基本配置
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ai_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期事件管理."""
    logger.info(f"Starting {settings.APP_NAME} on {settings.HOST}:{settings.PORT}")
    logger.info(f"Database target: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}")
    logger.info(f"Chroma storage dir: {settings.CHROMA_DIR}")
    logger.info(f"Configured CORS origins: {settings.CORS_ORIGINS}")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    description="高校就业推荐平台 - AI算法与智能体服务 (PySpark + RAG + LangChain + SSE)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 跨域中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册统一全局异常处理
register_exception_handlers(app)

# 挂载 API 路由
app.include_router(health_router)
app.include_router(spark_router)
app.include_router(recommend_router)
app.include_router(rag_router)
app.include_router(agent_router)


@app.get("/", summary="服务欢迎页")
async def root():
    """根路径引导接口."""
    return success(
        data={
            "app_name": settings.APP_NAME,
            "version": "1.0.0",
            "docs": "/docs",
            "endpoints": {
                "health": "/health",
                "spark": "/spark",
                "recommend": "/recommend",
                "rag": "/rag",
                "agent": "/agent",
                "agent_stream_demo": "/agent/stream-demo?q=计算机专业就业方向",
            },
        },
        msg="高校就业推荐平台算法与智能体服务正常运行中",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
