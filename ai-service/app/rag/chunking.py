"""按标题切分 Markdown，再用中文分隔符做定长切片。

切片长度约 400 字、重叠 60 字，分隔符顺序接近 RecursiveCharacterTextSplitter：
空行、换行、句号、叹号、问号、分号、逗号、顿号、空格，最后才按字硬切。
"""

from __future__ import annotations

import hashlib
import re

from app.core.config import settings

_HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", "、", " "]


def content_hash(title: str, section: str, content: str) -> str:
    """标题、章节和正文一起哈希，标题变化也会触发重新向量化。"""
    raw = f"{title}\n{section}\n{content}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def embed_input(title: str, section: str, content: str) -> str:
    """向量化文本带上标题和章节，避免切片脱离语境。"""
    head = title if not section else f"{title} / {section}"
    return f"{head}\n{content}"


def split_markdown(text: str, size: int | None = None, overlap: int | None = None) -> list[tuple[str, str]]:
    """按 # / ## / ### 分节，再对每节正文做定长切片。返回 (章节名, 正文)。"""
    size = size or settings.RAG_CHUNK_SIZE
    overlap = overlap or settings.RAG_CHUNK_OVERLAP
    sections = _split_sections(text)
    chunks: list[tuple[str, str]] = []
    for section, body in sections:
        for piece in split_text(body, size, overlap):
            chunks.append((section[:128], piece))
    return chunks


def split_text(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    """把纯文本切成不超过 size 的片段，相邻片段共享 overlap 个字符。"""
    size = size or settings.RAG_CHUNK_SIZE
    overlap = overlap if overlap is not None else settings.RAG_CHUNK_OVERLAP
    overlap = max(0, min(overlap, size // 2))
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    parts = _split_recursive(text, size, overlap, _SEPARATORS)
    return [part.strip() for part in parts if part and part.strip()]


def _split_sections(text: str) -> list[tuple[str, str]]:
    current = ""
    buf: list[str] = []
    sections: list[tuple[str, str]] = []
    seen_h1 = False

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            sections.append((current, body))

    for line in text.splitlines():
        matched = _HEADING.match(line)
        if not matched:
            buf.append(line)
            continue
        level = len(matched.group(1))
        name = matched.group(2).strip()
        flush()
        buf = []
        if level == 1 and not seen_h1:
            seen_h1 = True
            current = ""
            continue
        current = name
    flush()
    return sections


def _split_recursive(text: str, size: int, overlap: int, separators: list[str]) -> list[str]:
    if len(text) <= size:
        return [text]
    separator = ""
    rest: list[str] = []
    for index, sep in enumerate(separators):
        if sep and sep in text:
            separator = sep
            rest = separators[index + 1 :]
            break
    if not separator:
        return _hard_cut(text, size, overlap)

    raw_parts = text.split(separator)
    pieces: list[str] = []
    for index, part in enumerate(raw_parts):
        piece = part.strip()
        if not piece:
            continue
        if separator.strip():
            piece = piece + separator if index < len(raw_parts) - 1 else piece
        elif separator == "\n":
            piece = piece + "\n"
        else:
            piece = piece + "\n\n"
        pieces.append(piece)

    if len(pieces) <= 1:
        return _hard_cut(text, size, overlap)

    chunks: list[str] = []
    buf = ""
    for piece in pieces:
        if len(piece) > size:
            if buf.strip():
                chunks.append(buf.strip())
                buf = ""
            inner = piece.rstrip(separator).strip() or piece
            # 子串没有变短时直接硬切，避免分隔符回绕导致无限递归
            if len(inner) >= len(text):
                chunks.extend(_hard_cut(inner, size, overlap))
            else:
                chunks.extend(_split_recursive(inner, size, overlap, rest or separators))
            continue
        if not buf:
            buf = piece
            continue
        if len(buf) + len(piece) <= size:
            buf += piece
            continue
        chunks.append(buf.strip())
        tail = buf.strip()[-overlap:] if overlap else ""
        buf = f"{tail}{piece}" if tail else piece
        if len(buf) > size:
            buf = piece
    if buf.strip():
        chunks.append(buf.strip())
    cleaned = [item for item in chunks if item]
    if len(cleaned) == 1 and len(cleaned[0]) > size:
        return _hard_cut(text, size, overlap)
    return cleaned


def _hard_cut(text: str, size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + size, length)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks
