"""FastAPI 算法与智能体服务入口主程序.

包含应用生命周期管理、CORS 跨域配置、统一异常拦截与模块路由挂载.
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent_router, health_router, rag_router, recommend_router, resume_router, spark_router
from app.core.config import settings
from app.core.response import register_exception_handlers, success
from app.core.security import InternalTokenMiddleware
from app.spark.runner import shutdown as shutdown_batches
from app.spark.session import stop_spark

# 日志基本配置
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# DEBUG 模式下 py4j 会为每条 JVM 调用打一行日志（一次推荐批次十几万行），httpcore/openai 也逐包记录；
# 这些日志在请求进程里同步写盘、争 GIL，压测时会拖慢流式回答，统一收到 WARNING。
for _noisy in ("py4j", "httpcore", "httpcore2", "httpx2", "openai", "urllib3", "multipart", "chromadb", "hpack"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
logger = logging.getLogger("ai_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期事件管理."""
    logger.info(f"Starting {settings.APP_NAME} on {settings.HOST}:{settings.PORT}")
    logger.info(f"Database target: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}")
    logger.info(f"Chroma storage dir: {settings.CHROMA_DIR}")
    logger.info(f"Configured CORS origins: {settings.CORS_ORIGINS}")
    if settings.RAG_SYNC_JOBS_ON_START:
        def _sync_jobs_bg() -> None:
            try:
                from app.rag.ingest import ingest_source

                report = ingest_source("jobs", rebuild=False)
                logger.info("启动时职位知识库增量同步完成: %s", report)
            except Exception:
                logger.exception("启动时职位知识库同步失败，服务继续运行")

        threading.Thread(target=_sync_jobs_bg, name="rag-job-sync", daemon=True).start()
    yield
    shutdown_batches()
    stop_spark()
    logger.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    description="高校就业推荐平台 - AI算法与智能体服务 (PySpark + RAG + LangChain + SSE)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 先注册令牌中间件，再注册 CORS，使跨域头能包住 401/403。
app.add_middleware(InternalTokenMiddleware)
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
app.include_router(resume_router)


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
                "llm_health": "/ai/llm/health",
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
