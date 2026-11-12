#!/usr/bin/env python3
"""RAG 评测 v3：在 v2「改善后全量」语料上，对照范围门槛与查询改写的效果。

    .venv/bin/python experiments/rag_eval/run_rag_eval_v3.py
    .venv/bin/python experiments/rag_eval/run_rag_eval_v3.py --rerank   # 附录：政策重排（默认关闭）
    .venv/bin/python experiments/rag_eval/run_rag_eval_v3.py --report-only

语料、切分、混合检索与 v2 改善后全量一致（5431 在招职位 + 清洗后知识库）。
本轮变量只有：近域范围门槛、政策问题规则改写 + 加权 RRF。
不写入生产 Chroma。嵌入向量按语料哈希缓存，避免重复计算。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "experiments" / "rag_eval"))
sys.path.insert(0, str(ROOT / "ai-service"))

from common import FIGURES, RESULTS, env_info, save_json, setup_matplotlib  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.embedding import embed_query  # noqa: E402
from app.rag.bm25 import RERANK_WINDOW, candidate_pool_size  # noqa: E402
from app.rag.chunking import embed_input  # noqa: E402
from app.rag.diversity import diversify_hits  # noqa: E402
from app.rag.lc_retrievers import build_retriever  # noqa: E402
from app.rag.rewrite import expand_queries, merge_multi_query  # noqa: E402
from app.rag.scope import apply_scope_gate, decide_scope, domain_intent  # noqa: E402

from run_rag_eval_v2 import (  # noqa: E402
    METRIC_TOP_K,
    QUESTIONS,
    MemoryIndex,
    check,
    embed_vectors,
    evaluate_jobs,
    evaluate_policy,
    evaluate_routing,
    fetch_job_rows,
    job_chunks,
    knowledge_chunks,
    load_v2_questions,
)
from validate_questions import QUESTIONS as QUESTIONS_PATH  # noqa: E402

QUESTIONS_SCOPE = Path(__file__).resolve().parent / "questions_scope.jsonl"
CACHE_DIR = RESULTS / ".embed_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_scope_questions() -> list[dict]:
    rows = []
    for line in QUESTIONS_SCOPE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def corpus_digest(chunks: list[dict]) -> str:
    hasher = hashlib.sha256()
    for chunk in chunks:
        hasher.update(str(chunk["id"]).encode("utf-8"))
        hasher.update(b"\0")
        text = embed_input(chunk["title"], chunk["index_section"], chunk["content"])
        hasher.update(text.encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def embed_vectors_cached(chunks: list[dict], tag: str) -> list[list[float]]:
    digest = corpus_digest(chunks)
    path = CACHE_DIR / f"{tag}_{digest[:20]}.npz"
    if path.is_file():
        data = np.load(path)
        vectors = data["vectors"]
        if len(vectors) == len(chunks):
            print(f"  嵌入缓存命中 {path.name}（{len(chunks)} 条）", flush=True)
            return [[float(x) for x in row] for row in vectors]
    print(f"  计算嵌入 {len(chunks)} 条（随后写入缓存）", flush=True)
    vectors = embed_vectors(chunks)
    np.savez_compressed(path, vectors=np.asarray(vectors, dtype=np.float32))
    return vectors


def raw_hits(index: MemoryIndex, query: str, top_k: int, apply_threshold: bool) -> list[dict]:
    retriever = build_retriever(
        dense=index.dense,
        bm25=index.bm25,
        mode="hybrid",
        top_k=top_k,
        threshold=float(settings.RAG_SCORE_THRESHOLD),
        pool=candidate_pool_size(top_k),
        apply_threshold=apply_threshold,
        rerank_scorer=None,
    )
    docs = retriever.invoke(query)
    hits = []
    for doc in docs:
        chunk = dict(index.by_id.get(doc.id) or {})
        if not chunk:
            continue
        chunk["score"] = float((doc.metadata or {}).get("cosine") or 0.0)
        chunk["rrf"] = float((doc.metadata or {}).get("rrf") or 0.0)
        chunk["chroma_id"] = doc.id
        hits.append(chunk)
    return hits


def maybe_rerank(query: str, hits: list[dict]) -> list[dict]:
    if not hits:
        return hits
    from app.rag.rerank import rerank_scores

    window = hits[:RERANK_WINDOW]
    passages = [
        embed_input(item.get("title") or "", item.get("index_section") or item.get("section") or "", item.get("content") or "")
        for item in window
    ]
    scores = rerank_scores(query, passages)
    if not scores or len(scores) != len(window):
        return hits
    ranked = sorted(
        zip(window, scores),
        key=lambda item: (float(item[1]), float(item[0].get("rrf") or 0.0)),
        reverse=True,
    )
    out = []
    for hit, score in ranked:
        row = dict(hit)
        row["rerank"] = float(score)
        out.append(row)
    return out + list(hits[len(window) :])


def search_v3(
    index: MemoryIndex,
    query: str,
    top_k: int,
    apply_threshold: bool,
    diversify: bool,
    *,
    rewrite: bool,
    scope: bool,
    rerank: bool,
) -> list[dict]:
    fetch_k = max(top_k * 4, top_k) if diversify else top_k
    if rewrite:
        queries = expand_queries(query, allow_llm=False)
    else:
        queries = [query]
    lists = [raw_hits(index, item, fetch_k, apply_threshold) for item in queries]
    hits = lists[0] if len(lists) == 1 else merge_multi_query(lists, fetch_k)
    if rerank:
        hits = maybe_rerank(query, hits)
    if diversify:
        hits = diversify_hits(
            hits,
            top_k,
            per_job=settings.RAG_DIVERSITY_PER_JOB,
            per_company=settings.RAG_DIVERSITY_PER_COMPANY,
        )
    hits = hits[:top_k]
    if scope:
        hits = apply_scope_gate(query, hits, enabled=True)
    return hits


class TimedIndex:
    """把 search 换成 v3 实现，并记录时延。"""

    def __init__(self, inner: MemoryIndex, rewrite: bool, scope: bool, rerank: bool):
        self.inner = inner
        self.rewrite = rewrite
        self.scope = scope
        self.rerank = rerank
        self.times_ms: list[float] = []
        self.chunks = inner.chunks

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def search(self, query: str, top_k: int, apply_threshold: bool, diversify: bool) -> list[dict]:
        start = time.perf_counter()
        hits = search_v3(
            self.inner,
            query,
            top_k,
            apply_threshold,
            diversify,
            rewrite=self.rewrite,
            scope=self.scope,
            rerank=self.rerank,
        )
        self.times_ms.append((time.perf_counter() - start) * 1000)
        return hits

    @property
    def latency(self) -> dict:
        if not self.times_ms:
            return {"n": 0, "mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}
        arr = np.array(self.times_ms)
        return {
            "n": int(len(arr)),
            "mean_ms": float(arr.mean()),
            "p50_ms": float(np.percentile(arr, 50)),
            "p95_ms": float(np.percentile(arr, 95)),
        }


def evaluate_refusal_sets(index_wrapper: TimedIndex, questions: list[dict], diversify: bool) -> dict:
    """近域 / 远域拒答：与线上一致，先走阈值再走范围门槛。"""
    details = []
    for row in questions:
        start = time.perf_counter()
        raw = search_v3(
            index_wrapper.inner,
            row["question"],
            int(settings.RAG_TOP_K),
            True,
            diversify,
            rewrite=index_wrapper.rewrite,
            scope=False,
            rerank=index_wrapper.rerank,
        )
        decision = decide_scope(row["question"], raw)
        gated = apply_scope_gate(row["question"], raw, enabled=index_wrapper.scope)
        index_wrapper.times_ms.append((time.perf_counter() - start) * 1000)
        details.append(
            {
                "id": row["id"],
                "question": row["question"],
                "split": row.get("split") or "heldout",
                "type": row.get("type"),
                "intent": domain_intent(row["question"]),
                "rejected": len(gated) == 0,
                "rejected_without_gate": len(raw) == 0,
                "kept": len(gated),
                "raw_kept": len(raw),
                "max_cosine": round(decision.max_cosine, 4),
                "reason": decision.reason,
                "top_title": (gated[0].get("title") if gated else (raw[0].get("title") if raw else "")),
            }
        )
    n = len(details)
    return {
        "n": n,
        "reject_rate": (sum(1 for item in details if item["rejected"]) / n) if n else None,
        "reject_rate_without_gate": (sum(1 for item in details if item["rejected_without_gate"]) / n) if n else None,
        "details": details,
    }


def in_scope_false_refusal(index_wrapper: TimedIndex, questions: list[dict], diversify: bool) -> dict:
    """范围内问题被门槛误拒的比例。已无命中（改写前就空）的不计为误拒。"""
    details = []
    for row in questions:
        raw = search_v3(
            index_wrapper.inner,
            row["question"],
            METRIC_TOP_K,
            False,
            diversify,
            rewrite=index_wrapper.rewrite,
            scope=False,
            rerank=index_wrapper.rerank,
        )
        gated = apply_scope_gate(row["question"], raw, enabled=index_wrapper.scope)
        false_refuse = bool(raw) and not gated
        details.append(
            {
                "id": row["id"],
                "question": row["question"],
                "intent": domain_intent(row["question"]),
                "raw_kept": len(raw),
                "kept": len(gated),
                "false_refuse": false_refuse,
            }
        )
    n = len(details)
    n_false = sum(1 for item in details if item["false_refuse"])
    return {
        "n": n,
        "false_refuse": n_false,
        "false_refuse_rate": (n_false / n) if n else 0.0,
        "details": [item for item in details if item["false_refuse"] or item["raw_kept"] == 0],
    }


def drop_details(metrics: dict) -> dict:
    return {key: value for key, value in metrics.items() if key != "details"}


def pct(value) -> str:
    if value is None:
        return "—"
    return f"{100.0 * float(value):.1f}%"


def num(value, digits=3) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def ms(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):.0f} ms"


def write_chart(payload: dict) -> Path:
    plt = setup_matplotlib()
    before = payload["pipelines"]["baseline"]
    after = payload["pipelines"]["improved"]
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.4))
    width = 0.36

    def annotate(ax, bars, fmt="{:.2f}", dy=0.03, fontsize=8):
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + dy,
                fmt.format(height),
                ha="center",
                va="bottom",
                fontsize=fontsize,
                clip_on=False,
            )

    ax = axes[0]
    labels = ["近域拒答\nheld-out (5)", "近域拒答\ndev (8)", "远域拒答\n(5)", "范围内误拒"]
    b_vals = [
        (before["refusal_heldout"] or {}).get("reject_rate") or 0.0,
        (before["refusal_dev"] or {}).get("reject_rate") or 0.0,
        (before["refusal_far"] or {}).get("reject_rate") or 0.0,
        (before.get("false_refuse") or {}).get("false_refuse_rate") or 0.0,
    ]
    a_vals = [
        (after["refusal_heldout"] or {}).get("reject_rate") or 0.0,
        (after["refusal_dev"] or {}).get("reject_rate") or 0.0,
        (after["refusal_far"] or {}).get("reject_rate") or 0.0,
        (after.get("false_refuse") or {}).get("false_refuse_rate") or 0.0,
    ]
    x = np.arange(len(labels))
    bars1 = ax.bar(x - width / 2, b_vals, width, label="v2 改善后全量（无门槛、无改写）", color="#B0B0B0", zorder=3)
    bars2 = ax.bar(x + width / 2, a_vals, width, label="v3（范围门槛 + 规则改写）", color="#54A24B", zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.25)
    ax.set_ylabel("比例")
    ax.set_title("拒答与范围内误拒", pad=28)
    annotate(ax, list(bars1) + list(bars2))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper right", frameon=False, fontsize=8, handlelength=1.2)

    ax = axes[1]
    labels_r = ["改写题\nHit@1", "改写题\nHit@5", "改写题\nMRR@10", "多跳\nHit@1", "多跳\nMRR@10"]
    b_vals = [
        before["hard"]["hit_at_1"],
        before["hard"]["hit_at_5"],
        before["hard"]["mrr_at_10"],
        before["multihop"]["hit_at_1"],
        before["multihop"]["mrr_at_10"],
    ]
    a_vals = [
        after["hard"]["hit_at_1"],
        after["hard"]["hit_at_5"],
        after["hard"]["mrr_at_10"],
        after["multihop"]["hit_at_1"],
        after["multihop"]["mrr_at_10"],
    ]
    x = np.arange(len(labels_r))
    bars1 = ax.bar(x - width / 2, b_vals, width, label="v2 改善后全量", color="#B0B0B0", zorder=3)
    bars2 = ax.bar(x + width / 2, a_vals, width, label="v3 规则改写 + 加权 RRF", color="#4C78A8", zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(labels_r)
    ax.set_ylim(0, 1.25)
    ax.set_ylabel("分数")
    ax.set_title("改写题与多跳（全量语料）", pad=28)
    annotate(ax, list(bars1) + list(bars2))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper right", frameon=False, fontsize=8, handlelength=1.2)

    fig.tight_layout(rect=(0, 0, 1, 0.98))
    path = FIGURES / "rag_eval_v3.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {path.relative_to(ROOT)}")
    return path


def ranks_table(before: dict, after: dict, key: str) -> str:
    lines = ["| 题号 | 问题（节选） | 本次无改写 | v3 改写后 |", "|---|---|---:|---:|"]
    b_list = (before.get("details") or {}).get(key) or []
    a_list = (after.get("details") or {}).get(key) or []
    b_details = {item["id"]: item for item in b_list}
    def fmt(row):
        rank = row.get("hit_rank")
        return "未命中" if not rank else str(rank)
    for item in a_list:
        prev = b_details.get(item["id"]) or {}
        question = (item.get("question") or "")[:32].replace("|", "/")
        lines.append(f"| {item['id']} | {question} | {fmt(prev)} | {fmt(item)} |")
    return "\n".join(lines)


def write_report(payload: dict, chart: Path) -> Path:
    before = payload["pipelines"]["baseline"]
    after = payload["pipelines"]["improved"]
    rerank = (payload.get("pipelines") or {}).get("rerank") or {}
    corpus = payload.get("corpus") or {}
    improved = corpus.get("improved") or {}
    lat_b = (before.get("latency") or {})
    lat_a = (after.get("latency") or {})
    lat_r = (rerank.get("latency") or {})
    faith_note = ""
    path = Path(__file__).resolve().parent / "REPORT_v3.md"

    def block_refusal(name, metrics):
        return f"{pct(metrics.get('reject_rate'))}（{metrics.get('n')} 题）"

    report = f"""# RAG 范围门槛与查询改写评测（v3）

