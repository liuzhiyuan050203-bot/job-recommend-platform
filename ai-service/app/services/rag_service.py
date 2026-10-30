"""RAG (检索增强生成) 与向量知识库服务 (占位实现).

职责:
1. 基于 Chroma 向量数据库管理就业政策、校招指南、面经与企业信息
2. 文本向量化与相似度检索
3. 知识上下文检索并组装 Prompt 供给 Agent 调用
"""

import logging
from typing import Any, Dict, List

from app.core.config import settings

logger = logging.getLogger(__name__)


class RagService:
    """RAG 知识检索与向量库服务."""

    def __init__(self) -> None:
        self.chroma_dir = settings.CHROMA_DIR
        self.collection_name = "job_knowledge_base"

    def get_status(self) -> Dict[str, Any]:
        """获取 RAG 模块运行状态与向量库配置."""
        return {
            "module": "rag",
            "status": "READY",
            "chroma_dir": self.chroma_dir,
            "collection_name": self.collection_name,
            "embedding_model": "text-embedding-placeholder",
            "vector_count": 128,
            "description": "基于 Chroma 与 LangChain 的高校就业政策/面经知识库检索引擎",
        }

    def search_knowledge(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """检索知识库匹配的相关文档片段 (占位实现)."""
        logger.info(f"Searching knowledge base for query: {query}, top_k={top_k}")
        documents: List[Dict[str, Any]] = [
            {
                "doc_id": "doc-policy-2026",
                "title": "2026届高校毕业生就业创业支持政策通知",
                "content": "对到中西部地区、艰苦边远地区基层单位就业的高校毕业生，按规定给予学费补偿和国家助学贷款代偿。",
                "score": 0.92,
                "category": "就业政策",
            },
            {
                "doc_id": "doc-interview-java",
                "title": "互联网大厂Java开发校招高频面试核心要点",
                "content": "重点考察 JVM 内存模型与 GC 机制、Spring 事务失效场景、MySQL 索引优化及 Redis 分布式锁实现方案。",
                "score": 0.88,
                "category": "面试经验",
            },
            {
                "doc_id": "doc-guide-resume",
                "title": "应届生技术简历撰写指南：STAR法则与量化成果",
                "content": "技术简历需重点突出项目背景、技术选型难点、个人贡献与量化指标，技能清单按熟悉程度降序排列。",
                "score": 0.83,
                "category": "简历指导",
            },
        ]
        return {
            "query": query,
            "total": len(documents),
            "results": documents[:top_k],
        }


rag_service = RagService()
