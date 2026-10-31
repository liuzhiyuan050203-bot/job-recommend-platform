"""嵌入向量模型 (FastEmbed) 模块.

基于 FastEmbed 实现单例懒加载的轻量级 CPU 高性能向量嵌入服务，
提供 normalized 向量输出及 LangChain 兼容的 Embeddings 子类包装.
"""

import logging
import threading
from typing import Any, Dict, List, Optional

import numpy as np
from fastembed import TextEmbedding
from langchain_core.embeddings import Embeddings

from app.core.config import settings

logger = logging.getLogger(__name__)

# 内部单例模型与线程锁
_model_instance: Optional[TextEmbedding] = None
_model_lock = threading.Lock()
EMBEDDING_DIMENSION = 512  # BAAI/bge-small-zh-v1.5 默认输出维度


def _get_embedder() -> TextEmbedding:
    """获取或懒加载 FastEmbed TextEmbedding 模型单例."""
    global _model_instance
    if _model_instance is None:
        with _model_lock:
            if _model_instance is None:
                logger.info(
                    f"Lazy loading FastEmbed model '{settings.EMBEDDING_MODEL}' "
                    f"from cache: {settings.EMBEDDING_CACHE_DIR}..."
                )
                _model_instance = TextEmbedding(
                    model_name=settings.EMBEDDING_MODEL,
                    cache_dir=settings.EMBEDDING_CACHE_DIR,
                )
                logger.info("FastEmbed model loaded successfully.")
    return _model_instance


def _normalize_vector(vec: Any) -> List[float]:
    """对嵌入向量执行 L2 归一化并转为标准 Python float 列表."""
    arr = np.array(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


def embed_documents(texts: List[str]) -> List[List[float]]:
    """批量计算文档文本向量，返回归一化后的 float 列表.

    Args:
        texts: 待向量化的文档文本列表

    Returns:
        按顺序对齐的归一化向量列表 (512 维)
    """
    if not texts:
        return []
    embedder = _get_embedder()
    raw_generator = embedder.embed(texts)
    return [_normalize_vector(vec) for vec in raw_generator]


def embed_query(text: str) -> List[float]:
    """计算单个查询字符串的归一化嵌入向量.

    Args:
        text: 用户检索文本

    Returns:
        归一化向量 (512 维)
    """
    if not text or not str(text).strip():
        return [0.0] * EMBEDDING_DIMENSION
    embedder = _get_embedder()
    # BGE 查询侧使用 query_embed（带检索前缀），与文档侧 embed 不对称
    raw = next(iter(embedder.query_embed(str(text))))
    return _normalize_vector(raw)


class FastEmbedEmbeddings(Embeddings):
    """LangChain 兼容的 FastEmbed 向量模型封装器.

    可直接无缝挂载至 LangChain 知识库、Chroma 向量库检索等链条中.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.cache_dir = cache_dir or settings.EMBEDDING_CACHE_DIR

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """实现 LangChain Embeddings.embed_documents 接口."""
        return embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """实现 LangChain Embeddings.embed_query 接口."""
        return embed_query(text)


def get_embedding_model() -> FastEmbedEmbeddings:
    """获取 LangChain 兼容的 FastEmbed 向量包装实例."""
    return FastEmbedEmbeddings()


def health() -> Dict[str, Any]:
    """返回 Embedding 模型基础设施运行状态与配置."""
    global _model_instance
    return {
        "model": settings.EMBEDDING_MODEL,
        "dim": EMBEDDING_DIMENSION,
        "loaded": _model_instance is not None,
        "cache_dir": settings.EMBEDDING_CACHE_DIR,
        "available": True,
    }


def is_available() -> bool:
    """判断向量模型是否就绪."""
    return health().get("available", False)