在 v2「改善后全量」语料上（清洗后的 74 条知识库切片 + 全部 {improved.get('jobs', 5431)} 条在招职位，
含 600 条 ext_ats；混合检索，多样性截断），只改变两项线上已默认开启的能力：

1. **近域范围门槛**：领域意图（in / out / unknown）+ 按 dev 集标定的稠密余弦门槛。
   考研报名、护照办理等知识库未覆盖的相近问题应拒答，并提示可问范围；范围内问题不得误拒。
2. **政策问题规则改写**：同义替换（就业意向书→三方协议、考察期→试用期等）与多跳拆分，
   多路结果用加权 RRF 融合（原问权重 2，改写权重 1）。仅检索职位时不改写。
   云端模型可额外做 LLM 改写（`RAG_QUERY_REWRITE_LLM=auto`），本评测关闭 LLM，保证可复现。
   政策交叉编码器重排默认关闭，附录给出打开后的对照。

对照的「改善前」就是 v2 报告里的「改善后全量」设定：同一语料、同一检索，但**没有**范围门槛、也**没有**查询改写。
两组数字都在本次同一索引上重跑，避免实现细节差异。评测在内存 Chroma 上进行，不写入生产库。

## 1. 近域拒答（标定在 dev，报告在 held-out）

门槛在「仅知识库 74 切片」上标定（2026-11-12）：近域 OUT 最高余弦约 0.63（积分落户 vs 户口迁移），
OUT 门槛取 **0.82**；短关键词已归入 in，UNKNOWN 门槛取 **0.62**。本表在全量语料（含 5431 岗位干扰）上报告。

