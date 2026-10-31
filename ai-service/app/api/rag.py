"""RAG 知识库查询与管理接口。

/rag/search 与 /rag/admin 需要 X-Internal-Token。
/rag 与 /rag/status 只返回规模信息，保持公开以便健康检查。
"""

import asyncio

from fastapi import APIRouter, File, Form, Query, UploadFile

from app.core.response import AppException, success
from app.rag.ingest import ingest_all, ingest_source, reindex_doc_key, save_upload
from app.rag.store import delete_doc, list_documents, stats, sync_documents
from app.services.rag_service import rag_service

router = APIRouter(prefix="/rag", tags=["RAG Knowledge"])


@router.get("", summary="RAG 模块基本信息")
@router.get("/", summary="RAG 模块基本信息")
async def get_rag_info():
    return success(data=rag_service.get_status(), msg="RAG service status retrieved")


@router.get("/status", summary="RAG 向量库状态")
async def get_rag_status():
    return success(data=rag_service.get_status(), msg="RAG service status retrieved")


@router.get("/search", summary="知识库检索")
async def search_knowledge(
    q: str = Query(default="", description="检索问题"),
    top_k: int = Query(default=4, ge=1, le=10),
    doc_type: int | None = Query(default=None, ge=1, le=7, description="按文档类型过滤"),
):
    if not q.strip():
        raise AppException("检索问题不能为空", code=400)
    results = await asyncio.to_thread(rag_service.search_knowledge, q.strip(), top_k, doc_type)
    return success(data=results, msg="Knowledge base search completed")


@router.get("/admin/documents", summary="按逻辑文档分页")
async def admin_documents(
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=50),
    doc_type: int | None = Query(default=None, ge=1, le=7),
    source_type: int | None = Query(default=None, ge=1, le=6),
    q: str = Query(default=""),
):
    data = await asyncio.to_thread(list_documents, current, size, doc_type, source_type, q.strip())
    return success(data=data, msg="文档列表")


@router.get("/admin/stats", summary="知识库统计")
async def admin_stats():
    data = await asyncio.to_thread(stats)
    return success(data=data, msg="知识库统计")


@router.post("/admin/upload", summary="上传 Markdown 或文本")
async def admin_upload(
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: int = Form(...),
):
    if doc_type not in range(1, 8):
        raise AppException("doc_type 取值应为 1 到 7", code=400)
    if not title.strip():
        raise AppException("标题不能为空", code=400)
    raw = await file.read()
    if not raw:
        raise AppException("文件为空", code=400)
    if len(raw) > 512 * 1024:
        raise AppException("文件不能超过 512KB", code=400)
    try:
        doc = save_upload(file.filename or "upload.md", raw, title.strip(), doc_type)
        result = await asyncio.to_thread(sync_documents, [doc])
    except ValueError as exc:
        raise AppException(str(exc), code=400) from exc
    return success(
        data={"docKey": doc.doc_key, "title": doc.title, "docType": doc.doc_type, **result},
        msg="上传并索引完成",
    )


@router.post("/admin/reindex", summary="重建一个文档或一类来源")
async def admin_reindex(
    source: str | None = Query(default=None, description="knowledge、cms、jobs、uploads、all"),
    doc_key: str | None = Query(default=None),
    rebuild: bool = Query(default=False),
):
    try:
        if doc_key:
            data = await asyncio.to_thread(reindex_doc_key, doc_key.strip())
        elif source in {None, "", "all"}:
            data = await asyncio.to_thread(ingest_all, True)
        elif source in {"knowledge", "cms", "jobs", "uploads"}:
            data = await asyncio.to_thread(ingest_source, source, rebuild)
        else:
            raise AppException("source 不合法", code=400)
    except ValueError as exc:
        raise AppException(str(exc), code=400) from exc
    return success(data=data, msg="重新索引完成")


@router.delete("/admin/documents", summary="删除一个逻辑文档")
async def admin_delete(doc_key: str = Query(..., min_length=1)):
    removed = await asyncio.to_thread(delete_doc, doc_key.strip())
    return success(data={"docKey": doc_key.strip(), "deletedChunks": removed}, msg="已删除")
