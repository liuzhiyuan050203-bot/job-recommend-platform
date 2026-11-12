"""近域拒答：领域意图检查 + 相关性门槛。

知识库覆盖就业政策、三方协议、劳动合同、档案户口（就业相关）、求职指导和在招职位。
考研报名、四级准考证、护照办理、国考入口、积分落户申报等相近但未收录的主题，
应返回空命中，由助手给出「知识库暂无相关资料」并提示可问的范围。

稠密余弦门槛在 dev 集上标定、held-out 上报告，见 experiments/rag_eval/REPORT_v3.md。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger(__name__)

# OUT 意图：问的是知识库未覆盖的近域办事流程。必须带上该类事务的办理/报名用语，
# 避免把「因为考公不想去了，三方怎么违约」误判为拒答。
_OUT_PATTERNS = [
    re.compile(r"考研.{0,16}(报名|缴费|报考|准考证|调剂|初试|复试|成绩|大纲)"),
    re.compile(r"(报名|缴费|准考证|调剂|报考).{0,16}考研"),
    re.compile(r"研究生(入学|招生).{0,10}(考试|报名)"),
    re.compile(r"(英语)?[四六]级.{0,12}(考试|准考证|报名|成绩|证书|打印)"),
    re.compile(r"(CET|cet)[- ]?[46].{0,10}(考试|报名|成绩|准考证)"),
    re.compile(r"(申办|办理|申请|第一次|首次).{0,10}(因私)?护照"),
    re.compile(r"(因私)?护照.{0,14}(材料|派出所|预约|办理|申办|签证|出入境|大厅)"),
    re.compile(r"(国家)?公务员(考试|招考)|国考(报名|入口|岗位|准考证)"),
    re.compile(r"(公务员|事业编).{0,10}(报名入口|报名网址|准考证|报名费)"),
    re.compile(r"积分落户"),
    re.compile(r"(托福|雅思|GRE|IELTS|TOEFL).{0,10}(报名|考试|成绩|截止|日期)"),
    re.compile(r"(驾照|驾驶证).{0,10}(科目|预约|考试|办理|报名)"),
    re.compile(r"(旅游签证|出国签证|签证预约).{0,12}(材料|办理|预约|护照)"),
    re.compile(r"(结婚登记|身份证换领|户口本补办|医保异地就医)"),
]

# 明显属于就业知识库的用语。与 OUT 同时命中时仍以 OUT 为准（「积分落户」里也有「户口」）。
_IN_PATTERNS = [
    re.compile(p)
    for p in (
        r"三方(协议)?",
        r"就业(协议|意向|政策|指导|手续)",
        r"劳动合[同约]",
        r"劳动合约",
        r"劳动仲裁",
        r"试用期",
        r"考察期",
        r"网签",
        r"网申",
        r"违约(金|条款)?",
        r"解约",
        r"档案",
        r"户口",
        r"落户",
        r"报到证",
        r"人才(服务)?中心",
        r"组织关系",
        r"预备党员",
        r"校招",
        r"秋招",
        r"春招",
        r"简历",
        r"面试",
        r"技术面",
        r"群面",
        r"无领导小组",
        r"招聘(启事|合规|须知)?",
        r"投递",
        r"职位",
        r"岗位",
        r"薪资",
        r"工资",
        r"offer",
        r"录用",
        r"入职",
        r"离职",
        r"应届",
        r"求职",
        r"双选会",
        r"培训费",
        r"只(限|要)(男|女)",
        r"押金",
        r"点了接受",
        r"用人单位",
        r"在招",
        r"西部计划",
        r"三支一扶",
        r"特岗",
        r"征兵",
        r"入伍",
        r"当兵",
        r"创业",
        r"灵活就业",
        r"社保补贴",
        r"见习",
        r"一类账户",
        r"模拟数据",
        r"冷启动",
    )
]

# 很短的查询多半是知识库关键词（如「三支一扶」「包落户」），
# 在未命中 OUT 时按 in 处理，避免 UNKNOWN 门槛误伤。
_SHORT_QUERY_CHARS = 8

# 标定结果（dev 集，仅知识库 74 切片，hybrid，2026-11-12）：
# 近域 OUT 最高余弦 0.633（积分落户 vs 户口迁移），held-out 最高 0.627。
# OUT 门槛取 0.82，与 dev 最高分间隔约 0.19，只有几乎全文贴合才放行。
# UNKNOWN 门槛 0.62：短关键词查询已归入 in，长句 UNKNOWN 的 in-scope 最低约 0.63。
DEFAULT_OUT_COSINE = 0.82
DEFAULT_UNKNOWN_COSINE = 0.62
DEFAULT_OUT_RERANK = 0.0

_SCOPE_HINT = (
    "本平台知识库主要覆盖就业政策、三方协议与违约、劳动合同和试用期、"
    "档案户口（就业相关）、求职指导、企业招聘合规以及在招职位。"
)


@dataclass
class ScopeDecision:
    refuse: bool
    intent: str
    reason: str
    max_cosine: float = 0.0
    max_rerank: float | None = None
    threshold_used: float | None = None
    details: dict = field(default_factory=dict)


def _significant_chars(text: str) -> int:
    """不计空白和标点的有效字数，用来判断是否是短关键词查询。"""
    return sum(1 for ch in text if ch.isalnum() or ("一" <= ch <= "鿿"))


def domain_intent(question: str) -> str:
    """返回 in / out / unknown。"""
    text = (question or "").strip()
    if not text:
        return "unknown"
    if any(p.search(text) for p in _OUT_PATTERNS):
        return "out"
    if any(p.search(text) for p in _IN_PATTERNS):
        return "in"
    if _significant_chars(text) <= _SHORT_QUERY_CHARS:
        return "in"
    return "unknown"


def _max_cosine(hits: list[dict]) -> float:
    best = 0.0
    for hit in hits or []:
        try:
            best = max(best, float(hit.get("score") or 0.0))
        except (TypeError, ValueError):
            continue
    return best


def _thresholds() -> tuple[float, float, float]:
    out = getattr(settings, "RAG_SCOPE_OUT_COSINE", None)
    unknown = getattr(settings, "RAG_SCOPE_UNKNOWN_COSINE", None)
    rerank = getattr(settings, "RAG_SCOPE_OUT_RERANK", None)
    return (
        float(out) if out is not None and float(out) > 0 else DEFAULT_OUT_COSINE,
        float(unknown) if unknown is not None and float(unknown) > 0 else DEFAULT_UNKNOWN_COSINE,
        float(rerank) if rerank is not None else DEFAULT_OUT_RERANK,
    )


def decide_scope(
    question: str,
    hits: list[dict] | None,
    *,
    rerank: list[float] | None = None,
    out_cosine: float | None = None,
    unknown_cosine: float | None = None,
    out_rerank: float | None = None,
) -> ScopeDecision:
    """根据意图和最高相关性决定是否拒答。hits 为空视为已无资料，refuse=True。"""
    intent = domain_intent(question)
    rows = list(hits or [])
    max_cos = _max_cosine(rows)
    max_rr: float | None = None
    if rerank:
        try:
            max_rr = max(float(s) for s in rerank)
        except (TypeError, ValueError):
            max_rr = None
    default_out, default_unknown, default_rr = _thresholds()
    t_out = default_out if out_cosine is None else float(out_cosine)
    t_unk = default_unknown if unknown_cosine is None else float(unknown_cosine)
    t_rr = default_rr if out_rerank is None else float(out_rerank)

    if not rows:
        return ScopeDecision(
            refuse=True,
            intent=intent,
            reason="no_hits",
            max_cosine=max_cos,
            max_rerank=max_rr,
        )
    if intent == "in":
        return ScopeDecision(
            refuse=False,
            intent=intent,
            reason="in_scope",
            max_cosine=max_cos,
            max_rerank=max_rr,
        )
    if intent == "out":
        # 极高相关才放行（知识库以后若收录该类文档，仍能答）。
        keep_by_cosine = max_cos >= t_out
        keep_by_rerank = max_rr is not None and max_rr >= t_rr and max_cos >= t_out
        if keep_by_cosine or keep_by_rerank:
            return ScopeDecision(
                refuse=False,
                intent=intent,
                reason="out_but_strong",
                max_cosine=max_cos,
                max_rerank=max_rr,
                threshold_used=t_out,
            )
        return ScopeDecision(
            refuse=True,
            intent=intent,
            reason="out_of_scope",
            max_cosine=max_cos,
            max_rerank=max_rr,
            threshold_used=t_out,
        )
    if max_cos < t_unk:
        return ScopeDecision(
            refuse=True,
            intent=intent,
            reason="weak_relevance",
            max_cosine=max_cos,
            max_rerank=max_rr,
            threshold_used=t_unk,
        )
    return ScopeDecision(
        refuse=False,
        intent=intent,
        reason="unknown_relevant",
        max_cosine=max_cos,
        max_rerank=max_rr,
        threshold_used=t_unk,
    )


def apply_scope_gate(
    question: str,
    hits: list[dict] | None,
    *,
    rerank: list[float] | None = None,
    enabled: bool | None = None,
) -> list[dict]:
    """拒答时返回空列表，否则原样返回 hits。enabled 默认跟随配置 RAG_SCOPE_GATE。"""
    rows = list(hits or [])
    if enabled is None:
        enabled = bool(getattr(settings, "RAG_SCOPE_GATE", True))
    if not enabled:
        return rows
    decision = decide_scope(question, rows, rerank=rerank)
    if decision.refuse and rows:
        logger.info(
            "近域拒答 intent=%s reason=%s cosine=%.3f q=%s",
            decision.intent,
            decision.reason,
            decision.max_cosine,
            (question or "")[:40],
        )
        return []
    return rows


def refusal_answer(role: str = "student") -> str:
    """助手在知识库无相关资料时的固定话术，含可问范围建议。"""
    if role == "company":
        return (
            f"知识库暂无相关资料。{_SCOPE_HINT}"
            "建议改问招聘合规、职位发布或候选人筛选方面的问题，"
            "或到「招聘看板」「候选人管理」查看本公司实时数据。"
        )
    if role == "admin":
        return f"知识库暂无相关资料。{_SCOPE_HINT}请换一种问法，或查看管理端数据看板。"
    return (
        f"知识库暂无相关资料。{_SCOPE_HINT}"
        "建议改问这些方面，或向学校就业指导中心核实最新规定。"
    )
