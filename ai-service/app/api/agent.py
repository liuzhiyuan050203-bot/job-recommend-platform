"""智能体与 SSE 流式对话 API 路由."""

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.response import success
from app.services.agent_service import agent_service

router = APIRouter(prefix="/agent", tags=["AI Agent"])


@router.get("", summary="Agent 模块基本信息")
@router.get("/", summary="Agent 模块基本信息")
async def get_agent_info():
    """获取智能体模块状态与能力说明."""
    return success(data=agent_service.get_status(), msg="Agent service status retrieved")


@router.get("/status", summary="Agent 状态查询")
async def get_agent_status():
    """查询智能体模块状态."""
    return success(data=agent_service.get_status(), msg="Agent service status retrieved")


@router.get("/stream-demo", summary="Agent SSE 流式对话演示")
async def stream_demo(
    q: str = Query(default="请推荐适合计算机专业应届生的就业方向", description="用户问题"),
    role: str = Query(default="student", description="角色: student / company / admin"),
):
    """Server-Sent Events (SSE) 流式传输演示接口.

    逐条输出 data: {...}\\n\\n JSON 片段，最后以 data: [DONE]\\n\\n 结束.
    前端通过 EventSource 或 fetch+ReadableStream 直接消费.
    """
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