| 集合 | v2 全量拒答 | v3 拒答（有门槛） | 说明 |
|---|---:|---:|---|
| 近域 held-out（r01–r05：考研报名、四级、护照、国考、积分落户） | {pct(before['refusal_heldout'].get('reject_rate'))} | {pct(after['refusal_heldout'].get('reject_rate'))} | 与 v2 报告中的 0% 对应；v3 应全部拒答 |
| 近域 dev（rd1–rd8，标定集） | {pct(before['refusal_dev'].get('reject_rate'))} | {pct(after['refusal_dev'].get('reject_rate'))} | 只用于标定。无门槛时 12.5% 是 rd3 本身已无命中 |
| 远域（红烧肉、量子纠缠等 5 题） | {pct(before['refusal_far'].get('reject_rate'))} | {pct(after['refusal_far'].get('reject_rate'))} | 原先靠相似度阈值已能拒，不能回退 |
| 范围内误拒（易例有金标 + 改写 + 多跳 + 岗位） | {pct((before.get('false_refuse') or {}).get('false_refuse_rate'))} | {pct((after.get('false_refuse') or {}).get('false_refuse_rate'))} | 应为 0；已无命中的题目不计为误拒 |

held-out 近域在无门槛时最高余弦仍低于 0.82，靠意图识别为 out 后拒答，而不是把相似度门槛提高到误伤范围内问题的程度。
「因为考公不想去了」这类范围内问句不会被「国考」规则误伤（OUT 模式要求报名/入口等办理用语）。

