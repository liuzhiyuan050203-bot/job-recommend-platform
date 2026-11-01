"""BM25 关键词索引，以及和稠密检索共用的 RRF、阈值规则。

索引单位与 Chroma 中的切片相同（id / document / metadata）。
文本在正文前拼上标题和章节，方便「三方违约金」这类短查询命中专名，
切片边界本身不变。jieba 分词，去掉停用词、标点和单字，并转小写。
"""

from __future__ import annotations

import logging
import re
import threading

import jieba
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# Reciprocal Rank Fusion 的平滑常数，Cormack 等人论文里的常用取值。
RRF_K = 60
# 重排只看融合后的前若干条，避免把整库送进交叉编码器。
RERANK_WINDOW = 20
# 稠密、BM25 各自先取前 N 条再融合。N = max(20, top_k * 5)。
CANDIDATE_FLOOR = 20

# BM25 归一化：norm = raw / (raw + C)。
# 不用「除以本次最高分」，否则无关问句的相对第一名总会变成 1，阈值挡不住。
# 只命中一个查询词时，像「关系 / 一次 / 主要」这种词在短切片上也能到 norm≈0.6，
# 所以单词命中要到 0.72（原始分约 15.4）才算显著；两个及以上查询词命中则 0.50（原始分约 6）即可。
BM25_NORM_C = 6.0
BM25_SIGNIFICANT = 0.50
BM25_SINGLE_TERM_SIGNIFICANT = 0.72

_PUNCT_RE = re.compile(r"^[\W_]+$", re.UNICODE)
_STOP = frozenset(
    {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
        "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
        "自己", "这", "那", "与", "及", "或", "被", "把", "从", "对", "而", "但", "如果",
        "因为", "所以", "什么", "怎么", "如何", "哪些", "哪个", "吗", "呢", "啊", "吧",
        "吗", "么", "以及", "或者", "还是", "不是", "可以", "需要", "进行", "通过",
        "之后", "已经", "还没", "是否", "一般", "通常", "不要", "应该", "为什么",
        "这个", "那个", "我们", "他们", "它们", "及其", "其中", "关于", "对于",
        "the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "is", "are",
        "what", "how", "which",
    }
)
# 就业文档里的专名。不加入词典时，查询和正文会被切成对不上的碎片
# （例如「无领导小组」在问句里是一个词，在「无领导小组讨论」里会被拆开）。
_DOMAIN_WORDS = (
    "无领导小组", "三支一扶", "三方协议", "违约金", "报到证", "冷启动", "两栏简历",
    "求职创业补贴", "就业见习", "创业担保贷款", "双倍工资", "一类账户", "组织关系",
    "介绍信", "西部计划", "特岗教师", "缓存穿透", "入职收费", "灵活就业", "社保补贴",
    "试用期", "劳动合同", "集体户", "改派", "网签", "落户", "助学贷款", "学费补偿",
    "实名登记", "竞业限制", "最低工资", "劳动仲裁", "预备党员", "就业协议书",
    "签名费", "签字费", "双选会", "推荐列表", "技能标签", "匹配分",
)

_jieba_ready = False
_jieba_lock = threading.Lock()


def candidate_pool_size(top_k: int) -> int:
    return max(CANDIDATE_FLOOR, int(top_k) * 5)


def _ensure_jieba() -> None:
    global _jieba_ready
    if _jieba_ready:
        return
    with _jieba_lock:
        if _jieba_ready:
            return
        jieba.initialize()
        for word in _DOMAIN_WORDS:
            jieba.add_word(word)
        _jieba_ready = True


def tokenize(text: str) -> list[str]:
    """jieba 分词，去停用词和标点，英文小写。单字信息太少，直接丢掉。"""
    _ensure_jieba()
    raw = (text or "").lower()
    tokens: list[str] = []
    for tok in jieba.cut(raw, cut_all=False):
        tok = tok.strip().lower()
        if len(tok) < 2 or tok in _STOP or _PUNCT_RE.match(tok):
            continue
        tokens.append(tok)
    return tokens


def bm25_document_text(title: str, section: str, content: str) -> str:
    """BM25 看到的文本：标题、章节、正文。仍对应 Chroma 里的同一条切片。"""
    parts = [str(part).strip() for part in (title, section, content) if part and str(part).strip()]
    return "\n".join(parts)


def normalize_bm25(raw: float) -> float:
    raw = max(0.0, float(raw))
    if raw <= 0:
        return 0.0
    return raw / (raw + BM25_NORM_C)


def bm25_is_significant(raw: float, matched_terms: int = 0) -> bool:
    """归一化后是否显著。matched_terms 是该切片命中的不同查询词个数。"""
    norm = normalize_bm25(raw)
    if matched_terms >= 2:
        return norm >= BM25_SIGNIFICANT
    if matched_terms == 1:
        return norm >= BM25_SINGLE_TERM_SIGNIFICANT
    return False


