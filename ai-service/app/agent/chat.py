"""学生、企业、管理员三类助手的对话编排与 SSE 输出。

本地小模型默认走关键词路由；LLM_TOOL_CALLING=true 时先尝试 LangChain 工具调用，
没有合法调用再退回路由。工具结果和知识库切片一起交给模型生成最终回答。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from app.agent.router import Route, ToolRequest, allowed_tool_names, route
from app.agent.tools import Caller, execute, render
from app.core.config import settings
from app.core.llm import OfflineGenerator, get_llm, is_available
from app.rag.retrieve import fetch_chunks

logger = logging.getLogger(__name__)

AGENT_NAMES = {
    "student": "学生就业助手",
    "company": "企业招聘助手",
    "admin": "管理员数据助手",
}
ANSWER_TOKENS = 500
PROMPT_CHAR_BUDGET = 1500


def use_model_tools() -> bool:
    """auto 遇到本机或 8B 及以下模型时不用工具调用，改走确定性路由。"""
    mode = str(settings.LLM_TOOL_CALLING or "auto").strip().lower()
    if mode in {"1", "true", "yes", "on"}:
        return True
    if mode in {"0", "false", "no", "off"}:
        return False
    base = (settings.LLM_BASE_URL or "").lower()
    if any(host in base for host in ("127.0.0.1", "localhost", "0.0.0.0")):
        return False
    matched = re.search(r"(\d+(?:\.\d+)?)b", (settings.LLM_MODEL or "").lower())
    if matched and float(matched.group(1)) <= 8:
        return False
    return True


def _sse(payload: dict[str, Any]) -> str:
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def _history(items: list[dict] | None) -> list[dict[str, str]]:
    cleaned = []
    for item in items or []:
        role = str(item.get("role") or "")
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "").strip()
        if content:
            cleaned.append({"role": role, "content": content[:200]})
    return cleaned[-4:]


def _source_items(chunks: list[dict]) -> list[dict]:
    items = []
    for index, chunk in enumerate(chunks, 1):
        snippet = re.sub(r"\s+", " ", chunk.get("content") or "").strip()[:80]
        items.append(
            {
                "index": index,
                "title": chunk.get("title") or "",
                "doc_type": chunk.get("doc_type"),
                "source_type": chunk.get("source_type"),
                "source_id": chunk.get("source_id"),
                "section": chunk.get("section") or "",
                "score": chunk.get("score"),
                "snippet": snippet,
            }
        )
    return items


def _fit_prompt(question: str, history: list[dict], chunks: list[dict], tool_text: str, instruction: str) -> str:
    """把资料、工具和历史压到约 1500 字，避免小模型上下文过长。"""
    bodies = [settings.RAG_PROMPT_CHUNK_CHARS, 220, 160, 120]
    kept = list(chunks)
    text = ""
    for body_limit in bodies:
        lines = ["【资料】"]
        if kept:
            for index, chunk in enumerate(kept, 1):
                section = f" / {chunk['section']}" if chunk.get("section") else ""
                body = re.sub(r"\s+", " ", chunk.get("content") or "").strip()[:body_limit]
                lines.append(f"[{index}] {chunk.get('title') or '资料'}{section}")
                lines.append(body)
        else:
            lines.append("无")
        tool_block = (tool_text or "无")[:700]
        hist_lines = []
        for item in history:
            speaker = "用户" if item["role"] == "user" else "助手"
            hist_lines.append(f"{speaker}: {item['content'][:120]}")
        parts = ["\n".join(lines), "【工具结果】\n" + tool_block]
        if hist_lines:
            parts.append("【最近对话】\n" + "\n".join(hist_lines))
        if instruction:
            parts.append(instruction[:200])
        parts.append("【问题】\n" + question.strip()[:800])
        text = "\n\n".join(parts)
        if len(text) <= PROMPT_CHAR_BUDGET:
            return text
        if len(kept) > 2:
            kept = kept[:2]
    return text[:PROMPT_CHAR_BUDGET]


def _system_prompt(agent: str) -> str:
    return (
        f"你是高校就业推荐平台的{agent}。"
        "只根据【资料】和【工具结果】回答，禁止编造政策、岗位、候选人和统计数字。"
        "引用资料时在句末标注[序号]。资料和工具都是“无”时，直接说明知识库没有相关信息，"
        "并提醒以学校和当地最新政策为准。用简洁中文。"
    )


def _keep_conclusion(answer: str, tool_text: str) -> str:
    """统计结论以工具第一行为准。模型若改写了对象，把原结论补在末尾。"""
    matched = re.search(r"结论：(.+)", tool_text or "")
    if not matched:
        return answer
    line = matched.group(1).strip()
    subject = line.split("，")[0]
    subject = subject.replace("平均月薪最高的是", "").replace("增长最快的是", "").strip()
    if subject and subject not in (answer or ""):
        return (answer or "").rstrip() + f"\n\n统计结论：{line}"
    return answer


def _ensure_citations(answer: str, chunks: list[dict]) -> str:
    if not chunks or re.search(r"\[\d+\]", answer or ""):
        return answer
    lines = []
    for index, chunk in enumerate(chunks, 1):
        section = f" / {chunk['section']}" if chunk.get("section") else ""
        lines.append(f"[{index}] {chunk.get('title') or '资料'}{section}")
    return answer.rstrip() + "\n\n参考来源：\n" + "\n".join(lines)


def _offline_text(question: str, chunks: list[dict], tool_text: str) -> str:
    parts = []
    if tool_text.strip() and tool_text.strip() != "无":
        parts.append("【离线模式】大模型不可用，以下为查询结果：\n" + tool_text.strip())
    if chunks:
        extracted = OfflineGenerator.generate(question, chunks, max_sentences=3)
        extracted = re.sub(r"^【离线模式】[^\n]*\n?", "", extracted).strip()
        if extracted:
            prefix = "" if parts else "【离线模式】未连接大模型，以下为知识库原文摘录：\n"
            parts.append(prefix + extracted)
    if not parts:
        return "【离线模式】知识库中没有找到与该问题相关的资料，请以学校就业指导中心和当地最新政策为准。"
    return "\n\n".join(parts)


def _model_tool_requests(question: str, caller: Caller) -> list[ToolRequest] | None:
    """让大模型选择工具。失败或没有合法调用时返回 None，由路由接管。"""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class SearchArgs(BaseModel):
        keyword: str = ""
        city: str = ""
        direction: str = ""
        education: int | None = None
        salary_min: int | None = None
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

    catalog = {
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
        "recommend_eval": ("读取推荐离线评估指标", EmptyArgs),
        "platform_overview": ("读取用户、企业和职位数量", EmptyArgs),
    }
    allowed = allowed_tool_names(caller.role)
    tools = []
    for name, (desc, schema) in catalog.items():
        if name not in allowed:
            continue

        def _noop(**kwargs: Any) -> str:
            return ""

        tools.append(StructuredTool.from_function(_noop, name=name, description=desc, args_schema=schema))
    if not tools:
        return None
    llm = get_llm(streaming=False, max_tokens=120)
    bound = llm.bind_tools(tools)
    response = bound.invoke(
        [
            SystemMessage(content="需要查数据时只调用一个工具，不要编造参数里的用户身份，不要直接回答。"),
            HumanMessage(content=question[:400]),
        ]
    )
    calls = getattr(response, "tool_calls", None) or []
    requests: list[ToolRequest] = []
    for call in calls:
        name = str(call.get("name") or "")
        if name not in allowed:
            continue
        args = call.get("args") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if not isinstance(args, dict):
            args = {}
        args.pop("user_id", None)
        args.pop("role", None)
        args.pop("note", None)
        requests.append(ToolRequest(name=name, args=args))
        if len(requests) >= 2:
            break
    return requests or None


async def iter_events(
    question: str,
    caller: Caller,
    history: list[dict] | None = None,
    session_id: int | None = None,
) -> AsyncIterator[str]:
    """产出 SSE 事件，最后一条为 data: [DONE]。"""
    started = time.perf_counter()
    first_token_ms = None
    answer_parts: list[str] = []
    tool_events: list[dict[str, Any]] = []
    chunks: list[dict] = []
    online = False
    try:
        online = await asyncio.to_thread(is_available)
    except Exception:
        logger.exception("检查大模型可用性失败")
        online = False
    agent = AGENT_NAMES.get(caller.role, "就业助手")
    yield _sse(
        {
            "type": "meta",
            "role": caller.role,
            "agent": agent,
            "mode": "online" if online else "offline",
            "model": settings.LLM_MODEL,
            "session_id": session_id,
        }
    )

    def elapsed() -> int:
        return int((time.perf_counter() - started) * 1000)

    async def emit_text(text: str) -> AsyncIterator[str]:
        nonlocal first_token_ms
        if text and first_token_ms is None:
            first_token_ms = elapsed()
        answer_parts.append(text)
        yield _sse({"type": "delta", "text": text})

    try:
        decided: Route | None = None
        if online and use_model_tools():
            yield _sse({"type": "status", "text": "正在识别意图…"})
            try:
                picked = await asyncio.to_thread(_model_tool_requests, question, caller)
            except Exception:
                logger.exception("工具调用失败，改用规则路由")
                picked = None
            if picked:
                decided = Route(tools=picked, doc_types=_doc_types_for_tools(picked), instruction="")
        if decided is None:
            yield _sse({"type": "status", "text": "正在识别意图…"})
            decided = await asyncio.to_thread(route, question, caller.role)

        if decided.refusal:
            async for piece in emit_text(decided.refusal):
                yield piece
            yield _sse({"type": "sources", "items": []})
            yield _finish(answer_parts, [], tool_events, elapsed(), first_token_ms)
            yield "data: [DONE]\n\n"
            return

        doc_types = decided.doc_types if decided.doc_types is not None else []
        chunk_list: list[dict] = []
        if doc_types:
            yield _sse({"type": "status", "text": "正在检索知识库…"})
            async for item in _to_thread_stream(fetch_chunks, question, doc_types):
                if item == "__hb__":
                    yield ": ping\n\n"
                elif isinstance(item, list):
                    chunk_list = item
        chunks = chunk_list
        source_items = _source_items(chunk_list)
        yield _sse({"type": "sources", "items": source_items})

        tool_text_parts: list[str] = []
        for request in decided.tools:
            yield _sse({"type": "status", "text": f"正在调用工具 {request.name}…"})
            result_holder: list[dict] = []
            async for item in _to_thread_stream(execute, request.name, request.args, caller):
                if item == "__hb__":
                    yield ": ping\n\n"
                else:
                    result_holder.append(item)
            result = result_holder[0] if result_holder else {"ok": False, "message": "工具无结果"}
            prompt_text, summary = render(request.name, result)
            tool_events.append({"name": request.name, "args": request.args, "summary": summary})
            yield _sse({"type": "tool", "name": request.name, "args": request.args, "summary": summary})
            if result.get("denied"):
                async for piece in emit_text(result.get("message") or "无权执行该操作。"):
                    yield piece
                yield _finish(answer_parts, source_items, tool_events, elapsed(), first_token_ms)
                yield "data: [DONE]\n\n"
                return
            tool_text_parts.append(prompt_text)

        tool_text = "\n".join(tool_text_parts)

        if caller.role == "admin" and not decided.tools:
            async for piece in emit_text(decided.instruction or "请说明要查询的统计指标。"):
                yield piece
            yield _finish(answer_parts, source_items, tool_events, elapsed(), first_token_ms)
            yield "data: [DONE]\n\n"
            return

        if not online:
            text = _offline_text(question, chunk_list, tool_text)
            text = _ensure_citations(text, chunk_list)
            async for piece in emit_text(text):
                yield piece
            yield _finish(answer_parts, source_items, tool_events, elapsed(), first_token_ms)
            yield "data: [DONE]\n\n"
            return

        if not chunk_list and not tool_text_parts:
            fixed = "知识库中没有找到与该问题直接对应的资料。请换一种问法，或向学校就业指导中心核实最新政策。"
            # 仍交给模型会增加幻觉，政策类问题在没有命中时直接说明
            if not decided.tools:
                async for piece in emit_text(fixed):
                    yield piece
                yield _finish(answer_parts, source_items, tool_events, elapsed(), first_token_ms)
                yield "data: [DONE]\n\n"
                return

        prompt = _fit_prompt(question, _history(history), chunk_list, tool_text, decided.instruction)
        messages = [
            {"role": "system", "content": _system_prompt(agent)},
            {"role": "user", "content": prompt},
        ]
        yield _sse({"type": "status", "text": "正在生成回答…"})
        try:
            async for delta in _stream_tokens(messages):
                if delta == "__hb__":
                    yield ": ping\n\n"
                    continue
                if first_token_ms is None:
                    first_token_ms = elapsed()
                answer_parts.append(delta)
                yield _sse({"type": "delta", "text": delta})
        except Exception:
            logger.exception("流式生成失败，改为离线摘录")
            fallback = _offline_text(question, chunk_list, tool_text)
            async for piece in emit_text("\n" + fallback):
                yield piece

        final = _keep_conclusion("".join(answer_parts), tool_text)
        final = _ensure_citations(final, chunk_list)
        if final != "".join(answer_parts):
            extra = final[len("".join(answer_parts)) :]
            answer_parts.append(extra)
            if first_token_ms is None:
                first_token_ms = elapsed()
            yield _sse({"type": "delta", "text": extra})
        yield _finish(answer_parts, source_items, tool_events, elapsed(), first_token_ms)
        yield "data: [DONE]\n\n"
    except Exception as exc:
        logger.exception("对话失败")
        yield _sse({"type": "error", "msg": "对话处理失败"})
        yield _finish(answer_parts, _source_items(chunks if isinstance(chunks, list) else []), tool_events, elapsed(), first_token_ms)
        yield "data: [DONE]\n\n"


def _doc_types_for_tools(tools: list[ToolRequest]) -> list[int]:
    names = {item.name for item in tools}
    if "search_jobs" in names:
        return [7]
    if "analyze_resume_gap" in names or "polish_job_description" in names or "generate_job_description" in names:
        return [5, 4]
    return []


def _finish(parts: list[str], sources: list[dict], tools: list[dict], latency_ms: int, first_token_ms: int | None) -> str:
    return _sse(
        {
            "type": "done",
            "answer": "".join(parts),
            "sources": sources,
            "tools": tools,
            "latency_ms": latency_ms,
            "first_token_ms": first_token_ms,
        }
    )


async def _to_thread_stream(func, *args):
    task = asyncio.create_task(asyncio.to_thread(func, *args))
    while not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=8)
        except asyncio.TimeoutError:
            yield "__hb__"
    yield task.result()


async def _stream_tokens(messages: list[dict]) -> AsyncIterator[str]:
    queue: asyncio.Queue = asyncio.Queue()
    llm = get_llm(streaming=True, max_tokens=ANSWER_TOKENS)

    async def pump() -> None:
        try:
            async for chunk in llm.astream(messages):
                delta = chunk.content
                if isinstance(delta, str) and delta:
                    await queue.put(delta)
                elif isinstance(delta, list):
                    for part in delta:
                        if isinstance(part, str) and part:
                            await queue.put(part)
                        elif isinstance(part, dict) and part.get("text"):
                            await queue.put(part["text"])
        except Exception as exc:
            await queue.put(exc)
        await queue.put(None)

    task = asyncio.create_task(pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=8)
            except asyncio.TimeoutError:
                yield "__hb__"
                continue
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            if item:
                yield item
    finally:
        if not task.done():
            task.cancel()

