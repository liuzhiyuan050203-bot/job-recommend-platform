"""学生、企业、管理员三类助手的对话编排与 SSE 输出（LangChain 组件见 lc_chain.py）。

流程：SessionHistory 取会话记忆 → build_router（RunnableBranch：确定性规则路由先行；
在线且允许工具调用时由 create_agent 建的角色 Agent 选择并执行工具，失败退回规则）→
build_context（RunnableParallel：知识库混合检索与工具并行）→ build_answer_chain
（ChatPromptTemplate | ChatOpenAI | StrOutputParser，.astream 逐段推送）。
本地小模型（auto 模式下 8B 及以下或本机地址）不走 Agent，直接用规则路由；大模型不可用时走离线摘录。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from app.agent.lc_chain import SessionHistory, build_answer_chain, build_context, build_router, doc_types_for_tools
from app.agent.router import Route, ToolRequest, wants_skill_list
from app.agent.tools import Caller, render
from app.core.config import settings
from app.core.llm import OfflineGenerator, get_llm, is_available
from app.rag.retrieve import fetch_chunks
from app.spark.dicts import CITY_PROVINCE

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


def _system_prompt(agent: str, has_sources: bool) -> str:
    if has_sources:
        cite = "引用资料时在句末只写[1]、[2]这种序号，不要写成[资料1]。序号只能使用【资料】里出现的编号。"
    else:
        cite = "当前没有可引用的资料切片，回答中不要出现[1]、[2]这类方括号序号。"
    return (
        f"你是高校就业推荐平台的{agent}。"
        "只根据【资料】和【工具结果】回答，禁止编造政策、岗位、候选人和统计数字。"
        f"{cite}资料和工具都是“无”时，直接说明知识库没有相关信息，"
        "并提醒以学校和当地最新政策为准。用简洁中文。"
    )


# 未写完的「[资料2」或「【资料2」先留在缓冲区，避免把半个引用拆进两个 delta。
_INCOMPLETE_CITE = re.compile(
    r"(?:\[\s*资料\s*\d*\s*|\[\s*资|\[\s*|\[\d*|【\s*资料\s*\d*\s*|【\s*资|【\s*)$"
)


def _normalize_citations(text: str) -> str:
    """把模型写成的 [资料2]、【资料2】收成 [2]。"""
    text = re.sub(r"\[\s*资料\s*(\d+)\s*\]", r"[\1]", text or "")
    text = re.sub(r"【\s*资料\s*(\d+)\s*】", r"[\1]", text or "")
    return text


def _split_incomplete_citation(text: str) -> tuple[str, str]:
    """返回 (可以输出的部分, 末尾可能还没写完的引用)。"""
    positions = [text.rfind(mark) for mark in ("[", "【")]
    positions = [index for index in positions if index >= 0]
    if not positions:
        return text, ""
    start = max(positions)
    suffix = text[start:]
    if re.fullmatch(r"\[\s*资料\s*\d+\s*\]", suffix) or re.fullmatch(r"【\s*资料\s*\d+\s*】", suffix):
        return text, ""
    if re.fullmatch(r"\[\d+\]", suffix):
        return text, ""
    if _INCOMPLETE_CITE.fullmatch(suffix):
        return text[:start], suffix
    return text, ""


class _CitationGate:
    """流式把 [资料n] 收成 [n]，去掉超出资料条数的 [n]，并暂存末尾未写完的引用。

    推给前端的 delta 与最终 done.answer 使用同一套清洗结果。
    """

    def __init__(self) -> None:
        self.limit = 0
        self.pending = ""

    def set_limit(self, limit: int) -> None:
        self.limit = max(0, int(limit))

    def push(self, text: str) -> str:
        merged = self.pending + (text or "")
        ready, self.pending = _split_incomplete_citation(merged)
        return _strip_over_citations(_normalize_citations(ready), self.limit)

    def flush(self) -> str:
        tail = _strip_over_citations(_normalize_citations(self.pending), self.limit)
        self.pending = ""
        return tail


def _strip_over_citations(text: str, limit: int) -> str:
    """去掉编号小于 1 或大于资料条数的 [n]。没有资料时全部去掉。"""

    def repl(match: re.Match[str]) -> str:
        number = int(match.group(1))
        if number < 1 or number > limit:
            return ""
        return match.group(0)

    return re.sub(r"\[(\d+)\]", repl, text or "")


def _keep_conclusion(answer: str, tool_text: str, *, keep_single: bool = True) -> str:
    """统计结论以工具第一行为准。模型若改写了对象，把原结论补在末尾。

    排行类问题要保留前几名，不能再补一句「增长最快的是某某」。
    """
    if not keep_single:
        return answer
    matched = re.search(r"结论：(.+)", tool_text or "")
    if not matched:
        return answer
    line = matched.group(1).strip()
    subject = line.split("，")[0]
    subject = subject.replace("平均月薪最高的是", "").replace("增长最快的是", "").strip()
    if subject and subject not in (answer or ""):
        return (answer or "").rstrip() + f"\n\n统计结论：{line}"
    return answer


def _bullet_items(tool_text: str) -> list[str]:
    return [line[2:].strip() for line in (tool_text or "").splitlines() if line.startswith("- ") and line[2:].strip()]


def _compose_skill_answer(tool_text: str) -> str:
    """热门技能排行直接用工具里的需求量和环比，避免模型只复述第一名。"""
    bullets = _bullet_items(tool_text)
    if not bullets:
        return ""
    lines = ["按需求环比，靠前的技能如下："]
    for index, item in enumerate(bullets, 1):
        lines.append(f"{index}. {item}")
    return "\n".join(lines)


def _first_sentence(text: str) -> str:
    compact = re.sub(r"\s+", " ", (text or "")).strip()
    if not compact:
        return ""
    sentence = re.split(r"(?<=[。！？])", compact, maxsplit=1)[0].strip()
    return sentence[:120]


def _job_lead_ok(lead: str, cities: list[str]) -> bool:
    """导语不能把多个城市或不同薪资说成一样，也不能写出工具里没有的城市。"""
    if not lead:
        return False
    unique = list(dict.fromkeys(city for city in cities if city))
    if re.search(r"(薪资|月薪|工资|待遇).{0,10}(都|均|全部|一样|相同|均为)", lead):
        return False
    if re.search(r"(都|均|全部|全都|一律|清一色).{0,12}(在|位于|地处)", lead) and len(unique) != 1:
        return False
    mentioned = [name for name in sorted(CITY_PROVINCE, key=len, reverse=True) if name and name in lead]
    if any(name not in unique for name in mentioned):
        return False
    if len(unique) > 1 and len(mentioned) == 1:
        return False
    return True


def _compose_job_answer(model_text: str, tool_text: str) -> str:
    """推荐和检索：一句导语加上工具原文列表，城市和薪资按条保留。"""
    bullets = _bullet_items(tool_text)
    if not bullets:
        return model_text or ""
    cities = []
    for item in bullets:
        parts = [part.strip() for part in item.split("｜")]
        if len(parts) >= 3:
            cities.append(parts[2])
    lead = _first_sentence(model_text)
    if not _job_lead_ok(lead, cities):
        lead = "以下为查询到的职位，城市和薪资以每条为准。"
    lines = [lead, "", "职位列表（城市与薪资以每条为准）："]
    for index, item in enumerate(bullets, 1):
        lines.append(f"{index}. {item}")
    return "\n".join(lines)


def _apply_answer_shape(decided: Route, question: str) -> None:
    """模型选工具时补上和关键词路由相同的回答形态。"""
    if decided.answer_shape:
        return
    names = {item.name for item in decided.tools}
    if "search_jobs" in names or "get_my_recommendations" in names:
        decided.answer_shape = "job_list"
        if not decided.instruction:
            decided.instruction = "只用一句话说明条数，不要把不同职位概括成同一城市或同一薪资。"
    elif "tech_trend" in names and wants_skill_list(question):
        decided.answer_shape = "skill_list"
        decided.instruction = "按工具结果逐条列出技能名称、需求量和环比，不要只写增长最快的一项，不要改数字。"


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
    source_items: list[dict] = []
    gate = _CitationGate()
    online = False
    handling_error = False
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
        cleaned = gate.push(text)
        if not cleaned:
            return
        if first_token_ms is None:
            first_token_ms = elapsed()
        answer_parts.append(cleaned)
        yield _sse({"type": "delta", "text": cleaned})

    async def flush_gate() -> AsyncIterator[str]:
        nonlocal first_token_ms
        tail = gate.flush()
        if not tail:
            return
        if first_token_ms is None:
            first_token_ms = elapsed()
        answer_parts.append(tail)
        yield _sse({"type": "delta", "text": tail})

    async def end_turn() -> AsyncIterator[str]:
        async for piece in flush_gate():
            yield piece
        yield _finish(answer_parts, source_items, tool_events, elapsed(), first_token_ms)
        yield "data: [DONE]\n\n"

    try:
        yield _sse({"type": "status", "text": "正在识别意图…"})
        router = build_router(caller, use_agent=online and use_model_tools())
        decided: Route = await asyncio.to_thread(router.invoke, question)
        recent = SessionHistory(session_id, caller.user_id, history, question).recent()

        if decided.refusal:
            async for piece in emit_text(decided.refusal):
                yield piece
            yield _sse({"type": "sources", "items": []})
            async for piece in end_turn():
                yield piece
            return

        if caller.role == "admin" and not decided.tools:
            decided.tools.append(ToolRequest("platform_overview", {}))
            if not decided.doc_types:
                decided.doc_types = [1, 2, 3, 4, 5, 6]
            if not decided.instruction:
                decided.instruction = "结合平台概况中的数字和资料回答。没有直接依据时说明知识库没有相关内容，不要编造统计数字。"

        doc_types = decided.doc_types if decided.doc_types is not None else []
        if doc_types:
            yield _sse({"type": "status", "text": "正在检索知识库…"})
        for request in decided.tools:
            yield _sse({"type": "status", "text": f"正在调用工具 {request.name}…"})
        context = build_context(caller, fetch_chunks)
        gathered: dict = {}
        async for item in _to_thread_stream(context.invoke, {"question": question, "doc_types": doc_types, "tools": decided.tools}):
            if item == "__hb__":
                yield ": ping\n\n"
            else:
                gathered = item
        chunk_list: list[dict] = gathered.get("chunks") or []
        chunks = chunk_list
        source_items = _source_items(chunk_list)
        gate.set_limit(len(chunk_list))
        yield _sse({"type": "sources", "items": source_items})

        tool_text_parts: list[str] = []
        for request, result in gathered.get("tool_results") or []:
            prompt_text, summary = render(request.name, result)
            tool_events.append({"name": request.name, "args": request.args, "summary": summary})
            yield _sse({"type": "tool", "name": request.name, "args": request.args, "summary": summary})
            if result.get("denied"):
                async for piece in emit_text(result.get("message") or "无权执行该操作。"):
                    yield piece
                async for piece in end_turn():
                    yield piece
                return
            tool_text_parts.append(prompt_text)

        tool_text = "\n".join(tool_text_parts)
        _apply_answer_shape(decided, question)

        if not online:
            if decided.answer_shape == "skill_list" and (listed := _compose_skill_answer(tool_text)):
                text = "【离线模式】大模型不可用，以下为统计结果：\n" + listed
            elif decided.answer_shape == "job_list" and _bullet_items(tool_text):
                text = "【离线模式】大模型不可用，以下为查询结果：\n" + _compose_job_answer("", tool_text)
            else:
                text = _offline_text(question, chunk_list, tool_text)
            text = _ensure_citations(text, chunk_list)
            async for piece in emit_text(text):
                yield piece
            async for piece in end_turn():
                yield piece
            return

        if not chunk_list and not tool_text_parts:
            fixed = "知识库中没有找到与该问题直接对应的资料。请换一种问法，或向学校就业指导中心核实最新政策。"
            # 仍交给模型会增加幻觉，政策类问题在没有命中时直接说明
            if not decided.tools:
                async for piece in emit_text(fixed):
                    yield piece
                async for piece in end_turn():
                    yield piece
                return

        # 排行题的数字以工具为准，不再让小模型收成「只有第一名」
        skill_ready = _compose_skill_answer(tool_text) if decided.answer_shape == "skill_list" else ""
        if skill_ready:
            yield _sse({"type": "status", "text": "正在整理统计结果…"})
            async for piece in emit_text(skill_ready):
                yield piece
        else:
            instruction = decided.instruction or ""
            if decided.answer_shape == "job_list":
                instruction = (
                    instruction + " 职位明细由系统按工具结果逐条附上，你只写一句导语，不要概括城市和薪资。"
                ).strip()
            if not chunk_list:
                instruction = (instruction + " 不要使用[1]、[2]这类引用标记。").strip()
            answer_inputs = {
                "agent": agent,
                "question": question,
                "history": recent,
                "chunks": chunk_list,
                "tool_text": tool_text,
                "instruction": instruction,
            }
            yield _sse({"type": "status", "text": "正在生成回答…"})
            held: list[str] = []
            hold_jobs = decided.answer_shape == "job_list"
            try:
                token_limit = 120 if hold_jobs else ANSWER_TOKENS
                async for delta in _stream_tokens(answer_inputs, token_limit):
                    if delta == "__hb__":
                        yield ": ping\n\n"
                        continue
                    if hold_jobs:
                        held.append(delta)
                        continue
                    cleaned = gate.push(delta)
                    if not cleaned:
                        continue
                    if first_token_ms is None:
                        first_token_ms = elapsed()
                    answer_parts.append(cleaned)
                    yield _sse({"type": "delta", "text": cleaned})
            except Exception:
                logger.exception("流式生成失败，改为离线摘录")
                hold_jobs = False
                held.clear()
                fallback = _offline_text(question, chunk_list, tool_text)
                async for piece in emit_text("\n" + fallback):
                    yield piece
            if hold_jobs:
                async for piece in emit_text(_compose_job_answer("".join(held), tool_text)):
                    yield piece

        async for piece in flush_gate():
            yield piece
        current = "".join(answer_parts)
        final = _keep_conclusion(current, tool_text, keep_single=decided.answer_shape != "skill_list")
        final = _ensure_citations(final, chunk_list)
        if final.startswith(current) and len(final) > len(current):
            async for piece in emit_text(final[len(current) :]):
                yield piece
        async for piece in end_turn():
            yield piece
    except Exception:
        if handling_error:
            return
        handling_error = True
        logger.exception("对话失败")
        yield _sse({"type": "error", "msg": "对话处理失败"})
        if not source_items and chunks:
            source_items = _source_items(chunks)
        async for piece in end_turn():
            yield piece


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


async def _stream_tokens(inputs: dict, max_tokens: int | None = None) -> AsyncIterator[str]:
    """LCEL 回答链 .astream；8 秒没有新片段时插一条心跳。"""
    queue: asyncio.Queue = asyncio.Queue()
    llm = get_llm(streaming=True, max_tokens=max_tokens or ANSWER_TOKENS)
    chain = build_answer_chain(_system_prompt, _fit_prompt, llm)

    async def pump() -> None:
        try:
            async for delta in chain.astream(inputs):
                if isinstance(delta, str) and delta:
                    await queue.put(delta)
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
