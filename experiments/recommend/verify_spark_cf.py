"""Spark 用户余弦协同过滤与 numpy 参考实现的数值等价性校验（一条命令复现）。

    .venv/bin/python experiments/recommend/verify_spark_cf.py

步骤：同一进程、同一份库数据上
1. 运行 numpy_reference.reference_run（d8dc465 版生产算法，不写库）；
2. 通过 runner.run_blocking(["recommend"]) 跑一次真实的 Spark 生产推荐任务（写 spark_recommend /
   spark_user_neighbor / spark_recommend_eval，与管理端触发相同）；
3. 读回本批次结果对比：邻居相似度最大绝对差、邻居集合一致率、各算法 Top-10/Top-20 列表重合率、
   匹配分最大差、留出集 NDCG@10。结果写入 experiments/results/recommend_spark_equivalence.json。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import env_info, save_json  # noqa: E402

import numpy_reference as NR  # noqa: E402
from app.spark import db  # noqa: E402
from app.spark.paths import RECOMMEND_EVAL_PATH  # noqa: E402
from app.spark.runner import run_blocking  # noqa: E402
from app.spark.session import get_spark  # noqa: E402


def _ndcg(rows, k=10):
    return next(float(r["ndcg"]) for r in rows if int(r["k"]) == k)


def main() -> None:
    spark = get_spark()
    t0 = time.perf_counter()
    ref = NR.reference_run(spark)
    numpy_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    result = run_blocking(["recommend"])
    spark_job_seconds = time.perf_counter() - t0
    batch_no = result.get("batchNo")
    task = result["tasks"][0]
    if task.get("status") != 1:
        raise SystemExit(f"Spark 推荐任务失败: {task.get('errorMsg')}")
    import json

    payload = json.loads(RECOMMEND_EVAL_PATH.read_text(encoding="utf-8"))
    assert payload["batchNo"] == batch_no, (payload["batchNo"], batch_no)

    conn = db.connect()
    with conn.cursor() as cur:
        cur.execute("SELECT user_id, neighbor_id, similarity FROM spark_user_neighbor WHERE batch_no=%s", (batch_no,))
        neighbor_rows = cur.fetchall()
        cur.execute(
            "SELECT user_id, position_id, algo, match_score, rank_no FROM spark_recommend WHERE batch_no=%s ORDER BY algo, user_id, rank_no",
            (batch_no,),
        )
        rec_rows = cur.fetchall()
    conn.close()

    # 1) 邻居相似度
    user_index = {u: i for i, u in enumerate(ref["user_ids"])}
    sim_ref = ref["sim_full"]
    sim_spark = np.zeros_like(sim_ref)
    for row in neighbor_rows:
        sim_spark[user_index[int(row["user_id"])], user_index[int(row["neighbor_id"])]] = float(row["similarity"])
    sim_diff = float(np.max(np.abs(sim_spark - sim_ref))) if sim_ref.size else 0.0
    ref_pairs = set(zip(*np.nonzero(sim_ref > 0)))
    spark_pairs = set(zip(*np.nonzero(sim_spark > 0)))
    jaccard = len(ref_pairs & spark_pairs) / max(1, len(ref_pairs | spark_pairs))
    # 不一致的邻居对是否都落在第 40 名的并列边界上（argpartition 与 row_number 的并列取舍不同）
    unmasked = NR.cosine_similarity_matrix(ref["full_ratings"], neighbors=0)
    mismatched = sorted(ref_pairs ^ spark_pairs)
    tie_flags = []
    for u, v in mismatched:
        row = np.sort(unmasked[u])[::-1]
        kth = row[min(NR.NEIGHBORS, len(row)) - 1]
        tie_flags.append(bool(abs(unmasked[u, v] - kth) <= 1e-12))
    common = np.zeros_like(sim_ref, dtype=bool)
    for u, v in ref_pairs & spark_pairs:
        common[u, v] = True
    common_diff = float(np.max(np.abs(sim_spark[common] - sim_ref[common]))) if common.any() else 0.0

    # 2) Top-N 列表
    spark_lists: dict[tuple[int, int], list[tuple[int, float]]] = {}
    for row in rec_rows:
        spark_lists.setdefault((int(row["algo"]), int(row["user_id"])), []).append((int(row["position_id"]), float(row["match_score"])))
    list_stats = {}
    for algo, name in ((1, "cf"), (2, "content"), (3, "hybrid")):
        keys = [key for key in ref["lists"] if key[0] == algo]
        ov10, ov20, exact10, score_diff = [], [], 0, 0.0
        for key in keys:
            a = ref["lists"][key]
            b = spark_lists.get(key, [])
            a10 = [p for p, _ in a[:10]]
            b10 = [p for p, _ in b[:10]]
            ov10.append(len(set(a10) & set(b10)) / max(1, len(a10)))
            ov20.append(len({p for p, _ in a} & {p for p, _ in b}) / max(1, len(a)))
            exact10 += int(a10 == b10)
            ref_scores = dict(a)
            for pid, score in b:
                if pid in ref_scores:
                    score_diff = max(score_diff, abs(round(ref_scores[pid] + 1e-8, 2) - score))
        list_stats[name] = {
            "users": len(keys),
            "top10_overlap_mean": round(float(np.mean(ov10)), 6) if ov10 else None,
            "top10_overlap_min": round(float(np.min(ov10)), 6) if ov10 else None,
            "top10_identical_order_users": exact10,
            "top20_overlap_mean": round(float(np.mean(ov20)), 6) if ov20 else None,
            "max_abs_match_score_diff_on_common_items": round(score_diff, 4),
        }

    spark_metrics = {(m["algo"], m["k"]): m for m in payload["metrics"]}
    ndcg = {
        "numpy": {
            "cosine": round(_ndcg(ref["cosine_rows"]), 4),
            "hybrid": round(_ndcg(ref["hybrid_rows"]), 4),
            "content": round(_ndcg(ref["content_rows"]), 4),
            "popular": round(_ndcg(ref["popular_rows"]), 4),
            "best": {k: ref["best"][k] for k in ("alpha", "fusion", "adaptive")},
        },
        "spark": {
            "cosine": payload["cosineNdcg10"],
            "hybrid": payload["hybridNdcg10"],
            "content": spark_metrics[("content", 10)]["ndcg"],
            "popular": spark_metrics[("popular", 10)]["ndcg"],
            "best": {"alpha": payload["alpha"], "fusion": payload["fusion"], "adaptive": payload["adaptiveAlpha"]},
        },
    }
    out = {
        "batchNo": batch_no,
        "users": len(ref["user_ids"]),
        "items": len(ref["item_ids"]),
        "ratingNonZero": int(np.count_nonzero(ref["full_ratings"])),
        "holdoutUsers": {"numpy": ref["holdout_users"], "spark": payload["holdoutUsers"]},
        "similarity": {
            "neighbor_rows_spark": len(neighbor_rows),
            "neighbor_pairs_numpy": len(ref_pairs),
            "neighbor_set_jaccard": round(jaccard, 6),
            "max_abs_diff": sim_diff,
            "max_abs_diff_on_common_pairs": common_diff,
            "mismatched_pairs": len(mismatched),
            "mismatched_pairs_all_rank40_ties": all(tie_flags) if tie_flags else None,
        },
        "lists": list_stats,
        "ndcg10": ndcg,
        "timing_seconds": {
            "numpy_reference_total_incl_load": round(numpy_seconds, 3),
            "numpy_cosine_predict": {k: round(v, 4) for k, v in ref["numpy_cosine_seconds"].items()},
            "spark_job_total": round(spark_job_seconds, 3),
            "spark_stage_seconds": payload.get("stageSeconds"),
        },
        "env": env_info(),
    }
    save_json("recommend_spark_equivalence.json", out)
    print(json.dumps({k: v for k, v in out.items() if k != "env"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
