"""基于 LangChain 检索抽象的混合检索。

组成（全部是 ``langchain_core.retrievers.BaseRetriever``，可以 ``invoke`` / ``ainvoke``，
也能直接放进 LCEL 链）：

* :class:`ChromaDenseRetriever` —— 包一层 ``langchain_chroma.Chroma``（与入库同一个持久集合
  ``job_knowledge``，余弦空间），按 ``doc_type`` 过滤，返回的 Document.metadata 带 ``cosine``；
* :class:`JiebaBM25Retriever` —— 继承 ``langchain_community`` 的 ``BM25Retriever``，用 jieba 分词，
  额外给出原始 BM25 分和命中的查询词个数（阈值规则要用）；
* :class:`HybridRRFRetriever` —— 自定义 RRF 融合 + 生产阈值。没有直接用 ``EnsembleRetriever``：
  它只做加权 RRF，拿不到每条候选的稠密余弦和 BM25 显著性，无法实现「余弦低于阈值且 BM25 不显著
  就丢弃」的拒答规则；融合公式（k=60）与 EnsembleRetriever 相同；
* :class:`CrossEncoderCompressor` + ``ContextualCompressionRetriever`` —— 可选的交叉编码器重排，
  只有 ``RAG_RETRIEVAL_MODE=hybrid_rerank`` 时启用，默认关闭。

融合、阈值的数值规则仍在 ``app.rag.bm25``（``rrf_fuse`` / ``fuse_order`` / ``keep_candidate``），
评测脚本与线上共用同一套。
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Sequence
from typing import Any

from langchain_community.retrievers import BM25Retriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun, Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from rank_bm25 import BM25Okapi

from app.rag.bm25 import RERANK_WINDOW, candidate_pool_size, fuse_order, keep_candidate, tokenize
from app.rag.chunking import embed_input

logger = logging.getLogger(__name__)

RETRIEVAL_MODES = ("dense", "bm25", "hybrid", "hybrid_rerank")


def _bm25_tokens(text: str) -> list[str]:
    return tokenize(text) or ["\u0000"]


def _doc_type_of(meta: dict | None) -> int:
    try:
        return int((meta or {}).get("doc_type") or 0)
    except (TypeError, ValueError):
        return 0


def passage_text(doc: Document) -> str:
    meta = doc.metadata or {}
    return embed_input(meta.get("title") or "", meta.get("section") or "", doc.page_content or "")


def _unit(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(float(v) * float(v) for v in vector))
    return [float(v) / norm for v in vector] if norm > 0 else [float(v) for v in vector]


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return float(sum(float(x) * float(y) for x, y in zip(a, b)))


# --------------------------------------------------------------------------- 稠密


class ChromaDenseRetriever(BaseRetriever):
    """``langchain_chroma.Chroma`` 上的稠密检索。score = 1 - 余弦距离。"""

    vectorstore: Any
    """langchain_chroma.Chroma 实例（持久集合或评测用的内存集合）。"""
    k: int = 20

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
        doc_types: list[int] | None = None,
        k: int | None = None,
        query_vector: list[float] | None = None,
    ) -> list[Document]:
        try:
            total = int(self.vectorstore._collection.count())
        except Exception:
            logger.exception("Chroma 计数失败")
            return []
        if total <= 0:
            return []
        where = None
        if doc_types:
            types = [int(item) for item in doc_types]
            where = {"doc_type": types[0]} if len(types) == 1 else {"doc_type": {"$in": types}}
        vector = query_vector if query_vector is not None else self.vectorstore.embeddings.embed_query(query)
        n_results = min(int(k or self.k), total)
        pairs = None
        while n_results >= 1:
            try:
                # langchain_chroma 这里返回的是原始距离（余弦空间下 = 1 - cos）
                pairs = self.vectorstore.similarity_search_by_vector_with_relevance_scores(
                    vector, k=n_results, filter=where
                )
                break
            except Exception as exc:
                message = str(exc).lower()
                # doc_types 过滤后条数可能小于候选池，Chroma 会拒绝过大的 n_results。
                if n_results > 1 and ("n_results" in message or "greater than" in message or "fewer" in message):
                    n_results = max(1, n_results // 2)
                    continue
                logger.exception("Chroma 检索失败")
                return []
        docs: list[Document] = []
        for doc, distance in pairs or []:
            try:
                cosine = 1.0 - float(distance)
            except (TypeError, ValueError):
                continue
            doc.metadata = {**(doc.metadata or {}), "cosine": cosine}
            docs.append(doc)
        return docs

    def cosine_for(self, query_vector: list[float], docs: list[Document]) -> None:
        """给只被 BM25 召回的切片补算余弦：先读库里的向量，读不到再现算。"""
        if not docs:
            return
        query = _unit(query_vector)
        ids = [doc.id for doc in docs if doc.id]
        found: dict[str, float] = {}
        for offset in range(0, len(ids), 200):
            batch = ids[offset : offset + 200]
            try:
                got = self.vectorstore.get(ids=batch, include=["embeddings"])
            except Exception:
                logger.exception("读取候选向量失败")
                continue
            embeds = got.get("embeddings")
            if embeds is None:
                continue
            for chroma_id, embedding in zip(got.get("ids") or [], embeds):
                if embedding is None or len(embedding) == 0:
                    continue
                found[chroma_id] = _dot(query, _unit(embedding))
        missing = [doc for doc in docs if doc.id not in found]
        if missing:
            try:
                vectors = self.vectorstore.embeddings.embed_documents([passage_text(doc) for doc in missing])
                for doc, embedding in zip(missing, vectors):
                    found[doc.id] = _dot(query, _unit(embedding))
            except Exception:
                logger.exception("BM25 候选补算余弦失败")
        for doc in docs:
            doc.metadata["cosine"] = float(found.get(doc.id, 0.0))


# --------------------------------------------------------------------------- BM25


class JiebaBM25Retriever(BM25Retriever):
    """jieba 分词的 BM25Retriever。page_content 是切片正文，打分文本另拼上标题与章节。"""

    k: int = 20

    @classmethod
    def from_records(cls, records: list[dict], k: int = 20) -> "JiebaBM25Retriever | None":
        """records: [{id, document, metadata, text}]，text 为 bm25_document_text。"""
        if not records:
            return None
        docs = [
            Document(page_content=rec.get("document") or "", metadata=dict(rec.get("metadata") or {}), id=rec.get("id") or "")
            for rec in records
        ]
        tokenized = [_bm25_tokens(rec.get("text") or "") for rec in records]
        return cls(vectorizer=BM25Okapi(tokenized), docs=docs, k=k, preprocess_func=_bm25_tokens)

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
        doc_types: list[int] | None = None,
        k: int | None = None,
        **_: Any,
    ) -> list[Document]:
        tokens = tokenize(query)
        if not tokens or self.vectorizer is None:
            return []
        unique_tokens = list(dict.fromkeys(tokens))
        scores = self.vectorizer.get_scores(tokens)
        allowed = None if not doc_types else {int(item) for item in doc_types}
        ranked: list[tuple[float, int]] = []
        for index, score in enumerate(scores):
            raw = float(score)
            if raw <= 0:
                continue
            if allowed is not None and _doc_type_of(self.docs[index].metadata) not in allowed:
                continue
            ranked.append((raw, index))
        ranked.sort(key=lambda item: item[0], reverse=True)
        out: list[Document] = []
        for raw, index in ranked[: max(1, int(k or self.k))]:
            source = self.docs[index]
            doc_freq = self.vectorizer.doc_freqs[index]
            matched = sum(1 for token in unique_tokens if doc_freq.get(token))
            out.append(
                Document(
                    page_content=source.page_content,
                    metadata={**source.metadata, "bm25": raw, "bm25_terms": matched},
                    id=source.id,
                )
            )
        return out


# --------------------------------------------------------------------------- 融合


class HybridRRFRetriever(BaseRetriever):
    """稠密 + BM25 的 RRF 融合（k=60），再按生产阈值过滤。

    mode=dense / bm25 时只走一路；hybrid_rerank 时返回融合后前 RERANK_WINDOW 条（已过阈值），
    交给外层 ContextualCompressionRetriever 重排并截到 top_k。
    """

    dense: ChromaDenseRetriever | None = None
    bm25: Any = None
    """JiebaBM25Retriever，或返回它的无参函数（索引失效后惰性重建）。"""
    embeddings: Embeddings | None = None
    mode: str = "hybrid"
    top_k: int = 4
    threshold: float = 0.5
    pool: int | None = None
    apply_threshold: bool = True

    def _bm25(self) -> JiebaBM25Retriever | None:
        return self.bm25() if callable(self.bm25) and not isinstance(self.bm25, BaseRetriever) else self.bm25

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
        doc_types: list[int] | None = None,
    ) -> list[Document]:
        query = (query or "").strip()
        if not query:
            return []
        mode = self.mode if self.mode in RETRIEVAL_MODES else "hybrid"
        pool = int(self.pool or candidate_pool_size(self.top_k))
        if self.dense is not None:
            try:
                total = int(self.dense.vectorstore._collection.count())
            except Exception:
                logger.exception("Chroma 计数失败")
                return []
            if total <= 0:
                return []
            pool = min(pool, total)
        embeddings = self.embeddings or (self.dense.vectorstore.embeddings if self.dense is not None else None)
        vector = embeddings.embed_query(query) if embeddings is not None else None
        child = run_manager.get_child()

        by_id: dict[str, Document] = {}
        dense_ids: list[str] = []
        bm25_ids: list[str] = []
        if mode != "bm25" and self.dense is not None:
            for doc in self.dense.invoke(
                query, {"callbacks": child}, doc_types=doc_types, k=pool, query_vector=vector
            ):
                if not doc.id or doc.id in by_id:
                    continue
                doc.metadata.setdefault("bm25", 0.0)
                doc.metadata.setdefault("bm25_terms", 0)
                by_id[doc.id] = doc
                dense_ids.append(doc.id)
        bm25 = self._bm25()
        if mode != "dense" and bm25 is not None:
            for doc in bm25.invoke(query, {"callbacks": child}, doc_types=doc_types, k=pool):
                if not doc.id:
                    continue
                if doc.id in by_id:
                    by_id[doc.id].metadata["bm25"] = doc.metadata["bm25"]
                    by_id[doc.id].metadata["bm25_terms"] = doc.metadata["bm25_terms"]
                else:
                    by_id[doc.id] = doc
                if doc.id not in bm25_ids:
                    bm25_ids.append(doc.id)
        if not by_id:
            return []
        missing = [doc for doc in by_id.values() if "cosine" not in doc.metadata]
        if missing:
            if self.dense is not None and vector is not None:
                self.dense.cosine_for(vector, missing)
            for doc in missing:
                doc.metadata.setdefault("cosine", 0.0)

        cosine = {key: float(doc.metadata.get("cosine") or 0.0) for key, doc in by_id.items()}
        bm25_scores = {key: float(doc.metadata.get("bm25") or 0.0) for key, doc in by_id.items()}
        # 重排交给外层压缩器，这里按 hybrid 排序，只截出重排窗口
        ordered, rrf, _used = fuse_order(
            "hybrid" if mode == "hybrid_rerank" else mode,
            dense_ids,
            bm25_ids,
            cosine=cosine,
            bm25=bm25_scores,
            query=query,
            passage_of=lambda key: passage_text(by_id[key]),
            rerank_fn=lambda _q, _p: None,
        )
        if mode == "hybrid_rerank":
            ordered = ordered[:RERANK_WINDOW]
        limit = len(ordered) if mode == "hybrid_rerank" or self.top_k <= 0 else self.top_k
        out: list[Document] = []
        for key in ordered:
            doc = by_id[key]
            if self.apply_threshold and not keep_candidate(
                cosine[key], bm25_scores[key], self.threshold, int(doc.metadata.get("bm25_terms") or 0)
            ):
                continue
            doc.metadata["rrf"] = float(rrf.get(key, 0.0))
            doc.metadata["retrieval_mode"] = mode
            out.append(doc)
            if len(out) >= limit:
                break
        return out


class CrossEncoderCompressor(BaseDocumentCompressor):
    """交叉编码器重排（BAAI/bge-reranker-base）。模型不可用时保持 RRF 顺序，模式记为 hybrid。"""

    top_n: int = 4
    scorer: Callable[[str, list[str]], list[float] | None] | None = None

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> Sequence[Document]:
        docs = list(documents)
        if not docs:
            return []
        scorer = self.scorer
        if scorer is None:
            from app.rag.rerank import rerank_scores as scorer
        scores = scorer(query, [passage_text(doc) for doc in docs])
        if not scores or len(scores) != len(docs):
            for doc in docs:
                doc.metadata["retrieval_mode"] = "hybrid"
            return docs[: self.top_n]
        paired = sorted(
            zip(docs, scores),
            key=lambda item: (float(item[1]), float(item[0].metadata.get("rrf") or 0.0)),
            reverse=True,
        )
        out = []
        for doc, score in paired[: self.top_n]:
            doc.metadata["rerank"] = float(score)
            out.append(doc)
        return out


def build_retriever(
    *,
    dense: ChromaDenseRetriever | None,
    bm25: Any,
    mode: str = "hybrid",
    top_k: int = 4,
    threshold: float = 0.5,
    pool: int | None = None,
    apply_threshold: bool = True,
    embeddings: Embeddings | None = None,
    rerank_scorer: Callable[[str, list[str]], list[float] | None] | None = None,
) -> BaseRetriever:
    """按模式组装检索器。hybrid_rerank 外面套 ContextualCompressionRetriever。"""
    mode = (mode or "hybrid").strip().lower()
    if mode not in RETRIEVAL_MODES:
        logger.warning("未知检索模式 %s，改用 hybrid", mode)
        mode = "hybrid"
    base = HybridRRFRetriever(
        dense=dense,
        bm25=bm25,
        embeddings=embeddings,
        mode=mode,
        top_k=top_k,
        threshold=threshold,
        pool=pool,
        apply_threshold=apply_threshold,
    )
    if mode != "hybrid_rerank":
        return base
    from langchain_classic.retrievers import ContextualCompressionRetriever

    return ContextualCompressionRetriever(
        base_compressor=CrossEncoderCompressor(top_n=top_k, scorer=rerank_scorer),
        base_retriever=base,
    )
