#!/usr/bin/env python3
"""RAG 评测 v2：难例、岗位检索、路由准确率，以及改善前/后消融。

    .venv/bin/python experiments/rag_eval/run_rag_eval_v2.py
    .venv/bin/python experiments/rag_eval/run_rag_eval_v2.py --faithfulness --faithfulness-limit 8

默认只用生产配置（标题切分 + hybrid）。--faithfulness 时用当前 LLM_PROVIDER
（默认本地 qwen2.5:3b）在子集上测回答是否忠于资料；换成云端后同一命令可重跑。
不写入生产 Chroma。
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "experiments" / "rag_eval"))
sys.path.insert(0, str(ROOT / "ai-service"))

from common import FIGURES, RESULTS, env_info, save_json, setup_matplotlib  # noqa: E402
from validate_questions import QUESTIONS, check  # noqa: E402

from app.agent.router import route  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.embedding import embed_documents, embed_query, get_embedding_model  # noqa: E402
from app.rag.bm25 import bm25_document_text, candidate_pool_size  # noqa: E402
from app.rag.chunking import embed_input, split_markdown  # noqa: E402
from app.rag.diversity import diversify_hits  # noqa: E402
from app.rag.ingest import EDU_LABEL, EXP_LABEL, _chunks_of, doc_type_for_filename  # noqa: E402
from app.rag.job_text import build_job_text  # noqa: E402
from app.rag.lc_retrievers import ChromaDenseRetriever, JiebaBM25Retriever, build_retriever  # noqa: E402
from app.rag.store import COLLECTION_METADATA  # noqa: E402
from app.spark.db import connect  # noqa: E402

KNOWLEDGE = ROOT / "data" / "knowledge"
QUESTIONS_V2 = Path(__file__).resolve().parent / "questions_v2.jsonl"
METRIC_TOP_K = 10
OVERLAP_MIN = 50
HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*$", re.M)


def load_v2_questions() -> list[dict]:
    rows = []
    for line in QUESTIONS_V2.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def markdown_title(text: str) -> str:
    for line in text.splitlines():
        matched = re.match(r"^#\s+(.+?)\s*$", line)
        if matched:
            return matched.group(1).strip()
    return ""


def section_spans(text: str) -> dict[str, list[tuple[int, int]]]:
    matches = list(HEADING.finditer(text))
    found: dict[str, list[tuple[int, int]]] = {}
    for index, matched in enumerate(matches):
        start = matched.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        found.setdefault(matched.group(2).strip(), []).append((start, end))
    return found


def locate_span(source: str, chunk: str, search_from: int) -> tuple[int, int] | None:
    if not chunk:
        return None
    window = max(0, search_from - 500)
    exact = source.find(chunk, window)
    if exact >= 0:
        return exact, exact + len(chunk)
    max_cut = min(len(chunk) - 8, 180)
    suffix_pos = -1
    cut = 0
    for size in range(1, max_cut + 1):
        pos = source.find(chunk[size:], window)
        if pos >= 0:
            cut = size
            suffix_pos = pos
            break
    if suffix_pos < 0:
        return None
    prefix = chunk[:cut]
    prefix_pos = source.rfind(prefix, window, suffix_pos + 1)
    if prefix_pos < 0:
        prefix_pos = source.rfind(prefix, 0, suffix_pos + 1)
    end = suffix_pos + len(chunk) - cut
    if prefix_pos < 0 or prefix_pos > suffix_pos:
        return suffix_pos, end
    return prefix_pos, end


def spans_hit(c0: int, c1: int, s0: int, s1: int) -> bool:
    if c1 <= c0 or s1 <= s0:
        return False
    if c0 >= s0 and c1 <= s1:
        return True
    return min(c1, s1) - max(c0, s0) >= OVERLAP_MIN


def policy_hit(chunk: dict, gold: list[dict], gold_spans: dict) -> bool:
    if chunk.get("source") != "knowledge" or not gold:
        return False
    for item in gold:
        if item.get("file") != chunk.get("file"):
            continue
        for start, end in gold_spans.get(item["file"], {}).get(item["section"], []):
            if spans_hit(chunk.get("start") or 0, chunk.get("end") or 0, start, end):
                return True
        if chunk.get("section") == item.get("section"):
            return True
    return False


def job_relevant(chunk: dict, gold: dict) -> bool:
    if not gold or (chunk.get("source") != "job" and int(chunk.get("doc_type") or 0) != 7):
        return False
    blob = " ".join(
        str(chunk.get(key) or "")
        for key in ("title", "content", "company", "city", "data_source")
    )
    company = gold.get("company")
    if company and company not in blob:
        return False
    city = gold.get("city")
    if city and city not in blob:
        return False
    data_source = gold.get("data_source")
    if data_source and (chunk.get("data_source") or "") != data_source and data_source not in blob:
        return False
    title_has = gold.get("title_has") or []
    if title_has and not any(token in blob for token in title_has):
        return False
    either = gold.get("title_or_direction") or []
    if either and not any(token in blob for token in either):
        return False
    return True


def legacy_job_text(row: dict) -> str:
    salary = f"{int(row['salary_min'] or 0)}-{int(row['salary_max'] or 0)}元/月"
    months = int(row.get("salary_months") or 12)
    if months != 12:
        salary += f"，{months}薪"
    lines = [
        f"# {row['title']}",
        f"公司：{row['company_name']}",
        f"城市：{row['city']}",
        f"方向：{row['tech_direction']}",
        f"薪资：{salary}",
        f"学历：{EDU_LABEL.get(int(row.get('education') or 0), '不限')}",
        f"经验：{EXP_LABEL.get(int(row.get('experience_req') or 0), '不限')}",
        f"技能：{row.get('skills') or '未标注'}",
    ]
    if row.get("description"):
        lines.append("职责：" + str(row["description"]).strip()[:500])
    if row.get("requirement"):
        lines.append("要求：" + str(row["requirement"]).strip()[:300])
    if row.get("welfare"):
        lines.append("福利：" + str(row["welfare"]).strip()[:120])
    return "\n".join(lines)


def fetch_job_rows(limit: int | None = None) -> list[dict]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SET SESSION group_concat_max_len = 2048")
            sql = """
                SELECT p.id, p.title, p.city, p.tech_direction, p.salary_min, p.salary_max,
                       p.salary_months, p.education, p.experience_req, p.description,
                       p.requirement, p.welfare, p.data_source, c.company_name,
                       (
                         SELECT GROUP_CONCAT(t.name ORDER BY t.name SEPARATOR '、')
                         FROM job_position_tag pt
                         INNER JOIN skill_tag t ON t.id = pt.tag_id AND t.deleted = 0
                         WHERE pt.position_id = p.id AND pt.deleted = 0
                       ) AS skills
                FROM job_position p
                INNER JOIN ent_company c ON c.id = p.company_id AND c.deleted = 0 AND c.audit_status = 1
                WHERE p.deleted = 0 AND p.shelf_status = 1 AND p.audit_status = 1
                ORDER BY p.id
            """
            params: list = []
            if limit is not None:
                sql += " LIMIT %s"
                params.append(max(0, int(limit)))
            cur.execute(sql, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def knowledge_chunks(hygiene: bool) -> tuple[list[dict], dict]:
    chunks: list[dict] = []
    gold_spans: dict = {}
    for path in sorted(KNOWLEDGE.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        title = markdown_title(raw) or path.stem
        gold_spans[path.name] = section_spans(raw)
        if hygiene:
            records = _chunks_of(raw)
            parts = [(item.section, item.content) for item in records]
        else:
            parts = split_markdown(raw)
        cursor = 0
        for index, (section, piece) in enumerate(parts):
            if len((piece or "").strip()) < 8:
                continue
            found = locate_span(raw, piece, cursor)
            start, end = found if found else (0, 0)
            if found:
                cursor = found[0] + 1
            chunks.append(
                {
                    "id": f"kb:{path.name}:{index}",
                    "file": path.name,
                    "source": "knowledge",
                    "title": title,
                    "section": section,
                    "index_section": section,
                    "content": piece,
                    "start": start,
                    "end": end,
                    "doc_type": doc_type_for_filename(path.name),
                    "doc_key": f"kb:{path.name}",
                    "company": "",
                    "city": "",
                    "data_source": "",
                }
            )
    return chunks, gold_spans


def job_chunks(rows: list[dict], cleaned: bool) -> list[dict]:
    chunks: list[dict] = []
    for row in rows:
        text = build_job_text(row) if cleaned else legacy_job_text(row)
        data_source = (row.get("data_source") or "platform").strip() or "platform"
        estimated = data_source in {"self_crawl", "ext_ats"}
        if cleaned:
            parts = [(item.section, item.content) for item in _chunks_of(text)]
        else:
            parts = split_markdown(text) or [("", text)]
        for index, (section, piece) in enumerate(parts):
            if len((piece or "").strip()) < 8:
                continue
            chunks.append(
                {
                    "id": f"job:{row['id']}:{index}",
                    "file": "",
                    "source": "job",
                    "title": str(row["title"])[:128],
                    "section": section,
                    "index_section": section,
                    "content": piece,
                    "start": 0,
                    "end": 0,
                    "doc_type": 7,
                    "doc_key": f"job:{row['id']}",
                    "company": str(row.get("company_name") or ""),
                    "city": str(row.get("city") or ""),
                    "data_source": data_source,
                    "salary_estimated": estimated,
                }
            )
    return chunks


def embed_vectors(chunks: list[dict]) -> list[list[float]]:
    texts = [embed_input(chunk["title"], chunk["index_section"], chunk["content"]) for chunk in chunks]
    vectors: list[list[float]] = []
    batch = 64
    for offset in range(0, len(texts), batch):
        vectors.extend(embed_documents(texts[offset : offset + batch]))
        done = min(offset + batch, len(texts))
        if done == len(texts) or done % 512 == 0:
            print(f"  嵌入进度 {done}/{len(texts)}", flush=True)
    return [[float(v) for v in vector] for vector in vectors]


class MemoryIndex:
    def __init__(self, name: str, chunks: list[dict], vectors: list[list[float]]):
        import chromadb
        from langchain_chroma import Chroma

        self.client = chromadb.EphemeralClient()
        self.name = f"rag_v2_{name}_{int(time.time())}"
        self.chunks = chunks
        self.by_id = {chunk["id"]: chunk for chunk in chunks}
        try:
            self.client.delete_collection(self.name)
        except Exception:
            pass
        self.store = Chroma(
            client=self.client,
            collection_name=self.name,
            embedding_function=get_embedding_model(),
            collection_metadata=dict(COLLECTION_METADATA),
        )
        collection = self.store._collection
        for offset in range(0, len(chunks), 500):
            part = chunks[offset : offset + 500]
            collection.add(
                ids=[chunk["id"] for chunk in part],
                embeddings=vectors[offset : offset + 500],
                documents=[chunk["content"] for chunk in part],
                metadatas=[
                    {
                        "doc_type": int(chunk["doc_type"]),
                        "title": (chunk["title"] or "")[:120],
                        "section": (chunk["index_section"] or "")[:120],
                        "doc_key": (chunk["doc_key"] or "")[:120],
                        "company": (chunk.get("company") or "")[:120],
                        "city": (chunk.get("city") or "")[:64],
                        "data_source": (chunk.get("data_source") or "")[:32],
                        "source": chunk["source"],
                    }
                    for chunk in part
                ],
            )
        records = [
            {
                "id": chunk["id"],
                "document": chunk["content"],
                "metadata": {"doc_type": chunk["doc_type"], "title": chunk["title"], "section": chunk["index_section"]},
                "text": bm25_document_text(chunk["title"], chunk["index_section"], chunk["content"]),
            }
            for chunk in chunks
        ]
        self.bm25 = JiebaBM25Retriever.from_records(records)
        self.dense = ChromaDenseRetriever(vectorstore=self.store)

    def search(self, query: str, top_k: int, apply_threshold: bool, diversify: bool) -> list[dict]:
        fetch_k = max(top_k * 4, top_k) if diversify else top_k
        retriever = build_retriever(
            dense=self.dense,
            bm25=self.bm25,
            mode="hybrid",
            top_k=fetch_k,
            threshold=float(settings.RAG_SCORE_THRESHOLD),
            pool=candidate_pool_size(fetch_k),
            apply_threshold=apply_threshold,
            rerank_scorer=None,
        )
        docs = retriever.invoke(query)
        hits = []
        for doc in docs:
            chunk = dict(self.by_id.get(doc.id) or {})
            if not chunk:
                continue
            chunk["score"] = float((doc.metadata or {}).get("cosine") or 0.0)
            chunk["rrf"] = float((doc.metadata or {}).get("rrf") or 0.0)
            hits.append(chunk)
        if diversify:
            hits = diversify_hits(
                hits,
                top_k,
                per_job=settings.RAG_DIVERSITY_PER_JOB,
                per_company=settings.RAG_DIVERSITY_PER_COMPANY,
            )
        return hits[:top_k]

    def close(self) -> None:
        try:
            self.client.delete_collection(self.name)
        except Exception:
            pass


def evaluate_policy(index: MemoryIndex, questions: list[dict], gold_spans: dict, diversify: bool) -> dict:
    details = []
    for row in questions:
        gold = row.get("gold") or []
        if not gold:
            hits = index.search(row["question"], int(settings.RAG_TOP_K), True, diversify)
            details.append(
                {
                    "id": row["id"],
                    "question": row["question"],
                    "type": row.get("type"),
                    "rejected": len(hits) == 0,
                    "kept": len(hits),
                    "top_title": hits[0]["title"] if hits else "",
                    "has_disclaimer": any("演示用示例" in (h.get("content") or "") or "毕业设计演示" in (h.get("content") or "") for h in hits),
                }
            )
            continue
        hits = index.search(row["question"], METRIC_TOP_K, False, diversify)
        hit_rank = None
        found_sections: set[str] = set()
        gold_keys = {(item["file"], item["section"]) for item in gold}
        ranked = []
        for rank, chunk in enumerate(hits, start=1):
            hit = policy_hit(chunk, gold, gold_spans)
            if hit and hit_rank is None:
                hit_rank = rank
            if hit:
                found_sections.add((chunk.get("file"), chunk.get("section")))
            # also count by gold section name even if span missed
            for item in gold:
                if chunk.get("file") == item["file"] and chunk.get("section") == item["section"]:
                    found_sections.add((item["file"], item["section"]))
            ranked.append(
                {
                    "rank": rank,
                    "file": chunk.get("file"),
                    "section": chunk.get("section"),
                    "title": chunk.get("title"),
                    "hit": hit,
                    "score": round(float(chunk.get("score") or 0), 4),
                }
            )
        details.append(
            {
                "id": row["id"],
                "question": row["question"],
                "type": row.get("type"),
                "gold": gold,
                "hit_rank": hit_rank,
                "reciprocal_rank": 0.0 if not hit_rank or hit_rank > 10 else 1.0 / hit_rank,
                "sections_found": len(found_sections),
                "sections_total": len(gold_keys),
                "section_recall": (len(found_sections) / len(gold_keys)) if gold_keys else 0.0,
                "topk": ranked[:5],
            }
        )
    answered = [item for item in details if item.get("gold")]
    refused = [item for item in details if "rejected" in item]

    def rate(k: int) -> float:
        if not answered:
            return 0.0
        return sum(1 for item in answered if item["hit_rank"] and item["hit_rank"] <= k) / len(answered)

    mrr = sum(item["reciprocal_rank"] for item in answered) / len(answered) if answered else 0.0
    recall5 = sum(item.get("section_recall") or 0 for item in answered) / len(answered) if answered else 0.0
    # Recall@5 as fraction of questions whose first gold is in top 5 already in hit_at_5;
    # also mean section recall
    reject = sum(1 for item in refused if item["rejected"]) / len(refused) if refused else None
    disclaimer = sum(1 for item in refused if item.get("has_disclaimer")) + sum(
        1 for item in answered if any("演示" in json.dumps(item.get("topk") or [], ensure_ascii=False) for _ in [0])
    )
    return {
        "n": len(answered),
        "hit_at_1": rate(1),
        "hit_at_5": rate(5),
        "mrr_at_10": mrr,
        "recall_at_5": recall5,
        "reject_rate": reject,
        "disclaimer_hits": disclaimer,
        "details": details,
    }


def evaluate_jobs(index: MemoryIndex, questions: list[dict], diversify: bool) -> dict:
    details = []
    for row in questions:
        gold = row.get("gold") or {}
        relevant_ids = {
            chunk["doc_key"]
            for chunk in index.chunks
            if job_relevant(chunk, gold)
        }
        hits = index.search(row["question"], METRIC_TOP_K, False, diversify)
        hit_rank = None
        found: set[str] = set()
        companies = []
        for rank, chunk in enumerate(hits, start=1):
            ok = job_relevant(chunk, gold)
            if ok and hit_rank is None:
                hit_rank = rank
            if ok:
                found.add(chunk["doc_key"])
            if chunk.get("company"):
                companies.append(chunk["company"])
        top5 = hits[:5]
        companies5 = [c.get("company") for c in top5 if c.get("company")]
        details.append(
            {
                "id": row["id"],
                "question": row["question"],
                "hit_rank": hit_rank,
                "reciprocal_rank": 0.0 if not hit_rank or hit_rank > 10 else 1.0 / hit_rank,
                "relevant_in_corpus": len(relevant_ids),
                "relevant_in_top5": len({c["doc_key"] for c in top5 if job_relevant(c, gold)}),
                "recall_at_5": (
                    len({c["doc_key"] for c in top5 if job_relevant(c, gold)}) / len(relevant_ids)
                    if relevant_ids
                    else 0.0
                ),
                "unique_companies_top5": len(set(companies5)),
                "top5_companies": companies5,
                "top1": {
                    "title": hits[0]["title"] if hits else "",
                    "company": hits[0].get("company") if hits else "",
                    "city": hits[0].get("city") if hits else "",
                    "data_source": hits[0].get("data_source") if hits else "",
                },
                "diversity": bool(row.get("diversity")),
            }
        )
    n = len(details) or 1

    def mean(key: str) -> float:
        return sum(item[key] for item in details) / n

    diversity_rows = [item for item in details if item["diversity"]]
    return {
        "n": len(details),
        "hit_at_1": sum(1 for item in details if item["hit_rank"] == 1) / n,
        "hit_at_5": sum(1 for item in details if item["hit_rank"] and item["hit_rank"] <= 5) / n,
        "mrr_at_10": mean("reciprocal_rank"),
        "recall_at_5": mean("recall_at_5"),
        "avg_unique_companies_top5": (
            sum(item["unique_companies_top5"] for item in diversity_rows) / len(diversity_rows)
            if diversity_rows
            else mean("unique_companies_top5")
        ),
        "details": details,
    }


def evaluate_routing(questions: list[dict]) -> dict:
    details = []
    correct = 0
    for row in questions:
        decided = route(row["question"], row.get("role") or "student")
        tools = [item.name for item in decided.tools]
        doc_types = list(decided.doc_types or [])
        expect = list(row.get("expect_tools") or [])
        forbid = list(row.get("forbid_tools") or [])
        expect_docs = list(row.get("expect_doc_types") or [])
        ok_tools = all(name in tools for name in expect)
        ok_forbid = all(name not in tools for name in forbid)
        if expect_docs:
            ok_docs = any(value in doc_types for value in expect_docs) if doc_types else False
            if expect_docs and not expect and not doc_types:
                ok_docs = False
        else:
            ok_docs = (not doc_types) if row.get("expect_doc_types") == [] else True
        slot_ok = True
        for key, value in (row.get("expect_slot") or {}).items():
            if (decided.slots or {}).get(key) != value:
                slot_ok = False
        ok = ok_tools and ok_forbid and ok_docs and slot_ok
        if ok:
            correct += 1
        details.append(
            {
                "id": row["id"],
                "question": row["question"],
                "ok": ok,
                "tools": tools,
                "doc_types": doc_types,
                "keyword": (decided.slots or {}).get("keyword"),
            }
        )
    return {"n": len(questions), "accuracy": correct / len(questions) if questions else 0.0, "details": details}


def run_faithfulness(index: MemoryIndex, questions: list[dict], gold_spans: dict, diversify: bool, limit: int) -> dict:
    from app.core.llm import get_llm, is_available, normalize_provider

    info = {"provider": None, "model": settings.LLM_MODEL, "available": False, "n": 0, "items": []}
    try:
        info["provider"] = normalize_provider()
    except Exception as exc:
        info["error"] = str(exc)
        return info
    if not is_available():
        info["error"] = "大模型不可用（可稍后将 LLM_PROVIDER 换成云端再跑同一命令）"
        return info
    llm = get_llm()
    if llm is None:
        info["error"] = "get_llm 返回空"
        return info
    info["available"] = True
    picked = [row for row in questions if row.get("gold") or row.get("set") == "refusal"][:limit]
    items = []
    for row in picked:
        hits = index.search(row["question"], int(settings.RAG_TOP_K), True, diversify)
        context = "\n".join(
            f"[{i}] {h.get('title') or ''} / {h.get('section') or ''}\n{(h.get('content') or '')[: settings.prompt_chunk_chars]}"
            for i, h in enumerate(hits, 1)
        ) or "无"
        prompt = (
            "只根据【资料】回答，禁止编造。资料不足时说明知识库没有相关信息。引用用[1]、[2]。\n"
            f"【资料】\n{context}\n【问题】\n{row['question']}"
        )
        try:
            message = llm.invoke(prompt)
            answer = message.content if hasattr(message, "content") else str(message)
        except Exception as exc:
            items.append({"id": row["id"], "error": str(exc)[:200]})
            continue
        answer = str(answer or "")
        ctx = context
        issues = []
        if re.search(r"毕业设计演示|演示用示例|示例资料", answer):
            issues.append("回答引用了免责声明")
        numbers = re.findall(r"\d{2,}", answer)
        unsupported = [num for num in numbers if num not in ctx and num not in row["question"]]
        if unsupported and hits:
            issues.append("数字未出现在资料中: " + ",".join(unsupported[:5]))
        if not hits and not re.search(r"没有|未找到|资料不足|不知道", answer):
            issues.append("无资料时未明确拒答")
        if hits and len(answer.strip()) < 8:
            issues.append("回答过短")
        items.append(
            {
                "id": row["id"],
                "question": row["question"],
                "answer": answer[:800],
                "n_hits": len(hits),
                "faithful": len(issues) == 0,
                "issues": issues,
            }
        )
    info["n"] = len(items)
    info["faithful_rate"] = (sum(1 for item in items if item.get("faithful")) / len(items)) if items else 0.0
    info["items"] = items
    return info


def write_chart(payload: dict) -> Path:
    plt = setup_matplotlib()
    hist = payload.get("historical_easy") or {}
    b = payload["pipelines"]["baseline"]
    s = payload["pipelines"].get("improved_same_scale") or {}
    a = payload["pipelines"]["improved"]

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.4))
    width = 0.36

    def annotate(ax, bars, fmt="{:.2f}", dy=0.025, fontsize=8):
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + dy,
                fmt.format(h),
                ha="center",
                va="bottom",
                fontsize=fontsize,
                clip_on=False,
            )

    ax = axes[0]
    labels_l = ["历史评测\n(1000)", "改善前\n(1000)", "改善后\n同等规模", "改善后全量\n(压力测试)"]
    same_easy = s.get("easy") or b["easy"]
    hit = [
        hist.get("hit_at_1", 0.92),
        b["easy"]["hit_at_1"],
        same_easy["hit_at_1"],
        a["easy"]["hit_at_1"],
    ]
    mrr = [
        hist.get("mrr_at_10", 0.947),
        b["easy"]["mrr_at_10"],
        same_easy["mrr_at_10"],
        a["easy"]["mrr_at_10"],
    ]
    x = np.arange(len(labels_l))
    bars1 = ax.bar(x - width / 2, hit, width, label="Hit@1", color="#4C78A8", zorder=3)
    bars2 = ax.bar(x + width / 2, mrr, width, label="MRR@10", color="#F58518", zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(labels_l)
    ax.set_ylim(0, 1.22)
    ax.set_ylabel("分数")
    ax.set_title("政策易例（11 篇，50 题）", pad=28)
    ax.axhline(0.92, color="#4C78A8", ls="--", lw=0.7, alpha=0.45, zorder=1)
    annotate(ax, list(bars1) + list(bars2))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper right", frameon=False, bbox_to_anchor=(1.0, 1.02), ncol=2, handlelength=1.2)

    ax = axes[1]
    n_jobs = payload.get("corpus", {}).get("improved", {}).get("jobs", 5431)
    labels_r = ["岗位 Hit@1", "岗位 MRR@10", "岗位 Recall@5", "多跳 Hit@1", "多跳 MRR@10"]
    before = [
        b["job"]["hit_at_1"],
        b["job"]["mrr_at_10"],
        b["job"]["recall_at_5"],
        b["multihop"]["hit_at_1"],
        b["multihop"]["mrr_at_10"],
    ]
    after = [
        a["job"]["hit_at_1"],
        a["job"]["mrr_at_10"],
        a["job"]["recall_at_5"],
        a["multihop"]["hit_at_1"],
        a["multihop"]["mrr_at_10"],
    ]
    x = np.arange(len(labels_r))
    bars1 = ax.bar(x - width / 2, before, width, label="改善前（1000 条，无外部库）", color="#B0B0B0", zorder=3)
    bars2 = ax.bar(
        x + width / 2,
        after,
        width,
        label=f"改善后（全量 {n_jobs}，含 ext_ats）",
        color="#54A24B",
        zorder=3,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels_r)
    ax.set_ylim(0, 1.22)
    ax.set_ylabel("分数")
    ax.set_title("岗位检索与多跳（本次主要收益）", pad=28)
    annotate(ax, list(bars1) + list(bars2))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper right", frameon=False, bbox_to_anchor=(1.02, 1.02), ncol=1, fontsize=8, handlelength=1.2)

    fig.tight_layout(rect=(0, 0, 1, 0.98))
    path = FIGURES / "rag_eval_v2.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {path.relative_to(ROOT)}")
    return path


def load_historical_easy() -> dict:
    path = RESULTS / "rag_eval.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data.get("summary") or []:
        if row.get("chunking") == "markdown_heading" and row.get("retriever") == "hybrid":
            return {
                "hit_at_1": row["hit_at_1"],
                "hit_at_5": row["hit_at_5"],
                "mrr_at_10": row["mrr_at_10"],
                "source": "experiments/results/rag_eval.json（标题切分 + hybrid）",
            }
    return {}


def pct(value) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def write_report(payload: dict, chart: Path) -> Path:
    hist = payload.get("historical_easy") or {}
    b, a = payload["pipelines"]["baseline"], payload["pipelines"]["improved"]
    route = payload["routing"]
    faith = payload.get("faithfulness") or {}
    lines = [
        "# RAG 知识库与检索改善评测（v2）",
        "",
        "在原有 11 篇政策易例（Hit@1=0.92）之外，补充了不含章节标题的改写题、近域拒答、",
        "在招岗位检索（含外部扩充库「懂车帝」）、多跳问题，以及意图路由准确率。",
        "检索配置与线上一致：标题切分 + hybrid，评测在内存 Chroma 上进行，不写入生产库。",
        "",
        "## 1. 易例对照（保留原指标）",
        "",
        "| 配置 | Hit@1 | Hit@5 | MRR@10 | 说明 |",
        "|---|---:|---:|---:|---|",
        f"| 历史评测（标题+hybrid，1000 职位干扰） | {pct(hist.get('hit_at_1'))} | {pct(hist.get('hit_at_5'))} | {hist.get('mrr_at_10', 0):.3f} | {hist.get('source', '—')} |",
        f"| 本次改善前（旧正文+旧切分，{payload['corpus']['baseline']['jobs']} 职位） | {pct(b['easy']['hit_at_1'])} | {pct(b['easy']['hit_at_5'])} | {b['easy']['mrr_at_10']:.3f} | 含免责声明切片、任职要求中的 provenance JSON |",
        f"| 本次改善后（清洗+卫生+全量职位+多样性） | {pct(a['easy']['hit_at_1'])} | {pct(a['easy']['hit_at_5'])} | {a['easy']['mrr_at_10']:.3f} | 知识库 {payload['corpus']['improved']['knowledge']} 片，职位 {payload['corpus']['improved']['jobs']} 条 |",
        "",
        "## 2. 难例与多跳",
        "",
        "| 集合 | 改善前 Hit@1 | 改善后 Hit@1 | 改善前 MRR@10 | 改善后 MRR@10 | 改善前 Recall@5 | 改善后 Recall@5 |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| 改写（不含章节标题） | {pct(b['hard']['hit_at_1'])} | {pct(a['hard']['hit_at_1'])} | {b['hard']['mrr_at_10']:.3f} | {a['hard']['mrr_at_10']:.3f} | {pct(b['hard']['recall_at_5'])} | {pct(a['hard']['recall_at_5'])} |",
        f"| 多跳 | {pct(b['multihop']['hit_at_1'])} | {pct(a['multihop']['hit_at_1'])} | {b['multihop']['mrr_at_10']:.3f} | {a['multihop']['mrr_at_10']:.3f} | {pct(b['multihop']['recall_at_5'])} | {pct(a['multihop']['recall_at_5'])} |",
        f"| 近域拒答（应检索为空） | 拒答 {pct(b['refusal']['reject_rate'])} | 拒答 {pct(a['refusal']['reject_rate'])} | — | — | — | — |",
        "",
        "## 3. 岗位检索",
        "",
        "改善前语料按原评测截断为按 id 排序的前 1000 条，外部扩充库（懂车帝等，id 从 12039 起）不在其中；",
        "改善后纳入全部在招职位，清洗 provenance，并按公司/职位做多样性截断。",
        "",
        "| 指标 | 改善前 | 改善后 |",
        "|---|---:|---:|",
        f"| Hit@1 | {pct(b['job']['hit_at_1'])} | {pct(a['job']['hit_at_1'])} |",
        f"| MRR@10 | {b['job']['mrr_at_10']:.3f} | {a['job']['mrr_at_10']:.3f} |",
        f"| Recall@5 | {pct(b['job']['recall_at_5'])} | {pct(a['job']['recall_at_5'])} |",
        f"| 「杭州 Java 后端」Top-5 不同公司数 | {b['job']['avg_unique_companies_top5']:.2f} | {a['job']['avg_unique_companies_top5']:.2f} |",
        "",
        "## 4. 意图路由",
        "",
        f"在 {route['n']} 道路由题上的准确率：**{pct(route['accuracy'])}**。",
        "覆盖：企业合规（只限男性、收培训费）不再误入筛选工具；学生薪资问题同时调用预测与在招职位检索；",
        "「懂车帝在招哪些产品经理」能识别企业名并走岗位检索。",
        "",
        "## 5. 端到端忠实度（可选）",
        "",
    ]
    if faith.get("available"):
        lines.append(
            f"提供方 `{faith.get('provider')}` / 模型 `{faith.get('model')}`，"
            f"子集 {faith.get('n')} 题，忠实回答比例 {pct(faith.get('faithful_rate'))}。"
            "判定规则：不引用免责声明、数字须出现在资料中、无资料时须拒答。"
            "将 `.env` 中 `LLM_PROVIDER` 换成云端后，用同一命令 `--faithfulness` 可重跑对比。"
        )
    else:
        lines.append(
            "本次未跑或大模型不可用（"
            + str(faith.get("error") or "未加 --faithfulness")
            + "）。脚本已按当前 `LLM_PROVIDER` 编写，换成 Gemini / OpenAI 兼容接口后可重跑。"
        )
    lines += [
        "",
        "## 6. 图",
        "",
        f"![改善前/后对比]({chart.relative_to(ROOT / 'experiments') if False else '../figures/' + chart.name})",
        "",
        "## 7. 复现",
        "",
        "```bash",
        ".venv/bin/python experiments/rag_eval/run_rag_eval_v2.py",
        ".venv/bin/python experiments/rag_eval/run_rag_eval_v2.py --faithfulness --faithfulness-limit 8",
        "```",
        "",
        f"评测时间（用户时区 Asia/Shanghai）：{payload.get('env', {}).get('time', '')}",
        f"改善前切片 {payload['corpus']['baseline']['total']}（知识库 {payload['corpus']['baseline']['knowledge']}，职位 {payload['corpus']['baseline']['jobs']}），",
        f"改善后切片 {payload['corpus']['improved']['total']}（知识库 {payload['corpus']['improved']['knowledge']}，职位 {payload['corpus']['improved']['jobs']}）。",
        "",
    ]
    path = Path(__file__).resolve().parent / "REPORT_v2.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[saved] {path.relative_to(ROOT)}")
    return path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="RAG v2 评测")
    parser.add_argument("--job-limit-baseline", type=int, default=1000, help="改善前职位干扰项条数，与原评测一致")
    parser.add_argument("--job-limit-improved", type=int, default=0, help="改善后职位条数，0 表示全部在招")
    parser.add_argument("--faithfulness", action="store_true", help="用当前 LLM_PROVIDER 做小规模忠实度评测")
    parser.add_argument("--faithfulness-limit", type=int, default=8)
    parser.add_argument("--same-scale", action="store_true", default=True, help="额外评测清洗后、同等 1000 职位规模的政策检索")
    parser.add_argument("--no-same-scale", action="store_false", dest="same_scale")
    parser.add_argument("--report-only", action="store_true", help="读取已有 rag_eval_v2.json 只重画图")
    parser.add_argument("--force-report", action="store_true", help="根据结果覆盖 REPORT_v2.md")
    args = parser.parse_args()

    if args.report_only:
        path = RESULTS / "rag_eval_v2.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        chart = write_chart(payload)
        report_path = Path(__file__).resolve().parent / "REPORT_v2.md"
        if args.force_report or not report_path.is_file():
            write_report(payload, chart)
        else:
            print(f"[keep] {report_path.relative_to(ROOT)}")
        print("完成", flush=True)
        return

    easy = check(QUESTIONS)
    v2 = load_v2_questions()
    hard = [row for row in v2 if row.get("set") == "hard"]
    multi = [row for row in v2 if row.get("set") == "multihop"]
    refusal = [row for row in v2 if row.get("set") == "refusal"]
    jobs_q = [row for row in v2 if row.get("set") == "job"]
    route_q = [row for row in v2 if row.get("set") == "routing"]

    print("加载在招职位", flush=True)
    all_rows = fetch_job_rows(None)
    baseline_rows = all_rows[: args.job_limit_baseline]
    improved_rows = all_rows if not args.job_limit_improved else all_rows[: args.job_limit_improved]
    print(f"在招 {len(all_rows)}，改善前用 {len(baseline_rows)}，改善后用 {len(improved_rows)}", flush=True)

    print("预热嵌入模型", flush=True)
    embed_query("预热")

    routing = evaluate_routing(route_q)
    print(f"路由准确率 {routing['accuracy']:.3f} ({routing['n']} 题)", flush=True)

    pipelines = {}
    gold_spans_used = {}
    indexes = {}
    for name, rows, cleaned, hygiene, diversify in (
        ("baseline", baseline_rows, False, False, False),
        ("improved", improved_rows, True, True, True),
    ):
        print(f"== 构建语料 {name}", flush=True)
        k_chunks, gold_spans = knowledge_chunks(hygiene)
        j_chunks = job_chunks(rows, cleaned)
        chunks = k_chunks + j_chunks
        gold_spans_used[name] = gold_spans
        print(f"  切片 {len(chunks)}（知识库 {len(k_chunks)}，职位 {len(j_chunks)}）", flush=True)
        index = MemoryIndex(name, chunks, embed_vectors(chunks))
        indexes[name] = index
        easy_m = evaluate_policy(index, easy, gold_spans, diversify)
        hard_m = evaluate_policy(index, hard, gold_spans, diversify)
        multi_m = evaluate_policy(index, multi, gold_spans, diversify)
        refusal_m = evaluate_policy(index, refusal, gold_spans, diversify)
        job_m = evaluate_jobs(index, jobs_q, diversify)
        pipelines[name] = {
            "easy": {k: v for k, v in easy_m.items() if k != "details"},
            "hard": {k: v for k, v in hard_m.items() if k != "details"},
            "multihop": {k: v for k, v in multi_m.items() if k != "details"},
            "refusal": {k: v for k, v in refusal_m.items() if k != "details"},
            "job": {k: v for k, v in job_m.items() if k != "details"},
            "details": {
                "easy": easy_m["details"],
                "hard": hard_m["details"],
                "multihop": multi_m["details"],
                "refusal": refusal_m["details"],
                "job": job_m["details"],
            },
        }
        print(
            f"  易例 Hit@1={easy_m['hit_at_1']:.3f} MRR={easy_m['mrr_at_10']:.3f} | "
            f"难例 Hit@1={hard_m['hit_at_1']:.3f} | "
            f"岗位 Hit@1={job_m['hit_at_1']:.3f} Recall@5={job_m['recall_at_5']:.3f}",
            flush=True,
        )

    if args.same_scale and len(improved_rows) > len(baseline_rows):
        print("== 构建语料 improved_same_scale", flush=True)
        k_chunks, gold_spans = knowledge_chunks(True)
        j_chunks = job_chunks(baseline_rows, True)
        chunks = k_chunks + j_chunks
        print(f"  切片 {len(chunks)}（知识库 {len(k_chunks)}，职位 {len(j_chunks)}）", flush=True)
        index = MemoryIndex("improved_same_scale", chunks, embed_vectors(chunks))
        easy_m = evaluate_policy(index, easy, gold_spans, True)
        hard_m = evaluate_policy(index, hard, gold_spans, True)
        multi_m = evaluate_policy(index, multi, gold_spans, True)
        refusal_m = evaluate_policy(index, refusal, gold_spans, True)
        pipelines["improved_same_scale"] = {
            "easy": {k: v for k, v in easy_m.items() if k != "details"},
            "hard": {k: v for k, v in hard_m.items() if k != "details"},
            "multihop": {k: v for k, v in multi_m.items() if k != "details"},
            "refusal": {k: v for k, v in refusal_m.items() if k != "details"},
        }
        print(
            f"  同等规模易例 Hit@1={easy_m['hit_at_1']:.3f} MRR={easy_m['mrr_at_10']:.3f} | "
            f"难例 Hit@1={hard_m['hit_at_1']:.3f} | 多跳 Hit@1={multi_m['hit_at_1']:.3f}",
            flush=True,
        )
        index.close()

    faith = {}
    if args.faithfulness:
        print("忠实度评测", flush=True)
        subset = hard + multi + refusal
        faith = run_faithfulness(indexes["improved"], subset, gold_spans_used["improved"], True, args.faithfulness_limit)
        print(f"  忠实度 {faith.get('faithful_rate')} available={faith.get('available')}", flush=True)

    for index in indexes.values():
        index.close()

    k0, _ = knowledge_chunks(False)
    j0 = job_chunks(baseline_rows, False)
    k1, _ = knowledge_chunks(True)
    j1 = job_chunks(improved_rows, True)
    corpus = {
        "baseline": {"jobs": len(baseline_rows), "knowledge": len(k0), "job_chunks": len(j0), "total": len(k0) + len(j0)},
        "improved": {"jobs": len(improved_rows), "knowledge": len(k1), "job_chunks": len(j1), "total": len(k1) + len(j1)},
    }
    if "improved_same_scale" in pipelines:
        ks, _ = knowledge_chunks(True)
        js = job_chunks(baseline_rows, True)
        corpus["improved_same_scale"] = {
            "jobs": len(baseline_rows),
            "knowledge": len(ks),
            "job_chunks": len(js),
            "total": len(ks) + len(js),
        }
    payload = {
        "env": env_info(),
        "historical_easy": load_historical_easy(),
        "corpus": corpus,
        "pipelines": pipelines,
        "routing": routing,
        "faithfulness": faith,
        "notes": (
            "改善前：旧职位正文（含 provenance JSON）、旧切分（含免责声明）、职位按 id 截断 1000、无多样性。"
            "改善后同等规模：清洗模板、去掉免责声明并合并短碎片、仍 1000 条职位。"
            "改善后全量：同上清洗，全部在招（含 ext_ats），按公司/职位多样性截断。检索均为 hybrid。"
            "易例在同等规模下用于观察清洗是否回退；全量无过滤是政策题的压力测试（线上会按 doc_type 排除岗位）。"
        ),
    }

    save_json("rag_eval_v2.json", payload)
    chart = write_chart(payload)
    report_path = Path(__file__).resolve().parent / "REPORT_v2.md"
    if args.force_report or not report_path.is_file():
        write_report(payload, chart)
    else:
        print(f"[keep] {report_path.relative_to(ROOT)}")
    print("完成", flush=True)


if __name__ == "__main__":
    main()
