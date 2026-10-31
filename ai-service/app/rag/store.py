"""Chroma 持久集合与 rag_document 的写入、删除和检索。

重索引策略：同一 doc_key 的切片若标题、章节、正文哈希都未变且已入库，则跳过；
否则先按 chroma_id 删除向量，再物理删除 MySQL 行，然后重新写入。
不做逻辑删除，避免职位全量重建时留下上万行历史切片。
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

import chromadb

from app.core.config import settings
from app.core.embedding import embed_documents, embed_query
from app.rag.chunking import content_hash, embed_input
from app.rag.constants import COLLECTION
from app.spark.db import connect

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client: chromadb.PersistentClient | None = None


@dataclass
class ChunkRecord:
    section: str
    content: str
    chunk_no: int = 0
    content_hash: str = ""
    mysql_id: int | None = None


@dataclass
class LogicalDoc:
    doc_key: str
    doc_type: int
    source_type: int
    source_id: int | None
    title: str
    ref: str
    chunks: list[ChunkRecord] = field(default_factory=list)


def _collection_name() -> str:
    return settings.RAG_COLLECTION or COLLECTION


def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                path = settings.CHROMA_DIR
                from pathlib import Path

                Path(path).mkdir(parents=True, exist_ok=True)
                _client = chromadb.PersistentClient(path=path)
    return _client


def get_collection(rebuild: bool = False):
    """获取余弦空间的持久集合。rebuild 时删除后重建。"""
    client = get_client()
    name = _collection_name()
    with _lock:
        if rebuild:
            try:
                client.delete_collection(name)
            except Exception:
                logger.info("集合 %s 不存在或已删除", name)
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )


def reset_collection() -> None:
    get_collection(rebuild=True)


def chroma_count() -> int:
    try:
        return int(get_collection().count())
    except Exception:
        logger.exception("读取 Chroma 计数失败")
        return 0


def _existing_map(doc_keys: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not doc_keys:
        return {}
    found: dict[str, list[dict[str, Any]]] = {key: [] for key in doc_keys}
    conn = connect()
    try:
        with conn.cursor() as cur:
            for offset in range(0, len(doc_keys), 200):
                batch = doc_keys[offset : offset + 200]
                marks = ", ".join(["%s"] * len(batch))
                cur.execute(
                    f"""
                    SELECT id, doc_key, chunk_no, content_hash, chroma_id, embed_status
                    FROM rag_document
                    WHERE deleted = 0 AND doc_key IN ({marks})
                    ORDER BY doc_key, chunk_no
                    """,
                    batch,
                )
                for row in cur.fetchall():
                    found.setdefault(row["doc_key"], []).append(row)
    finally:
        conn.close()
    return found


def _unchanged(doc: LogicalDoc, rows: list[dict[str, Any]]) -> bool:
    if not rows or len(rows) != len(doc.chunks):
        return False
    rows = sorted(rows, key=lambda item: int(item["chunk_no"]))
    for chunk, row in zip(doc.chunks, rows):
        if int(row["chunk_no"]) != chunk.chunk_no:
            return False
        if (row.get("content_hash") or "") != chunk.content_hash:
            return False
        if int(row.get("embed_status") or 0) != 1 or not row.get("chroma_id"):
            return False
    return True


def _delete_docs(doc_keys: list[str], chroma_ids: list[str]) -> None:
    if chroma_ids:
        collection = get_collection()
        for offset in range(0, len(chroma_ids), 200):
            batch = [item for item in chroma_ids[offset : offset + 200] if item]
            if not batch:
                continue
            try:
                collection.delete(ids=batch)
            except Exception:
                logger.exception("删除 Chroma 向量失败，数量 %s", len(batch))
    if not doc_keys:
        return
    conn = connect()
    try:
        with conn.cursor() as cur:
            for offset in range(0, len(doc_keys), 200):
                batch = doc_keys[offset : offset + 200]
                marks = ", ".join(["%s"] * len(batch))
                cur.execute(f"DELETE FROM rag_document WHERE doc_key IN ({marks})", batch)
    finally:
        conn.close()


def _insert_rows(docs: list[LogicalDoc]) -> None:
    sql = """
        INSERT INTO rag_document (
            doc_type, title, doc_key, source_type, source_id, chunk_no, section,
            content, content_hash, chroma_collection, embed_status, deleted
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0)
    """
    conn = connect()
    try:
        conn.autocommit(False)
        with conn.cursor() as cur:
            for doc in docs:
                for chunk in doc.chunks:
                    cur.execute(
                        sql,
                        (
                            doc.doc_type,
                            doc.title[:128],
                            doc.doc_key[:128],
                            doc.source_type,
                            doc.source_id,
                            chunk.chunk_no,
                            (chunk.section or "")[:128] or None,
                            chunk.content,
                            chunk.content_hash,
                            _collection_name(),
                        ),
                    )
                    chunk.mysql_id = int(cur.lastrowid)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _mark_embedded(chunks: list[ChunkRecord], ok: bool) -> None:
    if not chunks:
        return
    conn = connect()
    try:
        with conn.cursor() as cur:
            for chunk in chunks:
                if not chunk.mysql_id:
                    continue
                if ok:
                    cur.execute(
                        """
                        UPDATE rag_document
                        SET embed_status = 1, chroma_id = %s, chroma_collection = %s
                        WHERE id = %s
                        """,
                        (f"rag-{chunk.mysql_id}", _collection_name(), chunk.mysql_id),
                    )
                else:
                    cur.execute(
                        "UPDATE rag_document SET embed_status = 2 WHERE id = %s",
                        (chunk.mysql_id,),
                    )
    finally:
        conn.close()


def _upsert_vectors(docs: list[LogicalDoc]) -> None:
    collection = get_collection()
    texts: list[str] = []
    owners: list[tuple[LogicalDoc, ChunkRecord]] = []
    for doc in docs:
        for chunk in doc.chunks:
            texts.append(embed_input(doc.title, chunk.section, chunk.content))
            owners.append((doc, chunk))
    if not texts:
        return
    batch = 64
    for offset in range(0, len(texts), batch):
        slice_owners = owners[offset : offset + batch]
        slice_chunks = [chunk for _doc, chunk in slice_owners]
        try:
            vectors = embed_documents(texts[offset : offset + batch])
            ids = []
            embeddings = []
            documents = []
            metadatas = []
            for (doc, chunk), vector in zip(slice_owners, vectors):
                ids.append(f"rag-{chunk.mysql_id}")
                embeddings.append(vector)
                documents.append(chunk.content)
                metadatas.append(
                    {
                        "rag_doc_id": int(chunk.mysql_id or 0),
                        "doc_type": int(doc.doc_type),
                        "source_type": int(doc.source_type),
                        "source_id": int(doc.source_id or 0),
                        "title": doc.title[:120],
                        "section": (chunk.section or "")[:120],
                        "chunk_no": int(chunk.chunk_no),
                        "doc_key": doc.doc_key[:120],
                        "ref": (doc.ref or "")[:200],
                    }
                )
            collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
            _mark_embedded(slice_chunks, ok=True)
        except Exception:
            logger.exception("向量批次写入失败，起始偏移 %s", offset)
            _mark_embedded(slice_chunks, ok=False)


def prepare_doc(doc: LogicalDoc) -> None:
    for index, chunk in enumerate(doc.chunks):
        chunk.chunk_no = index
        chunk.content_hash = content_hash(doc.title, chunk.section, chunk.content)


def sync_documents(docs: list[LogicalDoc]) -> dict[str, int]:
    """按 doc_key 增量写入。返回 skipped / rewritten / chunks。"""
    prepared = []
    for doc in docs:
        if not doc.doc_key or not doc.chunks:
            continue
        prepare_doc(doc)
        prepared.append(doc)
    if not prepared:
        return {"skipped": 0, "rewritten": 0, "chunks": 0}
    existing = _existing_map([doc.doc_key for doc in prepared])
    skipped = 0
    changed: list[LogicalDoc] = []
    delete_ids: list[str] = []
    delete_keys: list[str] = []
    for doc in prepared:
        rows = existing.get(doc.doc_key) or []
        if _unchanged(doc, rows):
            skipped += 1
            continue
        changed.append(doc)
        delete_keys.append(doc.doc_key)
        delete_ids.extend([row.get("chroma_id") or "" for row in rows])
    if changed:
        _delete_docs(delete_keys, [item for item in delete_ids if item])
        _insert_rows(changed)
        _upsert_vectors(changed)
    chunk_count = sum(len(doc.chunks) for doc in changed)
    return {"skipped": skipped, "rewritten": len(changed), "chunks": chunk_count}


def prune_doc_keys(doc_keys: list[str]) -> int:
    """物理删除一批逻辑文档。"""
    keys = [key for key in doc_keys if key]
    if not keys:
        return 0
    rows_map = _existing_map(keys)
    ids: list[str] = []
    for key in keys:
        ids.extend(row.get("chroma_id") or "" for row in rows_map.get(key) or [])
    _delete_docs(keys, ids)
    return len(keys)


def list_doc_keys(source_type: int | None = None, prefix: str | None = None) -> list[str]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            sql = "SELECT DISTINCT doc_key FROM rag_document WHERE deleted = 0 AND doc_key IS NOT NULL"
            params: list[Any] = []
            if source_type is not None:
                sql += " AND source_type = %s"
                params.append(int(source_type))
            if prefix:
                sql += " AND doc_key LIKE %s"
                params.append(prefix + "%")
            cur.execute(sql, params)
            return [row["doc_key"] for row in cur.fetchall()]
    finally:
        conn.close()


def delete_doc(doc_key: str) -> int:
    rows = _existing_map([doc_key]).get(doc_key) or []
    if not rows and not doc_key:
        return 0
    _delete_docs([doc_key], [row.get("chroma_id") or "" for row in rows])
    return len(rows)


def delete_by_source(source_type: int) -> int:
    """按来源物理删除切片和对应向量。"""
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT doc_key, chroma_id FROM rag_document WHERE source_type = %s",
                (int(source_type),),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    keys = list({row["doc_key"] for row in rows if row.get("doc_key")})
    ids = [row.get("chroma_id") or "" for row in rows]
    _delete_docs(keys, ids)
    return len(rows)


def delete_all_rows() -> int:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rag_document")
            return int(cur.rowcount)
    finally:
        conn.close()


def retrieve(
    query: str,
    top_k: int | None = None,
    doc_types: list[int] | None = None,
    score_threshold: float | None = None,
) -> list[dict[str, Any]]:
    """按余弦相似度检索。分数为 1 - Chroma cosine distance，低于阈值的丢弃。"""
    top_k = top_k or settings.RAG_TOP_K
    top_k = max(1, min(int(top_k), 10))
    threshold = settings.RAG_SCORE_THRESHOLD if score_threshold is None else float(score_threshold)
    query = (query or "").strip()
    if not query:
        return []
    collection = get_collection()
    try:
        total = int(collection.count())
    except Exception:
        logger.exception("Chroma 计数失败")
        return []
    if total <= 0:
        return []
    where = None
    if doc_types:
        types = [int(item) for item in doc_types]
        where = {"doc_type": types[0]} if len(types) == 1 else {"doc_type": {"$in": types}}
    n_results = min(max(top_k * 2, top_k), total)
    vector = embed_query(query)
    try:
        result = collection.query(
            query_embeddings=[vector],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        logger.exception("Chroma 检索失败")
        return []
    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    hits: list[dict[str, Any]] = []
    for chroma_id, document, meta, distance in zip(ids, docs, metas, distances):
        meta = meta or {}
        try:
            score = 1.0 - float(distance)
        except (TypeError, ValueError):
            continue
        if score < threshold:
            continue
        source_id = int(meta.get("source_id") or 0)
        hits.append(
            {
                "chroma_id": chroma_id,
                "rag_doc_id": int(meta.get("rag_doc_id") or 0),
                "doc_type": int(meta.get("doc_type") or 0),
                "source_type": int(meta.get("source_type") or 0),
                "source_id": source_id or None,
                "title": meta.get("title") or "",
                "section": meta.get("section") or "",
                "chunk_no": int(meta.get("chunk_no") or 0),
                "doc_key": meta.get("doc_key") or "",
                "ref": meta.get("ref") or "",
                "content": document or "",
                "score": round(score, 4),
            }
        )
    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[:top_k]


def list_documents(
    current: int = 1,
    size: int = 10,
    doc_type: int | None = None,
    source_type: int | None = None,
    keyword: str = "",
) -> dict[str, Any]:
    current = max(1, int(current))
    size = max(1, min(int(size), 50))
    offset = (current - 1) * size
    where = ["deleted = 0"]
    params: list[Any] = []
    if doc_type is not None:
        where.append("doc_type = %s")
        params.append(int(doc_type))
    if source_type is not None:
        where.append("source_type = %s")
        params.append(int(source_type))
    if keyword:
        where.append("(title LIKE %s OR doc_key LIKE %s)")
        like = f"%{keyword.strip()}%"
        params.extend([like, like])
    clause = " AND ".join(where)
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(DISTINCT doc_key) AS cnt FROM rag_document WHERE {clause}", params)
            total = int(cur.fetchone()["cnt"])
            cur.execute(
                f"""
                SELECT doc_key,
                       MAX(title) AS title,
                       MIN(doc_type) AS doc_type,
                       MIN(source_type) AS source_type,
                       MAX(source_id) AS source_id,
                       COUNT(*) AS chunk_count,
                       SUM(embed_status = 1) AS embedded,
                       SUM(embed_status = 2) AS failed,
                       MAX(update_time) AS update_time
                FROM rag_document
                WHERE {clause}
                GROUP BY doc_key
                ORDER BY update_time DESC
                LIMIT %s OFFSET %s
                """,
                [*params, size, offset],
            )
            rows = []
            for row in cur.fetchall():
                updated = row["update_time"]
                rows.append(
                    {
                        "docKey": row["doc_key"],
                        "title": row["title"],
                        "docType": int(row["doc_type"]),
                        "sourceType": int(row["source_type"]),
                        "sourceId": int(row["source_id"]) if row["source_id"] is not None else None,
                        "chunkCount": int(row["chunk_count"]),
                        "embedded": int(row["embedded"] or 0),
                        "failed": int(row["failed"] or 0),
                        "updateTime": updated.strftime("%Y-%m-%d %H:%M:%S") if updated else None,
                    }
                )
    finally:
        conn.close()
    return {"current": current, "size": size, "total": total, "records": rows}


def stats() -> dict[str, Any]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(DISTINCT doc_key) AS docs, COUNT(*) AS chunks
                FROM rag_document WHERE deleted = 0
                """
            )
            head = cur.fetchone()
            cur.execute(
                """
                SELECT doc_type, COUNT(DISTINCT doc_key) AS docs, COUNT(*) AS chunks
                FROM rag_document WHERE deleted = 0
                GROUP BY doc_type ORDER BY doc_type
                """
            )
            by_type = [
                {"docType": int(row["doc_type"]), "docs": int(row["docs"]), "chunks": int(row["chunks"])}
                for row in cur.fetchall()
            ]
            cur.execute(
                """
                SELECT source_type, COUNT(DISTINCT doc_key) AS docs, COUNT(*) AS chunks
                FROM rag_document WHERE deleted = 0
                GROUP BY source_type ORDER BY source_type
                """
            )
            by_source = [
                {"sourceType": int(row["source_type"]), "docs": int(row["docs"]), "chunks": int(row["chunks"])}
                for row in cur.fetchall()
            ]
            cur.execute(
                """
                SELECT embed_status, COUNT(*) AS chunks
                FROM rag_document WHERE deleted = 0
                GROUP BY embed_status ORDER BY embed_status
                """
            )
            by_status = [
                {"embedStatus": int(row["embed_status"]), "chunks": int(row["chunks"])} for row in cur.fetchall()
            ]
    finally:
        conn.close()
    return {
        "collection": _collection_name(),
        "documents": int(head["docs"] or 0),
        "chunks": int(head["chunks"] or 0),
        "chromaCount": chroma_count(),
        "scoreThreshold": settings.RAG_SCORE_THRESHOLD,
        "byDocType": by_type,
        "bySourceType": by_source,
        "byEmbedStatus": by_status,
    }
