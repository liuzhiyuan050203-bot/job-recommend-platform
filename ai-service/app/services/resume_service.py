"""从 PDF / DOCX 抽取正文，并按技能标签做边界匹配.

拉丁短名（Go、C、R、JS 等）必须按词边界匹配，避免命中 MongoDB、JavaScript、C++ 里的片段。
别名只挂在 skill_tag 已有的标准名上，不凭空造标签。
"""

from __future__ import annotations

import io
import logging
import re
from typing import Any

import pdfplumber
from docx import Document

from app.spark.db import connect

logger = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024
MAX_CHARS = 200_000
PREVIEW_CHARS = 400
MAX_PAGES = 30

# 标准名 -> 简历里常见写法。名字本身还会再匹配一次。
COMMON_ALIASES: dict[str, list[str]] = {
    "Spring Boot": ["SpringBoot", "spring-boot"],
    "Spring Cloud": ["SpringCloud"],
    "Vue": ["Vue.js", "VueJS", "Vue3"],
    "JavaScript": ["JS"],
    "TypeScript": ["TS"],
    "Kubernetes": ["K8s"],
    "Go": ["Golang"],
    "Node.js": ["NodeJS", "nodejs"],
    "C++": ["cpp"],
    "PyTorch": ["Pytorch"],
    "TensorFlow": ["Tensorflow"],
}

_CJK = re.compile(r"[\u4e00-\u9fff]")


def parse_resume_bytes(filename: str, raw: bytes) -> dict[str, Any]:
    """抽出正文并返回预览与命中的技能."""
    if raw is None or len(raw) == 0:
        raise ValueError("文件为空")
    if len(raw) > MAX_BYTES:
        raise ValueError("文件不能超过 5MB")
    ext = _ext(filename)
    if ext == "pdf":
        text = _pdf_text(raw)
    elif ext == "docx":
        text = _docx_text(raw)
    else:
        raise ValueError("只支持 PDF 或 DOCX")
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
    tags = _load_tags()
    skills = match_skills(text, tags)
    return {"textPreview": _preview(text), "skills": skills}


def match_skills(text: str, tags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """对一份正文做标签匹配。tags 元素含 id、name、direction."""
    if not text or not tags:
        return []
    ordered = sorted(tags, key=lambda row: len(str(row.get("name") or "")), reverse=True)
    found: list[dict[str, Any]] = []
    seen: set[int] = set()
    for tag in ordered:
        name = str(tag.get("name") or "").strip()
        tag_id = tag.get("id")
        if not name or tag_id is None or int(tag_id) in seen:
            continue
        tokens = [name, *COMMON_ALIASES.get(name, [])]
        span = None
        for token in tokens:
            span = _find_span(text, token)
            if span is not None:
                break
        if span is None:
            continue
        seen.add(int(tag_id))
        found.append(
            {
                "tagId": int(tag_id),
                "name": name,
                "direction": str(tag.get("direction") or ""),
                "evidence": _snippet(text, span[0], span[1]),
            }
        )
    found.sort(key=lambda item: item["tagId"])
    return found


def _find_span(text: str, token: str) -> tuple[int, int] | None:
    token = (token or "").strip()
    if not token:
        return None
    if _CJK.search(token):
        matched = re.search(re.escape(token), text, flags=re.IGNORECASE)
        if not matched:
            return None
        return matched.start(), matched.end()
    parts = [part for part in re.split(r"[\s_\-]+", token) if part]
    if not parts:
        return None
    body = r"[\s_\-]*".join(re.escape(part) for part in parts)
    alnum_len = len(re.sub(r"[^A-Za-z0-9]", "", token))
    # 两字符及以内的纯拉丁名（Go、C、R、JS）不能贴着字母、数字、+、#、点
    if alnum_len <= 2:
        pattern = re.compile(
            rf"(?<![A-Za-z0-9.]){body}(?![A-Za-z0-9+#\.])",
            flags=re.IGNORECASE,
        )
    else:
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])",
            flags=re.IGNORECASE,
        )
    matched = pattern.search(text)
    if not matched:
        return None
    return matched.start(), matched.end()


def _snippet(text: str, start: int, end: int, radius: int = 24) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    frag = re.sub(r"\s+", " ", text[left:right]).strip()
    if left > 0:
        frag = "…" + frag
    if right < len(text):
        frag = frag + "…"
    return frag[:160]


def _preview(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= PREVIEW_CHARS:
        return compact
    return compact[:PREVIEW_CHARS] + "…"


def _ext(filename: str) -> str:
    name = (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith(".docx"):
        return "docx"
    return ""


def _pdf_text(raw: bytes) -> str:
    parts: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for index, page in enumerate(pdf.pages):
                if index >= MAX_PAGES:
                    break
                parts.append(page.extract_text() or "")
    except Exception as exc:
        logger.info("PDF 解析失败: %s", exc)
        raise ValueError("无法解析 PDF") from exc
    return "\n".join(parts)


def _docx_text(raw: bytes) -> str:
    try:
        document = Document(io.BytesIO(raw))
    except Exception as exc:
        logger.info("DOCX 解析失败: %s", exc)
        raise ValueError("无法解析 DOCX") from exc
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def _load_tags() -> list[dict[str, Any]]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, direction FROM skill_tag "
                "WHERE deleted = 0 AND status = 1"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return list(rows or [])
