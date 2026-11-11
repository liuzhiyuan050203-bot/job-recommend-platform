#!/usr/bin/env python3
"""把飞书招聘公开门户抓到的职位（data/crawl_feishu_ats.py 输出）导入为「外部扩充库」。

  .venv/bin/python data/import_ats_jobs.py --input data/raw/ats_feishu_YYYYMMDD            # 预览，不写库
  .venv/bin/python data/import_ats_jobs.py --input data/raw/ats_feishu_YYYYMMDD --apply    # 写库

约定（与自爬核心库 real_* 区分开）：
  * sys_user.username = ext_<company_key>（密码 Real@123，同 real_* 账号），ent_company.credit_code = EXTA + 12 位
  * job_position.data_source = 'ext_ats'（需先执行 db/migrations/phase7_job_data_source.sql），前台检索排在核心库之后
  * 只保留 IT / 互联网技术类岗位：职位名按 prepare_real_salary.direction_of 能归入平台方向，且不是销售/制造/职能类
  * 飞书门户不返回薪资：salary_min/max 按 import_real_jobs.estimate_salary 估算，描述里带「薪资为平台按方向与城市估算」，
    详情页据此标注「估算薪资」；**这些估算薪资不进入任何薪资模型训练或评测**
  * 岗位职责 / 任职要求保存官网原文，requirement 为 JSON：{"provenance": {...}, "requirements": "原文"}
  * 幂等：先删除 EXTA* 企业及其职位（含标签、收藏、行为等子表），再重新插入；不动 real_* / demo_* / 种子数据
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pymysql

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "experiments" / "salary"))
from import_real_jobs import (CITY_PROVINCE, db_config, ensure_categories, estimate_salary, fetch_maps,  # noqa: E402
                              password_hash)
from prepare_real_salary import direction_of  # noqa: E402

USER_PREFIX = "ext_"
CREDIT_PREFIX = "EXTA"
NON_TECH = re.compile(r"顾问|销售|制造|机械|工艺|质量|供应链|采购|财务|法务|人力|HR|行政|市场|商务|运营|生产|装配|门店|"
                      r"交付|客服|客户|物流|仓储|品牌|公关|编辑|招聘|培训师|司机|技师|维修|焊接|涂装|总装")
COMPANY_META = {  # 行业 / 规模档位(1-7, 与 ent_company.scale 口径一致) / 总部城市
    "nio": ("新能源汽车", 6, "上海"), "xpeng": ("新能源汽车", 6, "广州"), "thundersoft": ("计算机软件", 6, "北京"),
    "hesai": ("智能硬件", 5, "上海"), "sensetime": ("人工智能", 6, "上海"), "minimax": ("人工智能", 4, "上海"),
    "desaysv": ("汽车电子", 6, "惠州"), "insta360": ("智能硬件", 5, "深圳"), "dcar": ("互联网", 5, "北京"),
    "kargobot": ("自动驾驶", 3, "北京"), "intchains": ("芯片", 3, "上海"), "dexteleop": ("机器人", 2, "北京"),
}


def credit_code_for(key: str) -> str:
    return CREDIT_PREFIX + hashlib.md5(key.encode()).hexdigest()[:12].upper()


def city_of(cities: list[str], fallback: str) -> tuple[str, str]:
    for c in cities or []:
        c = str(c).replace("市", "").strip()
        if c in CITY_PROVINCE:
            return CITY_PROVINCE[c], c
    return CITY_PROVINCE.get(fallback, "北京"), fallback


def keep(job: dict) -> str | None:
    title = job.get("title") or ""
    if not title or NON_TECH.search(title) or NON_TECH.search(job.get("job_function") or ""):
        return None
    d = direction_of(title)
    return None if d == "其他" else d


def load(input_dir: Path) -> list[dict]:
    rows = []
    for f in sorted(input_dir.glob("*.jsonl")):
        rows += [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    return rows


def delete_ext(cur) -> dict:
    cur.execute("SELECT id FROM ent_company WHERE credit_code LIKE %s", (CREDIT_PREFIX + "%",))
    cids = [r[0] for r in cur.fetchall()]
    counts = {}
    if cids:
        fmt = ",".join(["%s"] * len(cids))
        cur.execute(f"SELECT id FROM job_position WHERE company_id IN ({fmt})", cids)
        pids = [r[0] for r in cur.fetchall()]
        for i in range(0, len(pids), 500):
            chunk = pids[i:i + 500]
            f2 = ",".join(["%s"] * len(chunk))
            cur.execute(f"SELECT id FROM job_application WHERE position_id IN ({f2})", chunk)
            aids = [r[0] for r in cur.fetchall()]
            if aids:
                f3 = ",".join(["%s"] * len(aids))
                for t in ("job_interview", "job_application_log"):
                    cur.execute(f"DELETE FROM {t} WHERE application_id IN ({f3})", aids)
                cur.execute(f"DELETE FROM job_application WHERE id IN ({f3})", aids)
            for t, col in (("spark_recommend", "position_id"), ("job_position_tag", "position_id"),
                           ("job_favorite", "position_id")):
                cur.execute(f"DELETE FROM {t} WHERE {col} IN ({f2})", chunk)
                counts[t] = counts.get(t, 0) + cur.rowcount
            cur.execute(f"DELETE FROM user_behavior_log WHERE target_type=1 AND target_id IN ({f2})", chunk)
            cur.execute(f"DELETE FROM job_position WHERE id IN ({f2})", chunk)
            counts["job_position"] = counts.get("job_position", 0) + cur.rowcount
        cur.execute(f"SELECT user_id FROM ent_company WHERE id IN ({fmt})", cids)
        uids = [r[0] for r in cur.fetchall()]
        cur.execute(f"DELETE FROM ent_company WHERE id IN ({fmt})", cids)
        counts["ent_company"] = cur.rowcount
        if uids:
            f4 = ",".join(["%s"] * len(uids))
            cur.execute(f"DELETE FROM sys_user WHERE id IN ({f4}) AND username LIKE %s", (*uids, USER_PREFIX + "%"))
            counts["sys_user"] = cur.rowcount
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--seed", type=int, default=20261111)
    args = ap.parse_args()
    rows = load(args.input)
    kept, by_co, seen = [], {}, set()
    for r in rows:
        d = keep(r)
        if d and (r["company_key"], r["post_id"]) not in seen:
            seen.add((r["company_key"], r["post_id"]))
            kept.append((r, d))
            by_co[r["company_key"]] = by_co.get(r["company_key"], 0) + 1
    print(f"读取 {len(rows)} 条，保留 IT/技术岗 {len(kept)} 条：{by_co}")
    if not args.apply:
        for r, d in kept[:8]:
            print("  ", r["company_label"], "|", r["title"], "|", d)
        print("预览模式，未写库（加 --apply 写入）")
        return 0
    rng = random.Random(args.seed)
    conn = pymysql.connect(**db_config())
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                        "AND TABLE_NAME='job_position' AND COLUMN_NAME='data_source'")
            if cur.fetchone()[0] == 0:
                print("缺少 job_position.data_source，请先执行 db/migrations/phase7_job_data_source.sql", file=sys.stderr)
                return 2
            print("清理旧的外部扩充数据:", delete_ext(cur))
            cat, skill_by_name, skill_dir, admin_id = fetch_maps(cur)
            cat = ensure_categories(cur, cat)
            from retag_real_jobs import new_tags
            tags_by_dir: dict[str, list[int]] = {}
            for name, tid in sorted(skill_by_name.items(), key=lambda x: x[1]):
                tags_by_dir.setdefault(skill_dir.get(name, ""), []).append(tid)
            pw = password_hash()
            company_ids, stats = {}, {"jobs": 0, "tags": 0}
            # 外部扩充职位的发布时间统一放在核心库之前（更旧），默认「最新」排序下也不会压过核心库
            cur.execute("SELECT MIN(publish_time) FROM job_position WHERE deleted=0 AND publish_time IS NOT NULL")
            oldest = cur.fetchone()[0] or datetime.now()
            for r, direction in kept:
                key = r["company_key"]
                industry, scale, hq = COMPANY_META.get(key, ("互联网", 4, "北京"))
                if key not in company_ids:
                    created = oldest - timedelta(days=30)
                    cur.execute(
                        """INSERT INTO sys_user (username, password, role, nickname, phone, email, avatar, status,
                           audit_remark, audit_time, auditor_id, last_login_time, create_time, update_time, deleted)
                           VALUES (%s,%s,2,%s,NULL,%s,NULL,1,'外部扩充企业账号（飞书招聘公开门户）',%s,%s,NULL,%s,%s,0)""",
                        (USER_PREFIX + key, pw, f"{r['company_label']}招聘", f"hr@{key}.ext.local", created, admin_id,
                         created, created))
                    uid = cur.lastrowid
                    cur.execute(
                        """INSERT INTO ent_company (user_id, company_name, short_name, logo_url, industry, scale, province,
                           city, address, website, intro, credit_code, license_url, contact_name, contact_phone,
                           contact_email, audit_status, audit_remark, audit_time, auditor_id, create_time, update_time,
                           deleted) VALUES (%s,%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,NULL,%s,1,
                           '外部扩充：飞书招聘公开门户同步',%s,%s,%s,%s,0)""",
                        (uid, r["company_label"], r["company_label"], industry, scale, CITY_PROVINCE.get(hq, "北京"), hq,
                         f"{hq}（详见官网）", "https://" + r["source"],
                         f"{r['company_label']}职位来自其飞书招聘公开门户，投递请以官网为准。", credit_code_for(key),
                         f"{r['company_label']}HR", f"hr@{key}.ext.local", created, admin_id, created, created))
                    company_ids[key] = cur.lastrowid
                province, city = city_of(r.get("cities"), hq)
                smin, smax, months = estimate_salary(direction, city)
                text = f"{r['title']} {r.get('recruit_type', '')} {r.get('recruit_parent', '')}"
                job_type = 2 if re.search(r"实习|intern", text, re.I) else 3 if re.search(r"校招|校园|应届", text) else 1
                edu = 3 if re.search(r"硕士|研究生", r.get("requirement") or "") and not re.search(r"本科", r.get("requirement") or "") else 2
                pub = oldest - timedelta(hours=rng.randint(1, 24 * 7))
                desc = (f"【校招官网投递】{r['apply_url']}\n【来源】{r['source']} / {r['company_label']} / post_id={r['post_id']}\n"
                        f"【工作城市】{'、'.join(r.get('cities') or []) or city}\n【抓取时间】{r['crawled_at']}\n\n"
                        f"{(r.get('description') or '').strip()}\n\n"
                        f"本条记录由飞书招聘公开门户同步（外部扩充库），薪资为平台按方向与城市估算，实际以官网为准。")
                req = json.dumps({"provenance": {"company_key": key, "company_label": r["company_label"],
                                                 "source": r["source"], "post_id": r["post_id"],
                                                 "apply_url": r["apply_url"], "crawled_at": r["crawled_at"],
                                                 "recruit_label": r.get("recruit_type"), "project": r.get("job_function"),
                                                 "work_cities": "、".join(r.get("cities") or []),
                                                 "data_source": "ext_ats", "salary_estimated": True},
                                  "requirements": (r.get("requirement") or "").strip()}, ensure_ascii=False)
                cur.execute(
                    """INSERT INTO job_position (company_id, category_id, title, tech_direction, province, city, district,
                       address, salary_min, salary_max, salary_months, education, experience_req, job_type, headcount,
                       description, requirement, welfare, data_source, shelf_status, audit_status, audit_remark,
                       audit_time, auditor_id, publish_time, view_count, favorite_count, apply_count, create_time,
                       update_time, deleted)
                       VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s,'ext_ats',1,1,'外部扩充同步',%s,%s,%s,
                       0,0,0,%s,%s,0)""",
                    (company_ids[key], cat.get(direction) or cat.get("后端开发"), r["title"][:128], direction, province,
                     city, f"{city}（详见官网）", smin, smax, months, edu, 1 if job_type != 1 else 3, job_type, desc,
                     req, f"投递链接: {r['apply_url']}"[:500], pub, admin_id, pub, pub, pub))
                pid = cur.lastrowid
                for tid in new_tags(r["title"], direction, skill_by_name, tags_by_dir):
                    cur.execute("INSERT INTO job_position_tag (position_id, tag_id, create_time, update_time, deleted) "
                                "VALUES (%s,%s,%s,%s,0)", (pid, tid, pub, pub))
                    stats["tags"] += 1
                stats["jobs"] += 1
            conn.commit()
            cur.execute("SELECT data_source, COUNT(*) FROM job_position WHERE deleted=0 GROUP BY data_source")
            dist = dict(cur.fetchall())
        summary = {"imported_jobs": stats["jobs"], "tags": stats["tags"], "by_company": by_co,
                   "data_source_counts": dist, "imported_at": datetime.now().astimezone().isoformat(timespec="seconds")}
        (args.input / "import_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
