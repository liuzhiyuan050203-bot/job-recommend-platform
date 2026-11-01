"""内部服务令牌校验.

Spring Boot 调用用户数据或会改数据的接口时必须带 X-Internal-Token。
缺失返回 401，不匹配返回 403。比较使用 hmac.compare_digest，日志不记录令牌内容。
"""

import hmac
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)


def _normalize(path: str) -> str:
    path = path.split("?", 1)[0]
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"


def requires_internal_token(path: str) -> bool:
    """这些路径携带用户数据或会触发写入，必须校验内部令牌."""
    path = _normalize(path)
    if path.startswith("/agent/chat"):
        return True
    if path.startswith("/rag/admin"):
        return True
    if path == "/rag/search":
        return True
    if path.startswith("/recommend/user"):
        return True
    if path.startswith("/api/resume"):
        return True
    if path in {"/recommend/jobs", "/recommend/radar", "/recommend/run", "/spark/run"}:
        return True
    return False


def token_matches(provided: str) -> bool:
    expected = settings.AI_INTERNAL_TOKEN or ""
    if not provided or not expected:
        return False
    try:
        return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
    except Exception:
        return False


class InternalTokenMiddleware(BaseHTTPMiddleware):
    """对受保护路径校验 X-Internal-Token."""

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        if not requires_internal_token(request.url.path):
            return await call_next(request)
        provided = request.headers.get("X-Internal-Token", "")
        if not provided:
            logger.info("拒绝访问 %s：未提供内部令牌", request.url.path)
            return JSONResponse(
                status_code=401,
                content={"code": 401, "msg": "缺少内部访问令牌", "data": None},
            )
        if not token_matches(provided):
            logger.info("拒绝访问 %s：内部令牌无效", request.url.path)
            return JSONResponse(
                status_code=403,
                content={"code": 403, "msg": "内部访问令牌无效", "data": None},
            )
        return await call_next(request)
