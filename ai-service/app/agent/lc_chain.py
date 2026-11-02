"""对话编排里用到的 LangChain 组件。

* :class:`SessionHistory` —— ``BaseChatMessageHistory``。后端会把同一会话（ai_message）最近几条消息随请求
  带过来；没带而给了 session_id 时，直接从 ai_message 读（只读，落库仍由后端负责）。
* :func:`role_tools` —— 每个角色允许的工具包装成 ``StructuredTool``（``response_format="content_and_artifact"``，
  ``return_direct=True``），身份来自请求上下文，不接受模型给的 user_id / role。
* :func:`build_role_agent` —— ``langchain.agents.create_agent`` 建的三类角色工具调用 Agent。
* :func:`build_router` —— ``RunnableBranch``：先跑确定性规则路由（越权拒答、政策类检索类型），
  在线且允许工具调用时再交给 Agent 选工具；Agent 没有合法调用、或出错时退回规则结果。
* :func:`build_context` —— ``RunnableParallel``：知识库检索与工具执行并行。
* :func:`build_answer_chain` —— LCEL：``RunnableParallel(system, prompt) | ChatPromptTemplate | llm | StrOutputParser``，
  对话接口用 ``.astream`` 逐段输出。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableBranch, RunnableLambda, RunnableParallel
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.agent.router import Route, ToolRequest, allowed_tool_names, route
from app.agent.tools import Caller, execute, render

logger = logging.getLogger(__name__)

HISTORY_TURNS = 4
HISTORY_CHARS = 200
AGENT_MAX_TOOLS = 2


# --------------------------------------------------------------------------- 记忆


class SessionHistory(BaseChatMessageHistory):
    """一次请求内的会话记忆。消息来自请求体 history，或按 session_id 读 ai_message。"""

    def __init__(
        self,
        session_id: int | None = None,
        user_id: int | None = None,
        provided: list[dict] | None = None,
        question: str = "",
    ) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self._messages: list[BaseMessage] = []
        items = [item for item in (provided or []) if str(item.get("content") or "").strip()]
        if not items and session_id and user_id:
            items = self._load(session_id, user_id, question)
        for item in items:
            self.add_message(_to_message(item))

    @property
    def messages(self) -> list[BaseMessage]:  # type: ignore[override]
        return list(self._messages)

    def add_message(self, message: BaseMessage) -> None:
        if message is not None:
            self._messages.append(message)

    def clear(self) -> None:
        self._messages = []

    def recent(self, turns: int = HISTORY_TURNS, chars: int = HISTORY_CHARS) -> list[dict[str, str]]:
        """最近几条用户/助手消息（裁剪后的 dict，供提示词预算使用）。"""
        cleaned = []
        for message in self._messages:
            if isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            else:
                continue
            content = str(message.content or "").strip()
            if content:
                cleaned.append({"role": role, "content": content[:chars]})
        return cleaned[-turns:]

    @staticmethod
    def _load(session_id: int, user_id: int, question: str) -> list[dict]:
        from app.spark.db import connect

        try:
            conn = connect()
        except Exception:
            logger.exception("连接数据库读取会话记忆失败")
            return []
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.msg_role, m.content FROM ai_message m JOIN ai_session s ON s.id = m.session_id "
                    "WHERE m.session_id = %s AND s.user_id = %s AND m.deleted = 0 AND s.deleted = 0 "
                    "ORDER BY m.id DESC LIMIT %s",
                    (int(session_id), int(user_id), HISTORY_TURNS + 1),
                )
                rows = list(cur.fetchall())
        except Exception:
            logger.exception("读取 ai_message 失败")
            return []
        finally:
            conn.close()
        rows.reverse()
        # 后端先写入本轮提问再调用本服务，去掉与当前问题相同的最后一条
        if rows and rows[-1]["msg_role"] == "user" and str(rows[-1]["content"] or "").strip() == question.strip():
            rows = rows[:-1]
        return [{"role": row["msg_role"], "content": row["content"] or ""} for row in rows]


def _to_message(item: dict) -> BaseMessage | None:
    role = str(item.get("role") or "")
    content = str(item.get("content") or "")
    if role == "user":
        return HumanMessage(content=content)
    if role == "assistant":
        return AIMessage(content=content)
    return None


# --------------------------------------------------------------------------- 工具


class SearchArgs(BaseModel):
    keyword: str = Field(default="", description="职位关键词")
    city: str = Field(default="", description="城市")
    direction: str = Field(default="", description="技术方向")
    education: int | None = Field(default=None, description="学历要求编码")
    salary_min: int | None = Field(default=None, description="最低月薪（元）")
    limit: int = 5


class LimitArgs(BaseModel):
    limit: int = 5


class PredictArgs(BaseModel):
    city: str = ""
    direction: str = ""
    education: int | None = None
    experience_years: float | None = None


class GapArgs(BaseModel):
    job_id: int | None = None
    keyword: str = ""


class JdArgs(BaseModel):
    title: str = ""
    direction: str = ""
    city: str = ""
    skills: str = ""
    highlights: str = ""


class PolishArgs(BaseModel):
    text: str = ""


class ScreenArgs(BaseModel):
    job_id: int | None = None


class SalaryArgs(BaseModel):
    city: str = ""
    direction: str = ""


class TrendArgs(BaseModel):
    skill: str = ""
    top_n: int = 5


class TopArgs(BaseModel):
    top_n: int = 8


class EmptyArgs(BaseModel):
    note: str = Field(default="", description="留空")


TOOL_CATALOG: dict[str, tuple[str, type[BaseModel]]] = {
    "search_jobs": ("按城市、方向和关键词检索在架职位", SearchArgs),
    "get_my_recommendations": ("读取当前学生的职位推荐", LimitArgs),
    "predict_salary": ("按城市、方向、学历和年限预测月薪", PredictArgs),
    "analyze_resume_gap": ("对照职位看当前学生缺哪些技能", GapArgs),
    "generate_job_description": ("整理生成职位描述所需的要点", JdArgs),
    "polish_job_description": ("接收需要润色的职位描述", PolishArgs),
    "screen_applicants": ("按技能匹配排序本公司某职位的候选人", ScreenArgs),
    "list_my_jobs": ("列出当前企业发布的职位", LimitArgs),
    "salary_stats": ("查询城市或方向的平均月薪", SalaryArgs),
    "tech_trend": ("查询需求环比增长最快的技术", TrendArgs),
    "region_distribution": ("查询职位数最多的省份", TopArgs),
    "city_distribution": ("查询在架职位数最多的城市", TopArgs),
    "recommend_eval": ("读取推荐离线评估指标", EmptyArgs),
    "platform_overview": ("读取用户、企业和职位数量", EmptyArgs),
}

ROLE_AGENT_PROMPTS = {
    "student": "你是高校就业推荐平台的学生就业助手。需要查职位、推荐、薪资或技能差距时调用一个工具，不要直接回答。",
    "company": "你是高校就业推荐平台的企业招聘助手。需要生成或润色职位描述、筛选候选人、查看本公司职位时调用一个工具，不要直接回答。",
    "admin": "你是高校就业推荐平台的管理员数据助手。需要统计数字时调用一个工具，不要直接回答，不要编造数字。",
}


def _clean_args(args: Any) -> dict:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    if not isinstance(args, dict):
        return {}
    args = {key: value for key, value in args.items() if key not in {"user_id", "role", "note"}}
    return args


def role_tools(caller: Caller) -> list[StructuredTool]:
    """当前身份可用的工具。函数体直接执行受控工具，身份取自 caller。"""
    allowed = allowed_tool_names(caller.role)
    tools = []
    for name, (description, schema) in TOOL_CATALOG.items():
        if name not in allowed:
            continue

        def _run(_name: str = name, **kwargs: Any) -> tuple[str, dict]:
            args = _clean_args(kwargs)
            result = execute(_name, args, caller)
            prompt_text, _summary = render(_name, result)
            return prompt_text, {"name": _name, "args": args, "result": result}

        tools.append(
            StructuredTool.from_function(
                func=_run,
                name=name,
                description=description,
                args_schema=schema,
                return_direct=True,
                response_format="content_and_artifact",
            )
        )
    return tools


def build_role_agent(caller: Caller, llm=None):
    """三类角色共用的工具调用 Agent，工具集按角色白名单裁剪。"""
    from langchain.agents import create_agent

    from app.core.llm import get_llm

    tools = role_tools(caller)
    if not tools:
        return None
    model = llm or get_llm(streaming=False, max_tokens=160)
    return create_agent(model, tools, system_prompt=ROLE_AGENT_PROMPTS.get(caller.role, ROLE_AGENT_PROMPTS["student"]))


def agent_tool_requests(question: str, caller: Caller, llm=None) -> list[ToolRequest] | None:
    """运行角色 Agent，取出它实际调用过的工具（含已执行的结果）。没有合法调用时返回 None。"""
    agent = build_role_agent(caller, llm)
    if agent is None:
        return None
    state = agent.invoke({"messages": [HumanMessage(content=question[:400])]}, {"recursion_limit": 4})
    allowed = allowed_tool_names(caller.role)
    requests: list[ToolRequest] = []
    for message in state.get("messages", []):
        if not isinstance(message, ToolMessage):
            continue
        artifact = message.artifact if isinstance(message.artifact, dict) else None
        if not artifact or artifact.get("name") not in allowed:
            continue
        requests.append(ToolRequest(name=artifact["name"], args=artifact.get("args") or {}, result=artifact.get("result")))
        if len(requests) >= AGENT_MAX_TOOLS:
            break
    return requests or None


# --------------------------------------------------------------------------- 路由


def doc_types_for_tools(tools: list[ToolRequest]) -> list[int]:
    names = {item.name for item in tools}
    if "search_jobs" in names:
        return [7]
    if "analyze_resume_gap" in names or "polish_job_description" in names or "generate_job_description" in names:
        return [5, 4]
    return []


def build_router(caller: Caller, use_agent: bool) -> Runnable:
    """输入问题字符串，输出 Route。规则路由永远先跑：越权拒答不交给模型。"""
    rule = RunnableLambda(lambda question: route(question, caller.role), name="rule_router")

    def agent_route(question: str) -> Route:
        decided = route(question, caller.role)
        if decided.refusal:
            return decided
        try:
            picked = agent_tool_requests(question, caller)
        except Exception:
            logger.exception("Agent 工具调用失败，改用规则路由")
            picked = None
        if not picked:
            return decided
        return Route(tools=picked, doc_types=doc_types_for_tools(picked), instruction="")

    return RunnableBranch(
        (lambda _question: use_agent, RunnableLambda(agent_route, name="role_agent")),
        rule,
    )


# --------------------------------------------------------------------------- 检索 + 工具


def build_context(caller: Caller, fetch_chunks) -> Runnable:
    """输入 {question, doc_types, tools}，并行得到 {chunks, tool_results}。"""

    def retrieve(inputs: dict) -> list[dict]:
        doc_types = inputs.get("doc_types") or []
        return fetch_chunks(inputs["question"], doc_types) if doc_types else []

    def run_tools(inputs: dict) -> list[tuple[ToolRequest, dict]]:
        done = []
        for request in inputs.get("tools") or []:
            result = request.result if request.result is not None else execute(request.name, request.args, caller)
            done.append((request, result or {"ok": False, "message": "工具无结果"}))
            if (result or {}).get("denied"):
                break
        return done

    return RunnableParallel(
        chunks=RunnableLambda(retrieve, name="knowledge_retriever"),
        tool_results=RunnableLambda(run_tools, name="role_tools"),
    )


# --------------------------------------------------------------------------- 生成

ANSWER_PROMPT = ChatPromptTemplate.from_messages([("system", "{system}"), ("human", "{prompt}")])


def build_answer_chain(system_fn, prompt_fn, llm) -> Runnable:
    """LCEL 回答链。输入 {agent, question, history, chunks, tool_text, instruction}。"""
    prepare = RunnableParallel(
        system=RunnableLambda(lambda x: system_fn(x["agent"], bool(x["chunks"]))),
        prompt=RunnableLambda(
            lambda x: prompt_fn(x["question"], x["history"], x["chunks"], x["tool_text"], x["instruction"])
        ),
    )
    return prepare | ANSWER_PROMPT | llm | StrOutputParser()