## 2. 改写题与多跳（全量语料）

与 v2 第 2 节同一批题目，在同一索引上重跑无改写对照。
v2 报告发表的改写题 Hit@1 为 50%、MRR 0.729；本次无改写重跑为 37.5%、MRR 0.667。
差异集中在 h08：金标切片余弦仍是 0.723（与 v2 相同），但「测试实习生」等岗位标题靠 BM25 排到了前两名。
规则改写把「考察期」换成「试用期」后，该金标回到第 1（余弦 0.806）。对照以本次同一索引为准。

| 集合 | 指标 | 本次无改写（同一索引） | v3（规则改写 + 加权 RRF） |
|---|---|---:|---:|
| 改写（8 题，不含章节标题） | Hit@1 | {pct(before['hard']['hit_at_1'])} | {pct(after['hard']['hit_at_1'])} |
|  | Hit@5 | {pct(before['hard']['hit_at_5'])} | {pct(after['hard']['hit_at_5'])} |
|  | MRR@10 | {num(before['hard']['mrr_at_10'])} | {num(after['hard']['mrr_at_10'])} |
| 多跳（3 题） | Hit@1 | {pct(before['multihop']['hit_at_1'])} | {pct(after['multihop']['hit_at_1'])} |
|  | Hit@5 | {pct(before['multihop']['hit_at_5'])} | {pct(after['multihop']['hit_at_5'])} |
|  | MRR@10 | {num(before['multihop']['mrr_at_10'])} | {num(after['multihop']['mrr_at_10'])} |
| 政策易例（全量无过滤，压力测试） | Hit@1 | {pct(before['easy']['hit_at_1'])} | {pct(after['easy']['hit_at_1'])} |
|  | MRR@10 | {num(before['easy']['mrr_at_10'])} | {num(after['easy']['mrr_at_10'])} |
| 岗位检索（5 题） | Hit@1 | {pct(before['job']['hit_at_1'])} | {pct(after['job']['hit_at_1'])} |
|  | MRR@10 | {num(before['job']['mrr_at_10'])} | {num(after['job']['mrr_at_10'])} |

