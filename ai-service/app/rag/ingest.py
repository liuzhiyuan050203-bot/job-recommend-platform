"""从知识库文件、公告、在招职位和管理员上传重建 RAG 索引。

命令：
    cd ai-service && ../.venv/bin/python -m app.rag.ingest --all

--all 会清空 Chroma 集合和 rag_document 后全量重建。
同一 doc_key 内容未变时跳过向量计算。下架职位、删除的文件会从索引中移除。
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

from app.core.config import AI_SERVICE_DIR, settings
from app.rag.chunking import split_markdown, split_text
from app.rag.constants import CMS_TYPE_MAP, KNOWLEDGE_DOC_RULES
from app.rag.store import (
    ChunkRecord,
    LogicalDoc,
    delete_all_rows,
    delete_by_source,
    list_doc_keys,
    prune_doc_keys,
    reset_collection,
    stats,
    sync_documents,
)
from app.spark.db import connect

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = AI_SERVICE_DIR.parent / "data" / "knowledge"
UPLOAD_DIR = Path(settings.CHROMA_DIR).parent / "uploads"

EDU_LABEL = {0: "学历不限", 1: "专科", 2: "本科", 3: "硕士", 4: "博士"}
EXP_LABEL = {0: "经验不限", 1: "应届生", 2: "一年以内", 3: "一到三年", 4: "三到五年", 5: "五年以上"}

def doc_type_for_filename(name: str) -> int:
    for keyword, doc_type in KNOWLEDGE_DOC_RULES:
        if keyword in name:
            return doc_type
    return 5


def _chunks_of(text: str) -> list[ChunkRecord]:
    text = (text or "").replace("\r\n", "\n").strip()
    if len(text) < 8:
        return []
    if re.search(r"(?m)^#{1,3}\s+", text):
        parts = split_markdown(text)
    else:
        parts = [("", piece) for piece in split_text(text)]
    records = []
    for section, content in parts:
        content = content.strip()
        if len(content) < 8:
            continue
        records.append(ChunkRecord(section=section, content=content))
    return records


def _sync_batched(docs: list[LogicalDoc], batch: int = 300) -> dict[str, int]:
    total = {"skipped": 0, "rewritten": 0, "chunks": 0, "documents": len(docs)}
    if not docs:
        return total
    for offset in range(0, len(docs), batch):
        part = sync_documents(docs[offset : offset + batch])
        for key in ("skipped", "rewritten", "chunks"):
            total[key] += part[key]
        logger.info(
            "索引进度 %s/%s，本批跳过 %s、重写 %s",
            min(offset + batch, len(docs)),
            len(docs),
            part["skipped"],
            part["rewritten"],
        )
    return total


def load_knowledge() -> list[LogicalDoc]:
    docs: list[LogicalDoc] = []
    if not KNOWLEDGE_DIR.is_dir():
        logger.warning("知识库目录不存在: %s", KNOWLEDGE_DIR)
        return docs
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = _markdown_title(text) or path.stem
        chunks = _chunks_of(text)
        if not chunks:
            logger.info("跳过过短文件 %s", path.name)
            continue
        docs.append(
            LogicalDoc(
                doc_key=f"kb:{path.name}"[:128],
                doc_type=doc_type_for_filename(path.name),
                source_type=4,
                source_id=None,
                title=title[:128],
                ref=f"data/knowledge/{path.name}",
                chunks=chunks,
            )
        )
    return docs


def load_uploads() -> list[LogicalDoc]:
    docs: list[LogicalDoc] = []
    if not UPLOAD_DIR.is_dir():
        return docs
    for path in sorted(UPLOAD_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        if path.name.endswith(".meta.json"):
            continue
        meta = _upload_meta(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        title = meta.get("title") or _markdown_title(text) or path.stem
        chunks = _chunks_of(text)
        if not chunks:
            continue
        docs.append(
            LogicalDoc(
                doc_key=f"upload:{path.name}"[:128],
                doc_type=int(meta.get("doc_type") or 5),
                source_type=6,
                source_id=None,
                title=str(title)[:128],
                ref=f"uploads/{path.name}",
                chunks=chunks,
            )
        )
    return docs


def load_cms() -> list[LogicalDoc]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, article_type, title, summary, content
                FROM cms_article
                WHERE status = 1 AND deleted = 0
                ORDER BY id
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    docs: list[LogicalDoc] = []
    for row in rows:
        article_type = int(row["article_type"])
        doc_type, source_type = CMS_TYPE_MAP.get(article_type, (2, 2))
        parts = [str(row["summary"]).strip() if row.get("summary") else "", str(row["content"] or "").strip()]
        text = f"# {row['title']}\n\n" + "\n\n".join(part for part in parts if part)
        chunks = _chunks_of(text)
        if not chunks:
            logger.info("跳过过短公告 id=%s", row["id"])
            continue
        docs.append(
            LogicalDoc(
                doc_key=f"cms:{row['id']}",
                doc_type=doc_type,
                source_type=source_type,
                source_id=int(row["id"]),
                title=str(row["title"])[:128],
                ref=f"cms:{row['id']}",
                chunks=chunks,
            )
        )
    return docs


def load_job_texts(limit: int | None = None) -> list[dict]:
    """在招职位原文。拼接方式与 load_jobs 相同，limit 只给评测截断干扰项。"""
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SET SESSION group_concat_max_len = 2048")
            sql = """
                SELECT p.id, p.title, p.city, p.tech_direction, p.salary_min, p.salary_max,
                       p.salary_months, p.education, p.experience_req, p.description,
                       p.requirement, p.welfare, c.company_name,
                       (
                         SELECT GROUP_CONCAT(t.name ORDER BY t.name SEPARATOR '、')
                         FROM job_position_tag pt
                         INNER JOIN skill_tag t ON t.id = pt.tag_id AND t.deleted = 0
                         WHERE pt.position_id = p.id AND pt.deleted = 0
                       ) AS skills
                FROM job_position p
                INNER JOIN ent_company c ON c.id = p.company_id AND c.deleted = 0
                WHERE p.deleted = 0 AND p.shelf_status = 1 AND p.audit_status = 1
                ORDER BY p.id
            """
            params: list = []
            if limit is not None:
                sql += " LIMIT %s"
                params.append(max(0, int(limit)))
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()
    items: list[dict] = []
    for row in rows:
        items.append(
            {
                "doc_key": f"job:{row['id']}",
                "title": str(row["title"])[:128],
                "source_id": int(row["id"]),
                "text": _job_text(row),
            }
        )
    return items


def load_jobs(limit: int | None = None) -> list[LogicalDoc]:
    docs: list[LogicalDoc] = []
    for item in load_job_texts(limit):
        chunks = _chunks_of(item["text"])
        if not chunks:
            continue
        docs.append(
            LogicalDoc(
                doc_key=item["doc_key"],
                doc_type=7,
                source_type=5,
                source_id=item["source_id"],
                title=item["title"],
                ref=item["doc_key"],
                chunks=chunks,
            )
        )
    return docs


def _job_text(row: dict) -> str:
    salary = f"{int(row['salary_min'])}-{int(row['salary_max'])}元/月"
    months = int(row["salary_months"] or 12)
    if months != 12:
        salary += f"，{months}薪"
    lines = [
        f"# {row['title']}",
        f"公司：{row['company_name']}",
        f"城市：{row['city']}",
        f"方向：{row['tech_direction']}",
        f"薪资：{salary}",
        f"学历：{EDU_LABEL.get(int(row['education'] or 0), '不限')}",
        f"经验：{EXP_LABEL.get(int(row['experience_req'] or 0), '不限')}",
        f"技能：{row['skills'] or '未标注'}",
    ]
    if row.get("description"):
        lines.append("职责：" + str(row["description"]).strip()[:500])
    if row.get("requirement"):
        lines.append("要求：" + str(row["requirement"]).strip()[:300])
    if row.get("welfare"):
        lines.append("福利：" + str(row["welfare"]).strip()[:120])
    return "\n".join(lines)


def _markdown_title(text: str) -> str:
    for line in text.splitlines():
        matched = re.match(r"^#\s+(.+?)\s*$", line)
        if matched:
            return matched.group(1).strip()
    return ""


def _upload_meta(path: Path) -> dict:
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    if not meta_path.is_file():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("无法读取上传元数据 %s", meta_path.name)
        return {}


def _prune_missing(existing: list[str], live: set[str]) -> int:
    stale = [key for key in existing if key not in live]
    return prune_doc_keys(stale)


def ingest_source(source: str, rebuild: bool = False) -> dict[str, int]:
    source = source.strip().lower()
    if source == "knowledge":
        if rebuild:
            delete_by_source(4)
        docs = load_knowledge()
        result = _sync_batched(docs)
        result["pruned"] = _prune_missing(list_doc_keys(prefix="kb:"), {doc.doc_key for doc in docs})
        return result
    if source == "uploads":
        if rebuild:
            delete_by_source(6)
        docs = load_uploads()
        result = _sync_batched(docs)
        result["pruned"] = _prune_missing(list_doc_keys(prefix="upload:"), {doc.doc_key for doc in docs})
        return result
    if source == "cms":
        if rebuild:
            delete_by_source(2)
            delete_by_source(3)
        docs = load_cms()
        result = _sync_batched(docs)
        result["pruned"] = _prune_missing(list_doc_keys(prefix="cms:"), {doc.doc_key for doc in docs})
        return result
    if source == "jobs":
        if rebuild:
            delete_by_source(5)
        docs = load_jobs()
        result = _sync_batched(docs)
        result["pruned"] = _prune_missing(list_doc_keys(source_type=5), {doc.doc_key for doc in docs})
        return result
    raise ValueError("source 只能是 knowledge、cms、jobs、uploads")


def ingest_all(rebuild: bool = True) -> dict:
    if rebuild:
        logger.info("清空向量库与 rag_document 后全量重建")
        reset_collection()
        delete_all_rows()
    report = {}
    for name in ("knowledge", "cms", "uploads", "jobs"):
        logger.info("开始索引来源 %s", name)
        report[name] = ingest_source(name, rebuild=False)
    report["stats"] = stats()
    return report


def remove_upload_files(doc_key: str) -> None:
    """删除管理员上传留下的正文和旁路 meta，避免按 uploads 重建时又入库。"""
    prefix = "upload:"
    if not doc_key.startswith(prefix):
        return
    name = Path(doc_key[len(prefix) :]).name
    if not name or name in {".", ".."}:
        return
    root = UPLOAD_DIR.resolve()
    path = (UPLOAD_DIR / name).resolve()
    if path.parent != root:
        return
    if path.is_file():
        path.unlink()
    meta = path.with_suffix(path.suffix + ".meta.json")
    if meta.is_file() and meta.resolve().parent == root:
        meta.unlink()


def save_upload(filename: str, raw: bytes, title: str, doc_type: int) -> LogicalDoc:
    """保存管理员上传的 md/txt 并返回待索引文档。文件名只保留安全字符。"""
    if doc_type not in range(1, 8):
        raise ValueError("doc_type 取值应为 1 到 7")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".md", ".txt"}:
        raise ValueError("仅支持 .md 或 .txt")
    stem = Path(filename).stem
    safe_stem = re.sub(r"[^\w\-\u4e00-\u9fff]+", "_", stem).strip("._") or "upload"
    safe_name = f"{safe_stem}{suffix}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / safe_name
    path.write_bytes(raw)
    meta = {"title": title[:128], "doc_type": int(doc_type)}
    path.with_suffix(path.suffix + ".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False),
        encoding="utf-8",
    )
    text = raw.decode("utf-8", errors="replace")
    chunks = _chunks_of(text if text.lstrip().startswith("#") else f"# {title}\n\n{text}")
    if not chunks:
        raise ValueError("文档内容过短，无法切片")
    return LogicalDoc(
        doc_key=f"upload:{safe_name}"[:128],
        doc_type=int(doc_type),
        source_type=6,
        source_id=None,
        title=title[:128],
        ref=f"uploads/{safe_name}",
        chunks=chunks,
    )


def reindex_doc_key(doc_key: str) -> dict[str, int]:
    """按 doc_key 重新读取来源并覆盖该文档的切片。"""
    doc_key = (doc_key or "").strip()
    doc: LogicalDoc | None = None
    if doc_key.startswith("kb:"):
        name = doc_key[3:]
        path = KNOWLEDGE_DIR / name
        if not path.is_file():
            raise ValueError("知识库文件不存在")
        text = path.read_text(encoding="utf-8")
        chunks = _chunks_of(text)
        if not chunks:
            raise ValueError("文档内容过短")
        doc = LogicalDoc(
            doc_key=doc_key,
            doc_type=doc_type_for_filename(name),
            source_type=4,
            source_id=None,
            title=(_markdown_title(text) or path.stem)[:128],
            ref=f"data/knowledge/{name}",
            chunks=chunks,
        )
    elif doc_key.startswith("upload:"):
        name = doc_key[7:]
        path = UPLOAD_DIR / name
        if not path.is_file():
            raise ValueError("上传文件不存在")
        meta = _upload_meta(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        chunks = _chunks_of(text)
        if not chunks:
            raise ValueError("文档内容过短")
        doc = LogicalDoc(
            doc_key=doc_key[:128],
            doc_type=int(meta.get("doc_type") or 5),
            source_type=6,
            source_id=None,
            title=str(meta.get("title") or path.stem)[:128],
            ref=f"uploads/{name}",
            chunks=chunks,
        )
    elif doc_key.startswith("cms:"):
        docs = [item for item in load_cms() if item.doc_key == doc_key]
        if not docs:
            raise ValueError("公告不存在或未发布")
        doc = docs[0]
    elif doc_key.startswith("job:"):
        docs = [item for item in load_jobs() if item.doc_key == doc_key]
        if not docs:
            prune_doc_keys([doc_key])
            raise ValueError("职位不在架或未通过审核，已从知识库移除")
        doc = docs[0]
    else:
        raise ValueError("无法识别的 doc_key")
    return sync_documents([doc])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="构建或更新 RAG 知识库")
    parser.add_argument("--all", action="store_true", help="清空后重建全部来源")
    parser.add_argument(
        "--source",
        choices=["knowledge", "cms", "jobs", "uploads", "all"],
        help="只处理一个来源；all 与 --all 相同",
    )
    parser.add_argument("--rebuild", action="store_true", help="先删除该来源的旧切片再写入")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.all or args.source == "all":
        report = ingest_all(rebuild=True)
    elif args.source:
        report = ingest_source(args.source, rebuild=args.rebuild)
    else:
        parser.print_help()
        return
    print(json.dumps(report, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
