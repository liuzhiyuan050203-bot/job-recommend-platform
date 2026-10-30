"""统一响应结构与全局异常处理.

保证与 Spring Boot 后端 Result 结构 ({code, msg, data}) 完全一致.
code 200 表示成功，非 200 表示各类业务/系统异常.
"""

import logging
from typing import Any, Generic, Optional, TypeVar

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("ai_service")

T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    """与 Spring Boot 后端对齐的统一响应模型."""

    code: int = 200
    msg: str = "success"
    data: Optional[T] = None


class AppException(Exception):
    """自定义业务异常."""

    def __init__(
        self,
        msg: str = "业务处理异常",
        code: int = 500,
        data: Any = None,
    ):
        super().__init__(msg)
        self.code = code
        self.msg = msg
        self.data = data


def success(data: Any = None, msg: str = "success") -> dict:
    """构建成功响应字典."""
    return {
        "code": 200,
        "msg": msg,
        "data": data,
    }


def error(code: int = 500, msg: str = "error", data: Any = None) -> dict:
    """构建错误响应字典."""
    return {
        "code": code,
        "msg": msg,
        "data": data,
    }


def register_exception_handlers(app: FastAPI) -> None:
    """为 FastAPI 应用注册全局异常捕获器，统一输出 {code, msg, data} 格式."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(f"Business Exception at {request.url.path}: code={exc.code}, msg={exc.msg}")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=error(code=exc.code, msg=exc.msg, data=exc.data),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.warning(f"HTTP Exception at {request.url.path}: status={exc.status_code}, detail={exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content=error(code=exc.status_code, msg=str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning(f"Validation Error at {request.url.path}: {exc.errors()}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error(code=400, msg="请求参数校验失败", data=exc.errors()),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled Exception at {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error(code=500, msg=f"服务器内部异常: {str(exc)}"),
        )
