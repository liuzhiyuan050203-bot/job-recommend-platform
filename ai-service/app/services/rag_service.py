"""RAG 知识库服务。

检索、切片和向量写入在 app.rag 中实现，这里只保留给路由使用的薄封装。
"""

import logging
from typing import Any

from app.core.config import settings
from app.rag.store import retrieve, stats

logger = logging.getLogger(__name__)


class RagService:
    """知识库状态与调试检索。"""

    def get_status(self) -> dict[str, Any]:
        data = stats()
        data.update(
            {
                "module": "rag",
                "status": "READY",
                "embedding_model": settings.EMBEDDING_MODEL,
                "description": "就业政策、手续问答、求职指导和在架职位的向量检索",
            }
        )
        return data

    def search_knowledge(self, query: str, top_k: int = 4, doc_type: int | None = None) -> dict[str, Any]:
        types = [doc_type] if doc_type else None
        hits = retrieve(query, top_k=top_k, doc_types=types)
        logger.info("知识库检索命中 %s 条", len(hits))
        return {"query": query, "total": len(hits), "results": hits}


rag_service = RagService()
