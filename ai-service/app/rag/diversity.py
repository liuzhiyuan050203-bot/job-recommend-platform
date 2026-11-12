"""检索结果去重：同一职位、同一公司在 top-k 中的切片数量上限。

「杭州 Java 后端」这类问题如果某一家公司职位很多，稠密和 BM25 会把前几条占满。
政策类切片不受公司限制。名额用完后若还凑不满 top-k，再从被跳过的切片里补。
"""

from __future__ import annotations

from typing import Any


def diversify_hits(
    hits: list[dict[str, Any]],
    top_k: int,
    per_job: int = 1,
    per_company: int = 2,
) -> list[dict[str, Any]]:
    """按排名扫描，限制每个职位、每家公司进入结果的切片数。"""
    top_k = max(1, int(top_k))
    per_job = max(0, int(per_job))
    per_company = max(0, int(per_company))
    if not hits or (per_job == 0 and per_company == 0):
        return hits[:top_k]
    kept: list[dict[str, Any]] = []
    leftover: list[dict[str, Any]] = []
    job_counts: dict[str, int] = {}
    company_counts: dict[str, int] = {}
    for hit in hits:
        if len(kept) >= top_k:
            leftover.append(hit)
            continue
        if not _is_job(hit):
            kept.append(hit)
            continue
        job_key = _job_key(hit)
        company = (hit.get("company") or "").strip()
        if per_job and job_key and job_counts.get(job_key, 0) >= per_job:
            leftover.append(hit)
            continue
        if per_company and company and company_counts.get(company, 0) >= per_company:
            leftover.append(hit)
            continue
        kept.append(hit)
        if job_key:
            job_counts[job_key] = job_counts.get(job_key, 0) + 1
        if company:
            company_counts[company] = company_counts.get(company, 0) + 1
    for hit in leftover:
        if len(kept) >= top_k:
            break
        kept.append(hit)
    return kept[:top_k]


def _is_job(hit: dict[str, Any]) -> bool:
    if int(hit.get("doc_type") or 0) == 7:
        return True
    key = str(hit.get("doc_key") or "")
    return key.startswith("job:")


def _job_key(hit: dict[str, Any]) -> str:
    key = str(hit.get("doc_key") or "").strip()
    if key:
        return key
    source_id = hit.get("source_id")
    if source_id:
        return f"job:{source_id}"
    return ""