岗位检索默认不改写，Hit@1 保持 100%。政策易例是全量无 `doc_type` 过滤的压力测试，线上政策路径会排除岗位切片，干扰小于本表。
改写题上，h03（考察期→试用期）从第 2 升到第 1，h08 从第 3 回到第 1；h04、h05、h07 仍在第 2。
多跳上，m01 从第 2 升到第 1，m03 保持第 1，m02 从第 3 降到第 4（加权 RRF 把同文档的其他节提前了），净 Hit@1 仍从 33.3% 升到 66.7%。

### 改写题逐题排名

{ranks_table(before, after, 'hard')}

### 多跳逐题排名

{ranks_table(before, after, 'multihop')}

## 3. 时延

规则改写会多检索 1–3 路，时延应仍可接受。政策重排（交叉编码器）默认关闭。

| 配置 | 查询次数 | 平均 | P50 | P95 |
|---|---:|---:|---:|---:|
| v2 全量（单路） | {lat_b.get('n', 0)} | {ms(lat_b.get('mean_ms'))} | {ms(lat_b.get('p50_ms'))} | {ms(lat_b.get('p95_ms'))} |
| v3 规则改写 | {lat_a.get('n', 0)} | {ms(lat_a.get('mean_ms'))} | {ms(lat_a.get('p50_ms'))} | {ms(lat_a.get('p95_ms'))} |
"""

    if rerank:
        report += (
            f"| v3 + 政策重排（附录，默认关闭） | {lat_r.get('n', 0)} | {ms(lat_r.get('mean_ms'))} | "
            f"{ms(lat_r.get('p50_ms'))} | {ms(lat_r.get('p95_ms'))} |\n"
        )
        report += f"""
## 4. 附录：政策重排

