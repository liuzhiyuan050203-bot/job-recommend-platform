"""智能体对话接口。

/agent/chat 与 /agent/chat/stream 需要内部令牌，以及调用方传入的用户编号和角色。
/agent/stream-demo 保持原有演示，不访问数据库。
"""

import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.agent.chat import iter_events
from app.agent.tools import Caller
from app.core.response import AppException, success
from app.services.agent_service import agent_service
from app.spark.db import connect

router = APIRouter(prefix="/agent", tags=["AI Agent"])

_ROLE_BY_CODE = {1: "student", 2: "company", 3: "admin"}


class HistoryItem(BaseModel):
    role: str
    content: str = ""


class ChatBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    history: list[HistoryItem] = Field(default_factory=list)
    session_id: int | None = None


def resolve_caller(request: Request) -> Caller:
    """身份来自受信任的请求头，并与 sys_user 核对，不接受问题文本里的身份。"""
    raw_id = (request.headers.get("X-User-Id") or "").strip()
    role = (request.headers.get("X-User-Role") or "").strip().lower()
    if not raw_id.isdigit() or role not in _ROLE_BY_CODE.values():
        raise StarletteHTTPException(status_code=400, detail="缺少用户身份")
    user_id = int(raw_id)
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, role, status, deleted, nickname FROM sys_user WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row or int(row["deleted"] or 0) == 1 or int(row["status"]) != 1:
        raise StarletteHTTPException(status_code=403, detail="用户不可用")
    expected = _ROLE_BY_CODE.get(int(row["role"]))
    if expected != role:
        raise StarletteHTTPException(status_code=403, detail="用户身份与账号角色不一致")
    return Caller(user_id=user_id, role=role, nickname=row.get("nickname") or "")


@router.get("", summary="Agent 模块基本信息")
@router.get("/", summary="Agent 模块基本信息")
async def get_agent_info():
    return success(data=agent_service.get_status(), msg="Agent service status retrieved")


@router.get("/status", summary="Agent 状态查询")
async def get_agent_status():
    return success(data=agent_service.get_status(), msg="Agent service status retrieved")


@router.get("/stream-demo", summary="Agent SSE 流式对话演示")
async def stream_demo(
    q: str = Query(default="请推荐适合计算机专业应届生的就业方向", description="用户问题"),
    role: str = Query(default="student", description="角色: student / company / admin"),
):
    """保留原演示流，不检索知识库，也不校验内部令牌。"""
    return StreamingResponse(
        agent_service.generate_stream_chunks(query=q, role=role),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


def _stream_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Type": "text/event-stream; charset=utf-8",
    }


@router.post("/chat/stream", summary="角色助手流式对话")
async def chat_stream(body: ChatBody, request: Request):
    caller = resolve_caller(request)
    history = [item.model_dump() for item in body.history]
    return StreamingResponse(
        iter_events(body.question.strip(), caller, history, body.session_id),
        media_type="text/event-stream",
        headers=_stream_headers(),
    )


@router.post("/chat", summary="角色助手同步对话")
async def chat(body: ChatBody, request: Request):
    caller = resolve_caller(request)
    history = [item.model_dump() for item in body.history]
    done = None
    async for line in iter_events(body.question.strip(), caller, history, body.session_id):
        if not line.startswith("data: ") or line.startswith("data: [DONE]"):
            continue
        payload = json.loads(line[len("data: ") :].strip())
        if payload.get("type") == "done":
            done = payload
        elif payload.get("type") == "error" and done is None:
            raise AppException(payload.get("msg") or "对话失败", code=500)
    if not done:
        raise AppException("对话失败", code=500)
    done.pop("type", None)
    return success(data=done, msg="对话完成")
