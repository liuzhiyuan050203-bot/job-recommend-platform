#!/usr/bin/env python3
"""校验 RAG 评测题：gold 章节必须是知识库文件里真实的 ## / ### 标题。

用法：.venv/bin/python experiments/rag_eval/validate_questions.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "data" / "knowledge"
QUESTIONS = Path(__file__).resolve().parent / "questions.jsonl"
HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*$", re.M)
ANSWER_TYPES = {"direct", "paraphrase", "keyword", "synonym"}


def headings_of(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {match.group(2).strip() for match in HEADING.finditer(text)}


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path.name}:{line_no} 不是合法 JSON：{exc}") from exc
    return rows


def check(path: Path = QUESTIONS) -> list[dict]:
    files = {item.name: headings_of(item) for item in sorted(KNOWLEDGE.glob("*.md"))}
    if len(files) != 11:
        raise SystemExit(f"知识库 md 应为 11 个，实际 {len(files)}：{sorted(files)}")
    rows = load_questions(path)
    errors: list[str] = []
    ids: set[str] = set()
    per_file: Counter[str] = Counter()
    answered = [row for row in rows if row.get("gold")]
    irrelevant = [row for row in rows if not row.get("gold")]
    if len(answered) != 50:
        errors.append(f"有 gold 的题目应为 50，实际 {len(answered)}")
    if len(irrelevant) != 5:
        errors.append(f"gold 为空的无关题应为 5，实际 {len(irrelevant)}")
    for row in rows:
        qid = str(row.get("id") or "")
        if not qid:
            errors.append("存在空 id")
            continue
        if qid in ids:
            errors.append(f"重复 id {qid}")
        ids.add(qid)
        if not str(row.get("question") or "").strip():
            errors.append(f"{qid} 问题为空")
        gold = row.get("gold")
        if gold is None or not isinstance(gold, list):
            errors.append(f"{qid} gold 必须是数组")
            continue
        qtype = row.get("type")
        if gold:
            if qtype not in ANSWER_TYPES:
                errors.append(f"{qid} type 应为 {sorted(ANSWER_TYPES)}，实际 {qtype}")
            for item in gold:
                name = str((item or {}).get("file") or "")
                section = str((item or {}).get("section") or "")
                if name not in files:
                    errors.append(f"{qid} 文件不存在：{name}")
                    continue
                if section not in files[name]:
                    errors.append(f"{qid} 章节不在 {name} 中：{section}")
                else:
                    per_file[name] += 1
        else:
            if qtype != "irrelevant":
                errors.append(f"{qid} 无关题 type 应为 irrelevant，实际 {qtype}")
    for name in files:
        if per_file[name] < 3:
            errors.append(f"{name} 只有 {per_file[name]} 道题，至少需要 3 道")
    if errors:
        raise SystemExit("评测题校验失败：\n- " + "\n- ".join(errors))
    type_count = Counter(row["type"] for row in answered)
    print(f"校验通过：{len(answered)} 道有答案，{len(irrelevant)} 道无关题，11 个文件均至少 3 题")
    print("题型：" + "，".join(f"{key} {type_count[key]}" for key in ("direct", "paraphrase", "keyword", "synonym")))
    return rows


def main() -> None:
    check()


if __name__ == "__main__":
    main()
