"""可选的交叉编码器重排。模型加载失败时返回 None，调用方退回 hybrid。"""

from __future__ import annotations

import logging
import threading

from app.core.config import settings

logger = logging.getLogger(__name__)

RERANK_MODEL = "BAAI/bge-reranker-base"

_lock = threading.Lock()
_model = None
_failed = False


def rerank_available() -> bool:
    return _model is not None and not _failed


def load_reranker():
    """加载 BAAI/bge-reranker-base，CPU，缓存目录与嵌入模型相同。失败返回 None。"""
    global _model, _failed
    if _model is not None:
        return _model
    if _failed:
        return None
    with _lock:
        if _model is not None:
            return _model
        if _failed:
            return None
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            logger.info("加载重排模型 %s，缓存 %s", RERANK_MODEL, settings.EMBEDDING_CACHE_DIR)
            _model = TextCrossEncoder(
                model_name=RERANK_MODEL,
                cache_dir=settings.EMBEDDING_CACHE_DIR,
                cuda=False,
            )
            logger.info("重排模型已加载")
            return _model
        except Exception:
            logger.exception("重排模型 %s 加载失败，检索退回 hybrid", RERANK_MODEL)
            _failed = True
            return None


def rerank_scores(query: str, passages: list[str]) -> list[float] | None:
    """对 passages 打分。模型不可用或推理失败时返回 None，不抛给检索主路径。"""
    if not passages:
        return []
    model = load_reranker()
    if model is None:
        return None
    try:
        return [float(score) for score in model.rerank(query, passages)]
    except Exception:
        logger.exception("重排推理失败，本查询退回 hybrid")
        return None
