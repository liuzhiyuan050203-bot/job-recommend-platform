"""查询改写与分解：规则为主，云端模型可选；多路结果用 RRF 融合。

本地 ollama（qwen2.5:3b）默认只走规则，避免增加本地推理延迟。
``RAG_QUERY_REWRITE_LLM=auto`` 时仅云端提供方才调用大模型改写；失败则退回规则结果。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

from app.core.config import settings

logger = logging.getLogger(__name__)

# 长的在前，避免「就业协议书」被「就业协议」先替换掉。
SYNONYM_PAIRS: tuple[tuple[str, str], ...] = (
    ("毕业生就业协议书", "三方协议"),
    ("就业意向书", "三方协议"),
    ("就业协议书", "三方协议"),
    ("就业协议", "三方协议"),
    ("正式劳动合约", "劳动合同"),
    ("劳动合约", "劳动合同"),
    ("考察期内", "试用期内"),
    ("考察期间", "试用期"),
    ("考察时间", "试用期"),
    ("考察期", "试用期"),
    ("网上点了接受", "网签已接受"),
    ("点了接受", "网签已接受"),
    ("只要男生", "限制性别 违规"),
    ("只限男性", "限制性别 违规"),
    ("只限女生", "限制性别 违规"),
    ("只限女性", "限制性别 违规"),
    ("培训费押金", "培训费 押金 违规"),
    ("专项培训", "专项培训 服务期"),
)

_COMPARISON_CUES = ("分别", "两边", "有什么不一样", "有什么不同", "有何区别", "有哪些不一样")
_ROLE_PAIRS = (("企业", "学生"), ("用人单位", "毕业生"), ("公司", "学生"))
_SEPARATORS = ("，和", "；和", "；", "。", "，同时", "，另外", "，以及", "，学生", "，若学生")

# 最多保留的查询条数（含原问），控制多次嵌入的开销。
MAX_QUERIES = 4
MIN_CLAUSE_CHARS = 8


def apply_synonyms(text: str) -> str:
    """把口语替换成知识库常用说法。未命中时返回原文。

    若替换结果是「原词 + 补充词」，而补充词已在句中出现，则跳过，避免「服务期」被写两遍。
    """
    out = text or ""
    for src, dst in SYNONYM_PAIRS:
        if src not in out:
            continue
        if dst.startswith(src):
            extra = dst[len(src) :].strip()
            if extra and extra in out:
                continue
        out = out.replace(src, dst)
    return out


def _should_decompose(question: str) -> bool:
    text = (question or "").strip()
    if len(text) < 28:
        return False
    if any(cue in text for cue in _COMPARISON_CUES):
        return True
    return any(a in text and b in text for a, b in _ROLE_PAIRS)


def decompose(question: str) -> list[str]:
    """把同时问两件事的长句拆成子问题。不满足条件时返回空列表。"""
    text = (question or "").strip()
    if not _should_decompose(text):
        return []
    for sep in _SEPARATORS:
        if sep not in text:
            continue
        parts = [p.strip("，、；。 ") for p in text.split(sep) if len(p.strip("，、；。 ")) >= MIN_CLAUSE_CHARS]
        if len(parts) >= 2:
            return parts[:3]
    match = re.search(r"(.{%d,}?)和(.{%d,})" % (10, 10), text)
    if match:
        left, right = match.group(1).strip("，、；。 "), match.group(2).strip("，、；。 ")
        if left and right:
            return [left, right]
    return []


def _dedupe(queries: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in queries:
        text = " ".join((item or "").split())
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= MAX_QUERIES:
            break
    return out


_CLAUSE_TAIL = re.compile(
    r"[，、；]?(两边|分别).*$|(有什么不一样|有什么不同|有何区别|才谈得上要给钱).*$"
)


def _clean_clause(text: str) -> str:
    """去掉比较问句的共用尾巴，使子问题更像独立检索查询。"""
    cleaned = _CLAUSE_TAIL.sub("", text or "").strip("，、；。 ")
    return cleaned or (text or "").strip()


def rule_rewrites(question: str) -> list[str]:
    """原问 + 拆出的子问题（优先）+ 整句同义改写。子问题先做同义替换。"""
    text = (question or "").strip()
    if not text:
        return []
    queries = [text]
    for clause in decompose(text):
        clause = _clean_clause(clause)
        if not clause:
            continue
        queries.append(apply_synonyms(clause))
    expanded = apply_synonyms(text)
    if expanded != text:
        queries.append(expanded)
    return _dedupe(queries)


def _llm_rewrite_enabled() -> bool:
    flag = (getattr(settings, "RAG_QUERY_REWRITE_LLM", "auto") or "auto").strip().lower()
    if flag in {"false", "0", "no", "off"}:
        return False
    if flag in {"true", "1", "yes", "on"}:
        return True
    return bool(getattr(settings, "is_cloud_llm", False))


def llm_rewrites(question: str) -> list[str]:
    """云端（或显式开启时）让大模型生成 2–3 条检索子问。失败返回空，不抛给主路径。"""
    text = (question or "").strip()
    if not text or not _llm_rewrite_enabled():
        return []
    try:
        from app.core.llm import get_llm, is_available

        if not is_available():
            return []
        llm = get_llm()
        if llm is None:
            return []
        prompt = (
            "把下面这条高校就业或招聘问题改写成 2 到 3 条便于检索的子问题。"
            "若同时问两件事请拆开。使用知识库里的标准说法：三方协议、劳动合同、试用期、档案、户口、违约金。"
            "每行一条，不要编号和解释。\n问题：" + text
        )
        invoke = getattr(llm, "invoke", None)
        if invoke is None:
            return []
        # 短超时：改写失败就退回规则，不能拖垮整次检索。
        message = invoke(prompt)
        raw = message.content if hasattr(message, "content") else str(message)
        if isinstance(raw, list):
            raw = "".join(str(p) for p in raw)
        lines: list[str] = []
        for line in str(raw or "").splitlines():
            cleaned = re.sub(r"^[\s\d]+[\.\)、．]?\s*", "", line).strip(" \t-•*")
            if 4 <= len(cleaned) <= 80:
                lines.append(cleaned)
        return _dedupe(lines)[:3]
    except Exception:
        logger.exception("LLM 查询改写失败，退回规则改写")
        return []


def expand_queries(question: str, *, allow_llm: bool = True) -> list[str]:
    """最终用于多路检索的查询列表，第一条始终是原问。"""
    text = (question or "").strip()
    if not text:
        return []
    enabled = getattr(settings, "RAG_QUERY_REWRITE", True)
    if not enabled:
        return [text]
    queries = rule_rewrites(text)
    if allow_llm:
        for extra in llm_rewrites(text):
            if extra not in queries:
                queries.append(extra)
            if len(queries) >= MAX_QUERIES:
                break
    return _dedupe(queries) or [text]


def is_job_only(doc_types: list[int] | None) -> bool:
    """只检索职位切片时不做改写和拆分，避免把公司名、岗位名拆散。"""
    if not doc_types:
        return False
    return all(int(t) == 7 for t in doc_types)


# 原问权重大于改写子问，避免多路融合把原本已在第一的金标挤下去。
ORIGINAL_QUERY_WEIGHT = 2.0
REWRITE_QUERY_WEIGHT = 1.0
RRF_K = 60


def rrf_fuse_weighted(rankings: Sequence[Sequence[str]], weights: Sequence[float] | None = None, k: int = RRF_K) -> dict[str, float]:
    """带权重的 RRF。weights 缺省时各路为 1；与 rrf_fuse 在等权时结果相同。"""
    scores: dict[str, float] = {}
    for index, ranking in enumerate(rankings):
        weight = 1.0 if not weights else float(weights[index] if index < len(weights) else 1.0)
        if weight == 0:
            continue
        for rank, doc_id in enumerate(ranking, start=1):
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (k + rank)
    return scores


def merge_multi_query(
    hit_lists: Sequence[Sequence[dict]],
    limit: int,
    *,
    original_weight: float = ORIGINAL_QUERY_WEIGHT,
    rewrite_weight: float = REWRITE_QUERY_WEIGHT,
) -> list[dict]:
    """用加权 RRF（k=60）融合多路命中。第一路视为原问，权重默认 2，其余为 1。

    同一切片保留较高的稠密余弦。只有一路时保持该路原顺序。
    """
    rankings: list[list[str]] = []
    by_id: dict[str, dict] = {}
    for hits in hit_lists:
        ranking: list[str] = []
        for hit in hits:
            key = str(hit.get("chroma_id") or hit.get("id") or "")
            if not key:
                continue
            if key not in ranking:
                ranking.append(key)
            prev = by_id.get(key)
            if prev is None or float(hit.get("score") or 0) > float(prev.get("score") or 0):
                by_id[key] = dict(hit)
        if ranking:
            rankings.append(ranking)
    if not by_id:
        return []
    if len(rankings) == 1:
        return [by_id[key] for key in rankings[0][: max(1, int(limit))]]
    weights = [float(original_weight)] + [float(rewrite_weight)] * (len(rankings) - 1)
    scores = rrf_fuse_weighted(rankings, weights)
    ordered = sorted(
        by_id.keys(),
        key=lambda key: (scores.get(key, 0.0), float(by_id[key].get("score") or 0.0)),
        reverse=True,
    )
    out: list[dict] = []
    for key in ordered:
        row = by_id[key]
        row["rrf"] = round(float(scores.get(key, 0.0)), 6)
        out.append(row)
        if len(out) >= max(1, int(limit)):
            break
    return out
