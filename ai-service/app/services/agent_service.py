"""LangChain 多角色智能体服务 (占位实现).

职责:
1. 支撑学生、企业、管理员三种角色的就业智能助手
2. 调度 RAG 向量检索与推荐算法工具链
3. 生成流式输出 (SSE 传输协议)
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional

logger = logging.getLogger(__name__)


class AgentService:
    """智能体业务服务类."""

    def __init__(self) -> None:
        self.roles = ["student", "company", "admin"]

    def get_status(self) -> Dict[str, Any]:
        """获取智能体模块状态."""
        return {
            "module": "agent",
            "status": "READY",
            "supported_roles": self.roles,
            "stream_protocol": "Server-Sent Events (SSE)",
            "description": "基于 LangChain 的多角色就业咨询与求职辅导智能体",
        }

    async def generate_stream_chunks(
        self,
        query: str,
        role: str = "student",
    ) -> AsyncGenerator[str, None]:
        """生成流式 SSE 事件片段，以 JSON 格式输出，最终以 [DONE] 结束."""
        logger.info(f"Generating stream response for role={role}, query={query}")

        steps = [
            {
                "step": 1,
                "role": role,
                "thought": "正在意图识别与解析用户问题...",
                "content": f"您好！我是高校就业智能助手（针对【{role}】角色提供支持）。收到您的提问：「{query}」\n",
            },
            {
                "step": 2,
                "role": role,
                "thought": "正在调用 RAG 知识库检索校招政策与高频面试要点...",
                "content": "【检索结论】根据最新就业政策与企业用人画像分析，当前计算机与软件工程方向对应届生的核心关注点集中在：\n"
                           "1. 扎实的基础能力（数据结构、网络与操作系统）；\n"
                           "2. 实际业务落地与主流框架综合实践能力；\n",
            },
            {
                "step": 3,
                "role": role,
                "thought": "正在调用 Spark / 推荐引擎结合上下文生成建议...",
                "content": "【求职策略建议】建议在简历中突出 Spring Boot、微服务或大数据/AI落地项目实践，并结合平台技能雷达图查漏补缺。\n",
            },
            {
                "step": 4,
                "role": role,
                "thought": "智能体总结完成",
                "content": "祝您求职顺利！如需针对特定岗位（如Java后端、大数据、前端）的深度测评，请随时继续向我提问。",
            },
        ]

        for item in steps:
            data_str = json.dumps(item, ensure_ascii=False)
            yield f"data: {data_str}\n\n"
            await asyncio.sleep(0.2)

        # SSE 标准结束标记
        yield "data: [DONE]\n\n"


agent_service = AgentService()
