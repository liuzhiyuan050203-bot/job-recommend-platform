"""简历解析内部接口.

供 Spring Boot 携带 X-Internal-Token 调用，不对学生或企业浏览器开放。
"""

import logging

from fastapi import APIRouter, File, UploadFile

from app.core.response import AppException, success
from app.services.resume_service import parse_resume_bytes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resume", tags=["Resume"])


@router.post("/parse", summary="解析简历中的技能")
async def parse_resume(file: UploadFile = File(...)):
    """抽取正文并对照 skill_tag 返回命中的技能与证据片段."""
    filename = file.filename or ""
    raw = await file.read()
    try:
        data = parse_resume_bytes(filename, raw)
    except ValueError as exc:
        raise AppException(str(exc), code=400) from exc
    logger.info("简历解析完成，命中技能 %s 项", len(data.get("skills") or []))
    return success(data=data, msg="解析完成")