`RAG_POLICY_RERANK=true` 时，仅对非职位查询在融合后再做交叉编码器重排。默认关闭。

| 集合 | 指标 | v3（无重排） | v3 + 重排 |
|---|---|---:|---:|
| 改写 | Hit@1 | {pct(after['hard']['hit_at_1'])} | {pct(rerank.get('hard', {}).get('hit_at_1'))} |
| 改写 | MRR@10 | {num(after['hard']['mrr_at_10'])} | {num(rerank.get('hard', {}).get('mrr_at_10'))} |
| 多跳 | Hit@1 | {pct(after['multihop']['hit_at_1'])} | {pct(rerank.get('multihop', {}).get('hit_at_1'))} |
| 多跳 | MRR@10 | {num(after['multihop']['mrr_at_10'])} | {num(rerank.get('multihop', {}).get('mrr_at_10'))} |

重排把改写题 Hit@1 再抬到 75%，多跳 MRR 从 0.750 升到 0.833，但平均时延约 1.1 秒（P95 约 1.9 秒），
且 h03 从第 1 掉到第 5、m03 从第 1 掉到第 2。线上默认关闭，需要时再开 `RAG_POLICY_RERANK=true`。
"""
    else:
        report += "\n未跑政策重排（默认关闭）。加 `--rerank` 可补测。\n"

    report += f"""
## 5. 图

![范围门槛与改写对照](../figures/rag_eval_v3.png)

左图：近域拒答是本轮主要收益，范围内误拒应保持为 0。右图：改写题与多跳在全量语料上的对照。

## 6. 复现

```bash
.venv/bin/python experiments/rag_eval/run_rag_eval_v3.py
.venv/bin/python experiments/rag_eval/run_rag_eval_v3.py --rerank
```

