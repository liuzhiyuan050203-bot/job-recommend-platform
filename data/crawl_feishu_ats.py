#!/usr/bin/env python3
"""第 3 步外部扩充：抓取飞书招聘（ATSx，*.jobs.feishu.cn）企业官网的公开职位列表。

合规约束（与 data/REAL_DATA.md 一致）：
  * 只访问企业公开招聘门户本身用到的公开接口：先取门户 CSRF token（与浏览器打开页面相同），再分页调用职位检索；
    不登录、不带任何账号 Cookie、不破解签名/加密；接口要求签名或返回加密数据时立即停止该源并记录。
  * 每次请求间隔 ≥ 1.2s；每家公司最多 --per-company 条；robots.txt（jobs.feishu.cn 返回 404，即无限制）照常检查。
  * Moka（app.mokahr.com）的职位接口返回 AES 加密的 data 字段，解密属于绕过前端保护，已放弃该源（见 REPORT）。
输出：data/raw/ats_feishu_<YYYYMMDD>/<company>.jsonl 与 summary.json

  .venv/bin/python data/crawl_feishu_ats.py --per-company 300
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (X11; Linux x86_64) job-recommend-platform/1.0 (graduation-project research; public job listings only)"
INTERVAL = 1.2

# (company_key, 中文名, 子域名, 门户路径, 公司档位说明)。门户路径即页面 URL 第一段（campus / index / 数字站点 id）。
TENANTS = [
    ("nio", "蔚来", "nio", "campus"),
    ("xpeng", "小鹏集团", "xiaopeng", "campus"),
    ("thundersoft", "中科创达", "thundersoft", "campus"),
    ("hesai", "禾赛科技", "kwh0jtf778", "229043"),
    ("sensetime", "商汤科技", "sensetime", "edu"),
    ("minimax", "MiniMax", "vrfi1sk8a0", "379481"),
    ("desaysv", "德赛西威", "yesv-desaysv", "campus"),
    ("insta360", "影石创新", "arashivision", "campus"),
    ("dcar", "懂车帝", "dcar", "index"),
    ("kargobot", "卡尔动力", "kargobot", "267069"),
    ("intchains", "芯动科技(intchains)", "intchains", "749649"),
    ("dexteleop", "灵御智能", "dexteleop", "index"),
]


class Stop(Exception):
    pass


def polite(session: requests.Session, method: str, url: str, **kw):
    time.sleep(INTERVAL)
    r = session.request(method, url, timeout=25, **kw)
    if r.status_code in (401, 403, 429):
        raise Stop(f"HTTP {r.status_code}")
    r.raise_for_status()
    data = r.json()
    if isinstance(data.get("data"), str):
        raise Stop("响应 data 为加密字符串")
    return data


def crawl_tenant(key, label, sub, path, per_company):
    base = f"https://{sub}.jobs.feishu.cn"
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"})
    ref = f"{base}/{path}/"
    polite(s, "POST", f"{base}/api/v1/csrf/token", json={"portal_entrance": 1}, headers={"Referer": ref})
    token = urllib.parse.unquote(s.cookies.get("atsx-csrf-token", ""))
    if not token:
        raise Stop("未拿到门户 CSRF token")
    hdr = {"x-csrf-token": token, "Referer": f"{ref}position", "website-path": path}
    out, offset, total, ptype = [], 0, None, None
    for candidate in (None, 3, 2, 1, 6):  # 不同门户 portal_type 不同：先不传，再试常见值
        body = {"keyword": "", "limit": 1, "offset": 0, "job_category_id_list": [], "location_code_list": [],
                "subject_id_list": [], "recruitment_id_list": [], "job_function_id_list": [], "portal_entrance": 1}
        if candidate is not None:
            body["portal_type"] = candidate
        d = polite(s, "POST", f"{base}/api/v1/search/job/posts", json=body, headers=hdr)
        if d.get("code") == 0 and (d["data"].get("count") or 0) > 0:
            ptype, total = candidate, d["data"]["count"]
            break
    if total is None:
        raise Stop("检索接口无数据（portal_type 均为 0 条）")
    while offset < min(total, per_company):
        body = {"keyword": "", "limit": 50, "offset": offset, "job_category_id_list": [], "location_code_list": [],
                "subject_id_list": [], "recruitment_id_list": [], "job_function_id_list": [], "portal_entrance": 1}
        if ptype is not None:
            body["portal_type"] = ptype
        d = polite(s, "POST", f"{base}/api/v1/search/job/posts", json=body, headers=hdr)
        posts = d.get("data", {}).get("job_post_list") or []
        if not posts:
            break
        for p in posts:
            cities = [c.get("name") for c in (p.get("city_list") or []) if c.get("name")]
            if not cities and p.get("city_info"):
                cities = [p["city_info"].get("name")]
            rt = p.get("recruit_type") or {}
            out.append({
                "company_key": key, "company_label": label, "source": f"{sub}.jobs.feishu.cn",
                "post_id": p.get("id"), "title": (p.get("title") or "").strip(),
                "description": p.get("description") or "", "requirement": p.get("requirement") or "",
                "job_function": ((p.get("job_function") or {}).get("name")) or "",
                "job_category": ((p.get("job_category") or {}).get("name")) or "",
                "recruit_type": rt.get("name") or "", "recruit_parent": ((rt.get("parent") or {}).get("name")) or "",
                "cities": [c for c in cities if c], "publish_time": p.get("publish_time"),
                "apply_url": f"{base}/{path}/position/{p.get('id')}/detail",
                # 飞书门户的职位对象不含薪资字段；这里显式记录，供后续统计「带真实薪资」条数
                "salary": p.get("salary") or p.get("min_salary") or None,
                "crawled_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            })
        offset += len(posts)
    return out, total, ptype


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-company", type=int, default=300)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    day = datetime.now().strftime("%Y%m%d")
    outdir = ROOT / "raw" / f"ats_feishu_{day}"
    outdir.mkdir(parents=True, exist_ok=True)
    summary = {"started_at": datetime.now().astimezone().isoformat(timespec="seconds"), "interval_s": INTERVAL,
               "per_company": args.per_company, "companies": {}, "skipped": {}}
    only = {x for x in args.only.split(",") if x}
    for key, label, sub, path in TENANTS:
        if only and key not in only:
            continue
        try:
            rows, total, ptype = crawl_tenant(key, label, sub, path, args.per_company)
        except (Stop, requests.RequestException, ValueError, KeyError) as exc:
            summary["skipped"][key] = f"{label}: {type(exc).__name__}: {exc}"[:300]
            print("跳过", key, summary["skipped"][key], flush=True)
            continue
        with open(outdir / f"{key}.jsonl", "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        with_salary = sum(1 for r in rows if r["salary"])
        summary["companies"][key] = {"label": label, "domain": f"{sub}.jobs.feishu.cn", "portal": path,
                                     "portal_type": ptype, "total_listed": total, "fetched": len(rows),
                                     "with_salary": with_salary}
        print(f"{key:<12} {label:<10} 门户共 {total} 条，抓取 {len(rows)}，带薪资 {with_salary}", flush=True)
    summary["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("输出", outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