def keep_candidate(
    cosine: float,
    bm25_raw: float,
    threshold: float,
    matched_terms: int = 0,
) -> bool:
    """生产阈值：无关问题应返回空列表。

    丢弃当且仅当下面两条同时成立：
    1. 该切片的稠密余弦 < threshold（默认 RAG_SCORE_THRESHOLD）；
    2. BM25 不显著。

    显著的定义（见 bm25_is_significant）：
    - 原始分先按 raw / (raw + BM25_NORM_C) 归一化，不用本次最高分做分母；
    - 至少两个查询词命中，且归一化分 >= 0.50；或只命中一个查询词，但归一化分 >= 0.72。
    只蹭到「关系」「一次」这类单字词时归一化分常常超过 0.5，仍视为不显著。

    余弦已经够高就保留。纯稠密候选没有 BM25 分，matched_terms 为 0，退回「只看余弦」。
    """
    try:
        cosine_value = float(cosine)
    except (TypeError, ValueError):
        cosine_value = 0.0
    if cosine_value >= float(threshold):
        return True
    try:
        raw = float(bm25_raw)
    except (TypeError, ValueError):
        raw = 0.0
    try:
        terms = int(matched_terms)
    except (TypeError, ValueError):
        terms = 0
    return bm25_is_significant(raw, terms)


def rrf_fuse(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """名次从 1 开始。同一 id 出现在多路时分数相加。"""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


def fuse_order(
    mode: str,
    dense_ids: list[str],
    bm25_ids: list[str],
    *,
    cosine: dict[str, float],
    bm25: dict[str, float],
    query: str,
    passage_of,
    rerank_fn,
) -> tuple[list[str], dict[str, float], str]:
    """按模式排出候选 id。

    hybrid_rerank 只重排融合后的前 RERANK_WINDOW 条。
    重排模型不可用时 rerank_fn 返回 None，本函数把模式退回 hybrid。
    返回 (有序 id, rrf 分, 实际使用的模式)。
    """
    if mode == "dense":
        rankings = [dense_ids]
    elif mode == "bm25":
        rankings = [bm25_ids]
    else:
        rankings = [dense_ids, bm25_ids]
    rrf = rrf_fuse(rankings)
    if mode == "dense":
        ordered = sorted(dense_ids, key=lambda item: cosine.get(item, -1.0), reverse=True)
    elif mode == "bm25":
        ordered = sorted(bm25_ids, key=lambda item: bm25.get(item, -1.0), reverse=True)
    else:
        ordered = sorted(
            rrf.keys(),
            key=lambda item: (rrf.get(item, 0.0), cosine.get(item, -1.0)),
            reverse=True,
        )
        if mode == "hybrid_rerank":
            head = ordered[:RERANK_WINDOW]
            passages = [passage_of(item) for item in head]
            scores = rerank_fn(query, passages) if head else None
            if not scores or len(scores) != len(head):
                mode = "hybrid"
            else:
                paired = sorted(
                    zip(head, scores),
                    key=lambda item: (float(item[1]), rrf.get(item[0], 0.0)),
                    reverse=True,
                )
                ordered = [item for item, _score in paired]
    return ordered, rrf, mode


class Bm25Index:
    """惰性、可失效的 BM25Okapi 索引。写路径调用 invalidate，下次检索再重建。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._generation = 0
        self._built_gen = -1
        self._ready = False
        self._bm25: BM25Okapi | None = None
        self._records: list[dict] = []

    def invalidate(self) -> None:
        with self._lock:
            self._generation += 1
            self._ready = False

    def build(self, records: list[dict]) -> None:
        """评测或测试直接灌入切片，不走 Chroma。"""
        with self._lock:
            self._install(records)
            self._built_gen = self._generation
            self._ready = True

    def search(self, query: str, top_n: int, doc_types: list[int] | None, loader) -> list[dict]:
        with self._lock:
            self._ensure(loader)
            bm25 = self._bm25
            records = list(self._records)
        if bm25 is None or not records:
            return []
        tokens = tokenize(query)
        if not tokens:
            return []
        unique_tokens = list(dict.fromkeys(tokens))
        scores = bm25.get_scores(tokens)
        allowed = None if not doc_types else {int(item) for item in doc_types}
        ranked: list[tuple[float, int, dict]] = []
        for index, score in enumerate(scores):
            raw = float(score)
            if raw <= 0:
                continue
            record = records[index]
            if allowed is not None:
                meta = record.get("metadata") or {}
                try:
                    doc_type = int(meta.get("doc_type") or 0)
                except (TypeError, ValueError):
                    doc_type = 0
                if doc_type not in allowed:
                    continue
            ranked.append((raw, index, record))
        ranked.sort(key=lambda item: item[0], reverse=True)
        limit = max(1, int(top_n))
        hits = []
        for raw, index, record in ranked[:limit]:
            doc_freq = bm25.doc_freqs[index]
            matched = sum(1 for token in unique_tokens if doc_freq.get(token))
            hits.append(
                {
                    "id": record.get("id") or "",
                    "bm25": raw,
                    "terms": matched,
                    "document": record.get("document") or "",
                    "metadata": record.get("metadata") or {},
                }
            )
        return hits

    def _ensure(self, loader) -> None:
        if self._ready and self._built_gen == self._generation and self._bm25 is not None:
            return
        gen = self._generation
        records = loader() if loader else []
        self._install(records)
        if self._generation == gen:
            self._built_gen = gen
            self._ready = True
        else:
            self._ready = False

    def _install(self, records: list[dict]) -> None:
        usable: list[dict] = []
        tokenized: list[list[str]] = []
        for record in records:
            text = record.get("text") or ""
            tokens = tokenize(text) or ["\u0000"]
            usable.append(record)
            tokenized.append(tokens)
        self._records = usable
        if not tokenized:
            self._bm25 = None
            logger.info("BM25 索引为空")
            return
        self._bm25 = BM25Okapi(tokenized)
        logger.info("BM25 索引已构建，切片 %s", len(tokenized))


_index = Bm25Index()


def get_bm25_index() -> Bm25Index:
    return _index


def invalidate_bm25() -> None:
    _index.invalidate()
