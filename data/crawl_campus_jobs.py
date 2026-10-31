#!/usr/bin/env python3
"""Crawl real campus jobs via @ha7ch/job-pro public company APIs.

Writes JSONL under data/raw/campus_YYYYMMDD/ plus a summary JSON.
Rate limit ≥1s between calls. Cap per company and overall.
Skips failing companies and continues.

Usage:
  /workspace/bishe/.venv/bin/python data/crawl_campus_jobs.py
  /workspace/bishe/.venv/bin/python data/crawl_campus_jobs.py --max-total 2000 --page-size 50
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.job_pro_client import JobProClient, JobProError  # noqa: E402

TZ = ZoneInfo("Asia/Shanghai")

# Prefer Bespoke / Feishu campus portals known to return campus openings.
# Caps keep total in ~800–5000 range while covering ≥10 companies.
COMPANY_CAPS: list[tuple[str, str, int]] = [
    ("bytedance", "字节跳动", 280),
    ("tencent", "腾讯", 180),
    ("alibaba", "阿里巴巴", 180),
    ("xiaomi", "小米", 180),
    ("netease", "网易", 150),
    ("xiaohongshu", "小红书", 150),
    ("kuaishou", "快手", 150),
    ("didi", "滴滴", 180),
    ("antgroup", "蚂蚁集团", 140),
    ("bilibili", "哔哩哔哩", 120),
    ("jd", "京东", 120),
    ("baidu", "百度", 100),
    ("pdd", "拼多多", 50),
    ("oppo", "OPPO", 80),
    ("trip", "携程", 80),
    ("meituan", "美团", 100),  # may fail — skip+document
    ("huawei", "华为", 80),    # may be empty
    ("mihoyo", "米哈游", 60),
]


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Crawl campus jobs via job-pro")
    p.add_argument("--out-dir", type=Path, default=None, help="Output directory (default data/raw/campus_YYYYMMDD)")
    p.add_argument("--page-size", type=int, default=50)
    p.add_argument("--max-total", type=int, default=2200)
    p.add_argument("--min-interval", type=float, default=1.1)
    p.add_argument("--companies", type=str, default="", help="Comma-separated keys to override default list")
    p.add_argument("--keyword", type=str, default="", help="Optional search keyword (default empty = all campus)")
    p.add_argument("--scope", type=str, default="campus")
    return p.parse_args()


def company_plan(args: argparse.Namespace) -> list[tuple[str, str, int]]:
    if args.companies.strip():
        wanted = {k.strip() for k in args.companies.split(",") if k.strip()}
        plan = [(k, label, cap) for k, label, cap in COMPANY_CAPS if k in wanted]
        # allow unknown keys with default cap 100
        known = {k for k, _, _ in COMPANY_CAPS}
        for k in wanted:
            if k not in known:
                plan.append((k, k, 100))
        return plan
    return list(COMPANY_CAPS)


def normalize_position(raw: dict[str, Any], company_key: str, company_label: str, source: str) -> dict[str, Any]:
    post_id = str(raw.get("post_id") or raw.get("id") or "").strip()
    title = (raw.get("title") or "").strip()
    apply_url = (raw.get("apply_url") or raw.get("url") or "").strip()
    cities = raw.get("work_cities") or raw.get("cities") or raw.get("city") or ""
    if isinstance(cities, list):
        cities = " / ".join(str(c) for c in cities)
    return {
        "company_key": company_key,
        "company_label": company_label,
        "source": source,
        "post_id": post_id,
        "title": title,
        "project": raw.get("project") or "",
        "recruit_label": raw.get("recruit_label") or "",
        "bgs": raw.get("bgs") or "",
        "work_cities": cities,
        "apply_url": apply_url,
        "raw": raw,
        "crawled_at": now_iso(),
    }


def crawl_company(
    client: JobProClient,
    company_key: str,
    company_label: str,
    cap: int,
    *,
    page_size: int,
    keyword: str,
    scope: str,
    remaining_global: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta: dict[str, Any] = {
        "company_key": company_key,
        "company_label": company_label,
        "cap": cap,
        "ok": False,
        "total_reported": None,
        "fetched": 0,
        "pages": 0,
        "error": None,
        "skipped": False,
    }
    if remaining_global <= 0:
        meta["skipped"] = True
        meta["error"] = "global cap reached"
        return [], meta

    target = min(cap, remaining_global)
    positions: list[dict[str, Any]] = []
    seen: set[str] = set()
    page = 1
    source = ""
    try:
        while len(positions) < target:
            data = client.search(
                company_key,
                keyword,
                scope=scope,
                page=page,
                page_size=page_size,
            )
            source = data.get("source") or source
            if meta["total_reported"] is None:
                meta["total_reported"] = data.get("total")
            batch = data.get("positions") or []
            if not batch:
                break
            meta["pages"] += 1
            for raw in batch:
                item = normalize_position(raw, company_key, company_label, source or company_key)
                if not item["post_id"] or not item["title"]:
                    continue
                if item["post_id"] in seen:
                    continue
                seen.add(item["post_id"])
                positions.append(item)
                if len(positions) >= target:
                    break
            # stop if fewer than page_size returned
            if len(batch) < page_size:
                break
            # safety: if total known and we've passed it
            total = data.get("total")
            if isinstance(total, int) and page * page_size >= total:
                break
            page += 1
            if page > 80:  # hard safety
                break
        meta["ok"] = True
        meta["fetched"] = len(positions)
        meta["source"] = source
    except JobProError as exc:
        meta["error"] = str(exc)
        meta["fetched"] = len(positions)
        meta["ok"] = len(positions) > 0
        meta["source"] = source
    except Exception as exc:  # noqa: BLE001
        meta["error"] = f"{type(exc).__name__}: {exc}"
        meta["fetched"] = len(positions)
        meta["ok"] = len(positions) > 0
        meta["source"] = source
    return positions, meta


def main() -> int:
    args = parse_args()
    day = datetime.now(TZ).strftime("%Y%m%d")
    out_dir = args.out_dir or (ROOT / "data" / "raw" / f"campus_{day}")
    out_dir.mkdir(parents=True, exist_ok=True)
    client = JobProClient(min_interval=args.min_interval)
    plan = company_plan(args)

    all_rows: list[dict[str, Any]] = []
    company_metas: list[dict[str, Any]] = []
    started = now_iso()
    print(f"[crawl] start {started} out={out_dir} max_total={args.max_total} companies={len(plan)}")

    for company_key, company_label, cap in plan:
        remaining = args.max_total - len(all_rows)
        print(f"[crawl] {company_key} ({company_label}) cap={cap} remaining={remaining}")
        rows, meta = crawl_company(
            client,
            company_key,
            company_label,
            cap,
            page_size=args.page_size,
            keyword=args.keyword,
            scope=args.scope,
            remaining_global=remaining,
        )
        company_metas.append(meta)
        # per-company JSONL
        company_path = out_dir / f"{company_key}.jsonl"
        with company_path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        all_rows.extend(rows)
        status = "OK" if meta["ok"] else "SKIP/FAIL"
        print(
            f"  -> {status} fetched={meta['fetched']} pages={meta['pages']} "
            f"total_reported={meta['total_reported']} err={meta.get('error')}"
        )
        if len(all_rows) >= args.max_total:
            print("[crawl] global cap reached")
            break

    # combined JSONL + summary
    combined = out_dir / "all_jobs.jsonl"
    with combined.open("w", encoding="utf-8") as fh:
        for row in all_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    by_company = {}
    for row in all_rows:
        by_company[row["company_key"]] = by_company.get(row["company_key"], 0) + 1

    summary = {
        "started_at": started,
        "finished_at": now_iso(),
        "out_dir": str(out_dir),
        "scope": args.scope,
        "keyword": args.keyword,
        "page_size": args.page_size,
        "max_total": args.max_total,
        "total_jobs": len(all_rows),
        "companies_ok": sum(1 for m in company_metas if m.get("ok")),
        "companies_failed": [m for m in company_metas if not m.get("ok")],
        "by_company": by_company,
        "company_metas": company_metas,
        "sample": [
            {"company": r["company_label"], "title": r["title"], "apply_url": r["apply_url"]}
            for r in all_rows[:8]
        ],
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[crawl] done total={len(all_rows)} companies_ok={summary['companies_ok']} -> {combined}")
    print(json.dumps(by_company, ensure_ascii=False))
    return 0 if len(all_rows) >= 800 else (0 if len(all_rows) > 0 else 1)


if __name__ == "__main__":
    raise SystemExit(main())
