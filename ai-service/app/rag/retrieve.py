"""面向智能体的检索入口。分数低于阈值的切片不会返回；近域问题再经范围门槛过滤。"""

from __future__ import annotations

from app.rag.scope import apply_scope_gate
from app.rag.store import retrieve


def fetch_chunks(query: str, doc_types: list[int] | None = None, top_k: int | None = None) -> list[dict]:
    hits = retrieve(query, top_k=top_k, doc_types=doc_types or None)
    return apply_scope_gate(query, hits)
