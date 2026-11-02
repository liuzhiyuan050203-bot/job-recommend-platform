#!/usr/bin/env python3
"""RAG 切片方式与检索方式对比。

一条命令：
    .venv/bin/python experiments/rag_eval/run_rag_eval.py
    .venv/bin/python experiments/rag_eval/run_rag_eval.py --job-limit 1000

语料 = data/knowledge 下 11 个 Markdown + 数据库在招职位（默认最多 1000 条）。
职位文本用 ingest.load_job_texts，拼接方式与 load_jobs / _job_text 相同。
检索走与线上相同的 LangChain 组件：内存 Chroma（chromadb.EphemeralClient + langchain_chroma，
余弦空间，ef_search 与线上相同）上的 ChromaDenseRetriever、JiebaBM25Retriever、HybridRRFRetriever，
hybrid_rerank 再套 ContextualCompressionRetriever + CrossEncoderCompressor。不写入生产 Chroma。
嵌入模型与重排模型的首次加载不计入单查询延迟。

命中：切片在源文件中的字符区间与 gold 节区间重叠不少于 50 字，或切片完全落在该节内。
排序指标（Hit@1/3/5、MRR@10）在阈值过滤之前计算，候选池按 top_k=10，
即 N = max(20, 10*5) = 50。无关题拒答按生产默认 top_k 和同一套 keep_candidate 规则另计。
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "ai-service"))

from common import FIGURES, RESULTS, env_info, save_json, setup_matplotlib  # noqa: E402
from validate_questions import QUESTIONS, check  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.embedding import embed_documents, embed_query  # noqa: E402
from app.core.embedding import get_embedding_model  # noqa: E402
from app.rag.bm25 import bm25_document_text, candidate_pool_size  # noqa: E402
from app.rag.store import COLLECTION_METADATA  # noqa: E402
from app.rag.lc_retrievers import ChromaDenseRetriever, JiebaBM25Retriever, build_retriever  # noqa: E402
from app.rag.chunking import embed_input, split_fixed, split_markdown  # noqa: E402
from app.rag.ingest import doc_type_for_filename, load_job_texts  # noqa: E402
from app.rag.rerank import load_reranker, rerank_scores  # noqa: E402

KNOWLEDGE = ROOT / "data" / "knowledge"
HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*$", re.M)
CHUNKINGS = ("fixed", "markdown_heading")
RETRIEVERS = ("dense", "bm25", "hybrid", "hybrid_rerank")
METRIC_TOP_K = 10
OVERLAP_MIN = 50
LABELS = {
    "fixed": "定长",
    "markdown_heading": "标题",
    "dense": "稠密",
    "bm25": "BM25",
    "hybrid": "混合",
    "hybrid_rerank": "混合重排",
}


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


def section_at(spans: dict[str, list[tuple[int, int]]], pos: int) -> str:
    for name, ranges in spans.items():
        for start, end in ranges:
            if start <= pos < end:
                return name
    return ""


def locate_span(source: str, chunk: str, search_from: int) -> tuple[int, int] | None:
    """定位切片在原文中的覆盖区间。

    重叠拼接有时会丢掉两个字符的分隔符，整段不再是连续子串。
    这时取「重叠前缀」和「新增后缀」的最小覆盖区间，中间多出来的空隙一般只有换行。
    """
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


def locate_many(source: str, chunks: list[str]) -> list[tuple[int, int]]:
    spans = []
    cursor = 0
    for chunk in chunks:
        found = locate_span(source, chunk, cursor)
        if found is None:
            raise RuntimeError(f"无法在原文中定位切片：{chunk[:40]!r}")
        spans.append(found)
        cursor = found[0] + 1
    return spans


def build_corpus(chunking: str, jobs: list[dict]) -> tuple[list[dict], dict[str, dict[str, list[tuple[int, int]]]]]:
    size = settings.RAG_CHUNK_SIZE
    overlap = settings.RAG_CHUNK_OVERLAP
    chunks: list[dict] = []
    gold_spans: dict[str, dict[str, list[tuple[int, int]]]] = {}
    for path in sorted(KNOWLEDGE.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = markdown_title(text) or path.stem
        spans = section_spans(text)
        gold_spans[path.name] = spans
        if chunking == "markdown_heading":
            parts = split_markdown(text, size, overlap)
            located = locate_many(text, [piece for _section, piece in parts])
            for index, ((section, piece), (start, end)) in enumerate(zip(parts, located)):
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
                    }
                )
        else:
            parts = split_fixed(text, size, overlap)
            located = locate_many(text, parts)
            for index, (piece, (start, end)) in enumerate(zip(parts, located)):
                chunks.append(
                    {
                        "id": f"kb:{path.name}:{index}",
                        "file": path.name,
                        "source": "knowledge",
                        "title": title,
                        "section": section_at(spans, start),
                        "index_section": "",
                        "content": piece,
                        "start": start,
                        "end": end,
                        "doc_type": doc_type_for_filename(path.name),
                    }
                )
    for job in jobs:
        text = job["text"]
        title = job["title"]
        if chunking == "markdown_heading":
            parts = [(section, piece) for section, piece in split_markdown(text, size, overlap)]
        else:
            parts = [("", piece) for piece in split_fixed(text, size, overlap)]
        for index, (section, piece) in enumerate(parts):
            if len(piece.strip()) < 8:
                continue
            chunks.append(
                {
                    "id": f"{job['doc_key']}:{index}",
                    "file": "",
                    "source": "job",
                    "title": title,
                    "section": section,
                    "index_section": section if chunking == "markdown_heading" else "",
                    "content": piece,
                    "start": 0,
                    "end": 0,
                    "doc_type": 7,
                }
            )
    return chunks, gold_spans


def assert_markdown_spans(chunks: list[dict], gold_spans: dict[str, dict[str, list[tuple[int, int]]]]) -> None:
    bad = []
    for chunk in chunks:
        if chunk["source"] != "knowledge" or not chunk["index_section"]:
            continue
        ranges = gold_spans.get(chunk["file"], {}).get(chunk["index_section"]) or []
        if not any(spans_hit(chunk["start"], chunk["end"], start, end) for start, end in ranges):
            bad.append(f"{chunk['file']} / {chunk['index_section']} [{chunk['start']},{chunk['end']})")
    if bad:
        preview = "\n".join(bad[:8])
        raise SystemExit(f"标题切片与章节区间对不上，共 {len(bad)} 条：\n{preview}")


def embed_vectors(chunks: list[dict]) -> list[list[float]]:
    texts = [embed_input(chunk["title"], chunk["index_section"], chunk["content"]) for chunk in chunks]
    vectors: list[list[float]] = []
    batch = 64
    for offset in range(0, len(texts), batch):
        vectors.extend(embed_documents(texts[offset : offset + batch]))
        done = min(offset + batch, len(texts))
        if done == len(texts) or done % 256 == 0:
            print(f"  嵌入进度 {done}/{len(texts)}", flush=True)
    return [[float(v) for v in vector] for vector in vectors]


def question_hit(chunk: dict, gold: list[dict], gold_spans: dict[str, dict[str, list[tuple[int, int]]]]) -> bool:
    if chunk["source"] != "knowledge":
        return False
    for item in gold:
        if item["file"] != chunk["file"]:
            continue
        for start, end in gold_spans.get(item["file"], {}).get(item["section"], []):
            if spans_hit(chunk["start"], chunk["end"], start, end):
                return True
    return False


class LcIndex:
    """一种切分方式下的 LangChain 检索组件：内存 Chroma 稠密 + jieba BM25。"""

    def __init__(self, name: str, chunks: list[dict], vectors: list[list[float]]):
        import chromadb
        from langchain_chroma import Chroma

        self.client = chromadb.EphemeralClient()
        self.name = f"rag_eval_{name}"
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
                    {"doc_type": chunk["doc_type"], "title": chunk["title"], "section": chunk["index_section"]}
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

    def retriever(self, mode: str, top_k: int, apply_threshold: bool, rerank_fn):
        return build_retriever(
            dense=self.dense,
            bm25=self.bm25,
            mode=mode,
            top_k=top_k,
            threshold=float(settings.RAG_SCORE_THRESHOLD),
            pool=candidate_pool_size(top_k),
            apply_threshold=apply_threshold,
            rerank_scorer=rerank_fn,
        )

    def close(self) -> None:
        try:
            self.client.delete_collection(self.name)
        except Exception:
            pass


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def evaluate_config(
    retriever: str,
    chunks: list[dict],
    index: LcIndex,
    questions: list[dict],
    gold_spans: dict,
    rerank_cache: dict,
) -> dict:
    def rerank_fn(query: str, passages: list[str]):
        key = (query, tuple(passages))
        if key not in rerank_cache:
            rerank_cache[key] = rerank_scores(query, passages)
        return rerank_cache[key]

    # 排序指标：阈值前、top_k=10；无关题：生产 top_k + 生产阈值，返回空即拒答
    metric = index.retriever(retriever, METRIC_TOP_K, False, rerank_fn)
    prod = index.retriever(retriever, int(settings.RAG_TOP_K), True, rerank_fn)
    by_id = {chunk["id"]: chunk for chunk in chunks}
    details = []
    latencies = []
    irrelevant = []
    fallback = 0
    for row in questions:
        if row["gold"]:
            started = time.perf_counter()
            docs = metric.invoke(row["question"])
            elapsed = (time.perf_counter() - started) * 1000.0
            if retriever == "hybrid_rerank" and docs and docs[0].metadata.get("retrieval_mode") != "hybrid_rerank":
                fallback += 1
            ranked = []
            hit_rank = None
            for rank, doc in enumerate(docs[:METRIC_TOP_K], start=1):
                chunk = by_id[doc.id]
                hit = question_hit(chunk, row["gold"], gold_spans)
                if hit and hit_rank is None:
                    hit_rank = rank
                ranked.append(
                    {
                        "rank": rank,
                        "id": doc.id,
                        "file": chunk["file"],
                        "section": chunk["section"],
                        "start": chunk["start"],
                        "end": chunk["end"],
                        "score": round(float(doc.metadata.get("cosine") or 0.0), 4),
                        "bm25": round(float(doc.metadata.get("bm25") or 0.0), 4),
                        "rrf": round(float(doc.metadata.get("rrf") or 0.0), 6),
                        "hit": hit,
                    }
                )
            latencies.append(elapsed)
            details.append(
                {
                    "id": row["id"],
                    "type": row["type"],
                    "question": row["question"],
                    "gold": row["gold"],
                    "hit_rank": hit_rank,
                    "reciprocal_rank": 0.0 if not hit_rank or hit_rank > 10 else 1.0 / hit_rank,
                    "latency_ms": round(elapsed, 3),
                    "topk": ranked,
                }
            )
            continue
        kept = prod.invoke(row["question"])
        if retriever == "hybrid_rerank" and kept and kept[0].metadata.get("retrieval_mode") != "hybrid_rerank":
            fallback += 1
        irrelevant.append(
            {
                "id": row["id"],
                "question": row["question"],
                "rejected": len(kept) == 0,
                "kept": len(kept),
                "top_score": round(float(kept[0].metadata.get("cosine") or 0.0), 4) if kept else None,
                "top_bm25": round(float(kept[0].metadata.get("bm25") or 0.0), 4) if kept else None,
                "mode": kept[0].metadata.get("retrieval_mode") if kept else retriever,
            }
        )
    answered = details
    def rate(k: int) -> float:
        if not answered:
            return 0.0
        return sum(1 for item in answered if item["hit_rank"] and item["hit_rank"] <= k) / len(answered)

    mrr = sum(item["reciprocal_rank"] for item in answered) / len(answered) if answered else 0.0
    reject = sum(1 for item in irrelevant if item["rejected"]) / len(irrelevant) if irrelevant else 0.0
    return {
        "hit_at_1": rate(1),
        "hit_at_3": rate(3),
        "hit_at_5": rate(5),
        "mrr_at_10": mrr,
        "latency_mean_ms": float(np.mean(latencies)) if latencies else 0.0,
        "latency_p95_ms": percentile(latencies, 95),
        "irrelevant_reject_rate": reject,
        "rerank_fallback": fallback,
        "details": answered,
        "irrelevant": irrelevant,
    }


def write_csv(rows: list[dict]) -> Path:
    path = RESULTS / "rag_eval.csv"
    fields = [
        "chunking",
        "retriever",
        "hit_at_1",
        "hit_at_3",
        "hit_at_5",
        "mrr_at_10",
        "latency_mean_ms",
        "latency_p95_ms",
        "irrelevant_reject_rate",
        "questions",
        "irrelevant_questions",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fields})
    print(f"[saved] {path.relative_to(ROOT)}")
    return path


def write_figures(rows: list[dict]) -> None:
    plt = setup_matplotlib()
    labels = [f"{LABELS[row['chunking']]}/{LABELS[row['retriever']]}" for row in rows]
    x = np.arange(len(rows))
    width = 0.25
    fig, ax = plt.subplots(figsize=(12.2, 5.2))
    for offset, key, label in ((-width, "hit_at_1", "Hit@1"), (0, "hit_at_3", "Hit@3"), (width, "hit_at_5", "Hit@5")):
        ax.bar(x + offset, [row[key] for row in rows], width, label=label)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("命中率")
    ax.set_title("RAG 检索 Hit@1 / Hit@3 / Hit@5")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "rag_eval_hit.png")
    plt.close(fig)
    print(f"[saved] {(FIGURES / 'rag_eval_hit.png').relative_to(ROOT)}")

    fig, ax = plt.subplots(figsize=(12.2, 5.2))
    ax.bar(x - width / 2, [row["latency_mean_ms"] for row in rows], width, label="平均延迟")
    ax.bar(x + width / 2, [row["latency_p95_ms"] for row in rows], width, label="P95 延迟")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("毫秒")
    ax.set_title("RAG 单查询延迟（不含首次模型加载）")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "rag_eval_latency.png")
    plt.close(fig)
    print(f"[saved] {(FIGURES / 'rag_eval_latency.png').relative_to(ROOT)}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="RAG 切片与检索评测")
    parser.add_argument("--job-limit", type=int, default=1000, help="在招职位干扰项条数，默认 1000。全库约 4800 条，嵌入太慢所以截断")
    args = parser.parse_args()
    questions = check(QUESTIONS)
    print(f"加载在招职位，上限 {args.job_limit}", flush=True)
    jobs = load_job_texts(args.job_limit)
    print(f"职位文本 {len(jobs)} 条", flush=True)

    print("预热嵌入模型（不计入查询延迟）", flush=True)
    warm_started = time.perf_counter()
    embed_query("预热")
    embed_warm_ms = (time.perf_counter() - warm_started) * 1000.0
    print("预热重排模型（不计入查询延迟）", flush=True)
    rerank_started = time.perf_counter()
    reranker = load_reranker()
    rerank_ok = reranker is not None
    if rerank_ok:
        list(reranker.rerank("预热", ["这是一段预热文本，用来把交叉编码器加载进内存。"]))
    rerank_warm_ms = (time.perf_counter() - rerank_started) * 1000.0
    print(f"重排模型{'已加载' if rerank_ok else '加载失败，hybrid_rerank 将退回 hybrid'}", flush=True)

    summary = []
    details = {}
    chunk_counts = {}
    rerank_cache: dict = {}
    for chunking in CHUNKINGS:
        print(f"== 切分 {chunking}", flush=True)
        chunks, gold_spans = build_corpus(chunking, jobs)
        if chunking == "markdown_heading":
            assert_markdown_spans(chunks, gold_spans)
        knowledge_n = sum(1 for chunk in chunks if chunk["source"] == "knowledge")
        job_n = sum(1 for chunk in chunks if chunk["source"] == "job")
        chunk_counts[chunking] = {"total": len(chunks), "knowledge": knowledge_n, "jobs": job_n}
        print(f"  切片 {len(chunks)}（知识库 {knowledge_n}，职位 {job_n}）", flush=True)
        index = LcIndex(chunking, chunks, embed_vectors(chunks))
        for retriever in RETRIEVERS:
            print(f"  检索 {retriever}", flush=True)
            result = evaluate_config(retriever, chunks, index, questions, gold_spans, rerank_cache)
            row = {
                "chunking": chunking,
                "retriever": retriever,
                "hit_at_1": round(result["hit_at_1"], 4),
                "hit_at_3": round(result["hit_at_3"], 4),
                "hit_at_5": round(result["hit_at_5"], 4),
                "mrr_at_10": round(result["mrr_at_10"], 4),
                "latency_mean_ms": round(result["latency_mean_ms"], 2),
                "latency_p95_ms": round(result["latency_p95_ms"], 2),
                "irrelevant_reject_rate": round(result["irrelevant_reject_rate"], 4),
                "questions": 50,
                "irrelevant_questions": 5,
                "rerank_fallback": result["rerank_fallback"],
            }
            summary.append(row)
            details[f"{chunking}|{retriever}"] = {
                "questions": result["details"],
                "irrelevant": result["irrelevant"],
            }
            print(
                f"    Hit@1={row['hit_at_1']:.3f} Hit@3={row['hit_at_3']:.3f} "
                f"Hit@5={row['hit_at_5']:.3f} MRR={row['mrr_at_10']:.3f} "
                f"延迟 {row['latency_mean_ms']:.1f}/{row['latency_p95_ms']:.1f} ms "
                f"拒答 {row['irrelevant_reject_rate']:.2f}",
                flush=True,
            )
        index.close()

    payload = {
        "env": env_info(),
        "job_limit": args.job_limit,
        "jobs_loaded": len(jobs),
        "chunk_counts": chunk_counts,
        "metric_top_k": METRIC_TOP_K,
        "candidate_pool": candidate_pool_size(METRIC_TOP_K),
        "production_top_k": int(settings.RAG_TOP_K),
        "production_pool": candidate_pool_size(int(settings.RAG_TOP_K)),
        "score_threshold": float(settings.RAG_SCORE_THRESHOLD),
        "overlap_chars": OVERLAP_MIN,
        "embed_warmup_ms": round(embed_warm_ms, 1),
        "rerank_warmup_ms": round(rerank_warm_ms, 1),
        "rerank_loaded": rerank_ok,
        "notes": (
            "Hit/MRR 在阈值过滤前、按 top_k=10 的候选池计算。"
            "无关题拒答使用生产 RAG_TOP_K 对应的候选池和生产 keep_candidate 规则。"
            "检索经 LangChain 组件（内存 Chroma + JiebaBM25Retriever + HybridRRFRetriever"
            " + 可选 ContextualCompressionRetriever 重排），与线上 get_retriever 同一实现。"
            "职位只作干扰项。首次模型加载不计入延迟。"
        ),
        "summary": summary,
        "details": details,
    }
    save_json("rag_eval.json", payload)
    write_csv(summary)
    write_figures(summary)
    print("完成", flush=True)


if __name__ == "__main__":
    main()