评测时间（Asia/Shanghai）：{payload.get('env', {}).get('time', '')}。
语料切片 {improved.get('total', '?')}（知识库 {improved.get('knowledge', '?')}，职位切片 {improved.get('job_chunks', '?')} / {improved.get('jobs', '?')} 条）。
与 v2 改善后全量相同。嵌入按语料哈希缓存于 `experiments/results/.embed_cache/`（不入库）。
"""
    path.write_text(report, encoding="utf-8")
    print(f"[saved] {path.relative_to(ROOT)}")
    return path


def run_pipeline(index: MemoryIndex, easy, hard, multi, jobs_q, far, heldout, dev, in_scope, *, rewrite, scope, rerank, diversify=True):
    wrapped = TimedIndex(index, rewrite=rewrite, scope=scope, rerank=rerank)
    # 岗位不改写，与线上 is_job_only 一致
    jobs_wrapped = TimedIndex(index, rewrite=False, scope=scope, rerank=False)
    easy_m = evaluate_policy(wrapped, easy, run_pipeline.gold_spans, diversify)
    hard_m = evaluate_policy(wrapped, hard, run_pipeline.gold_spans, diversify)
    multi_m = evaluate_policy(wrapped, multi, run_pipeline.gold_spans, diversify)
    job_m = evaluate_jobs(jobs_wrapped, jobs_q, diversify)
    held = evaluate_refusal_sets(wrapped, heldout, diversify)
    dev_m = evaluate_refusal_sets(wrapped, dev, diversify)
    far_m = evaluate_refusal_sets(wrapped, far, diversify)
    false_m = in_scope_false_refusal(wrapped, in_scope, diversify)
    latency = wrapped.latency
    print(
        f"  易例 Hit@1={easy_m['hit_at_1']:.3f} | 改写 Hit@1={hard_m['hit_at_1']:.3f} MRR={hard_m['mrr_at_10']:.3f} | "
        f"多跳 Hit@1={multi_m['hit_at_1']:.3f} MRR={multi_m['mrr_at_10']:.3f} | "
        f"近域 held-out 拒答={held['reject_rate']} | 误拒={false_m['false_refuse']} | "
        f"时延 mean={latency['mean_ms']:.0f}ms",
        flush=True,
    )
    return {
        "easy": drop_details(easy_m),
        "hard": drop_details(hard_m),
        "multihop": drop_details(multi_m),
        "job": drop_details(job_m),
        "refusal_heldout": drop_details(held),
        "refusal_dev": drop_details(dev_m),
        "refusal_far": drop_details(far_m),
        "false_refuse": drop_details(false_m),
        "latency": latency,
        "details": {
            "easy": easy_m["details"],
            "hard": hard_m["details"],
            "multihop": multi_m["details"],
            "job": job_m["details"],
            "refusal_heldout": held["details"],
            "refusal_dev": dev_m["details"],
            "refusal_far": far_m["details"],
            "false_refuse": false_m["details"],
        },
    }


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="RAG v3 评测：范围门槛与查询改写")
    parser.add_argument("--rerank", action="store_true", help="额外评测政策重排（默认线上关闭）")
    parser.add_argument("--report-only", action="store_true", help="读取已有 rag_eval_v3.json 只重写报告和图")
    args = parser.parse_args()

    if args.report_only:
        payload = json.loads((RESULTS / "rag_eval_v3.json").read_text(encoding="utf-8"))
        chart = write_chart(payload)
        write_report(payload, chart)
        print("完成", flush=True)
        return

    easy = check(QUESTIONS_PATH)
    v2 = load_v2_questions()
    hard = [row for row in v2 if row.get("set") == "hard"]
    multi = [row for row in v2 if row.get("set") == "multihop"]
    jobs_q = [row for row in v2 if row.get("set") == "job"]
    route_q = [row for row in v2 if row.get("set") == "routing"]
    heldout_v2 = [row for row in v2 if row.get("set") == "refusal"]
    scope_q = load_scope_questions()
    dev = [row for row in scope_q if row.get("split") == "dev"]
    heldout = [row for row in scope_q if row.get("split") == "heldout"] or heldout_v2
    far = [row for row in easy if not (row.get("gold") or [])]
    in_scope = [row for row in easy if row.get("gold")] + hard + multi + jobs_q

    print("加载在招职位", flush=True)
    all_rows = fetch_job_rows(None)
    print(f"在招 {len(all_rows)}", flush=True)
    print("预热嵌入模型", flush=True)
    embed_query("预热")

    routing = evaluate_routing(route_q)
    print(f"路由准确率 {routing['accuracy']:.3f}（{routing['n']} 题，本轮未改路由）", flush=True)

    print("== 构建语料 improved（与 v2 改善后全量相同）", flush=True)
    k_chunks, gold_spans = knowledge_chunks(True)
    j_chunks = job_chunks(all_rows, True)
    chunks = k_chunks + j_chunks
    print(f"  切片 {len(chunks)}（知识库 {len(k_chunks)}，职位 {len(j_chunks)}）", flush=True)
    vectors = embed_vectors_cached(chunks, "improved_full")
    index = MemoryIndex("v3_improved", chunks, vectors)
    run_pipeline.gold_spans = gold_spans

    print("== 对照：无门槛、无改写（复现 v2 改善后全量）", flush=True)
    baseline = run_pipeline(
        index, easy, hard, multi, jobs_q, far, heldout, dev, in_scope,
        rewrite=False, scope=False, rerank=False,
    )
    print("== v3：范围门槛 + 规则改写", flush=True)
    improved = run_pipeline(
        index, easy, hard, multi, jobs_q, far, heldout, dev, in_scope,
        rewrite=True, scope=True, rerank=False,
    )

    rerank_m = {}
    if args.rerank:
        print("== 附录：范围门槛 + 规则改写 + 政策重排", flush=True)
        rerank_m = run_pipeline(
            index, easy, hard, multi, jobs_q, far, heldout, dev, in_scope,
            rewrite=True, scope=True, rerank=True,
        )

    index.close()

    payload = {
        "env": env_info(),
        "corpus": {
            "improved": {
                "jobs": len(all_rows),
                "knowledge": len(k_chunks),
                "job_chunks": len(j_chunks),
                "total": len(chunks),
            }
        },
        "pipelines": {
            "baseline": baseline,
            "improved": improved,
            **({"rerank": rerank_m} if rerank_m else {}),
        },
        "routing": {k: v for k, v in routing.items() if k != "details"},
        "notes": (
            "语料与 v2 改善后全量相同。baseline=无范围门槛、无改写；"
            "improved=范围门槛+规则改写+加权RRF（线上默认，LLM 改写关闭，政策重排关闭）。"
            "近域门槛在知识库 74 切片的 dev 集上标定，本报告在全量语料的 held-out 上报告。"
        ),
    }
    save_json("rag_eval_v3.json", payload)
    chart = write_chart(payload)
    write_report(payload, chart)
    print("完成", flush=True)


if __name__ == "__main__":
    main()
