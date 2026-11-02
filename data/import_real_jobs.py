#!/usr/bin/env python3
"""Import crawled campus JSONL into MySQL 8.4 as real_* companies.

Creates:
  - sys_user username=real_<company_key> password=Real@123 (role=企业, status=正常)
  - ent_company credit_code=REAL<...> audit passed
  - job_position approved+on shelf, skill tags by keyword, category by direction
  - optionally appends to data/raw/jobs_raw.csv for Spark clean demo
  - optionally injects demo-student behavior logs onto real jobs for CF signal

Idempotent: removes previous real_* / REAL* rows then re-inserts.
Does not touch seed accounts (admin/student/company) or demo_* rows
unless --replace-demo-jobs is set (then deletes demo jobs/companies too).

Usage:
  /workspace/bishe/.venv/bin/python data/import_real_jobs.py --input data/raw/campus_YYYYMMDD
  /workspace/bishe/.venv/bin/python data/import_real_jobs.py --input ... --inject-behaviors --append-csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import bcrypt
import pymysql

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")

REAL_PASSWORD = "Real@123"
# Precomputed bcrypt for Real@123 (gensalt rounds=10). Verified at import time.
REAL_PASSWORD_HASH = "$2b$10$8ACWpWnSq7Jubpp/Ky05luE8ireokS7AUBB14ROL30R2BqPyO0Yea"
USER_PREFIX = "real_"
CREDIT_PREFIX = "REAL"

CITY_PROVINCE = {
    "北京": "北京", "上海": "上海", "天津": "天津", "重庆": "重庆",
    "深圳": "广东", "广州": "广东", "东莞": "广东", "佛山": "广东", "珠海": "广东",
    "杭州": "浙江", "宁波": "浙江", "南京": "江苏", "苏州": "江苏", "无锡": "江苏",
    "成都": "四川", "武汉": "湖北", "西安": "陕西", "长沙": "湖南", "合肥": "安徽",
    "厦门": "福建", "福州": "福建", "郑州": "河南", "济南": "山东", "青岛": "山东",
    "大连": "辽宁", "沈阳": "辽宁", "哈尔滨": "黑龙江", "长春": "吉林",
    "昆明": "云南", "贵阳": "贵州", "南宁": "广西", "海口": "海南",
    "石家庄": "河北", "太原": "山西", "呼和浩特": "内蒙古", "兰州": "甘肃",
    "乌鲁木齐": "新疆", "银川": "宁夏", "西宁": "青海", "拉萨": "西藏",
    "香港": "香港", "澳门": "澳门", "台北": "台湾",
}

COMPANY_META = {
    "bytedance": {"name": "字节跳动", "short": "字节", "industry": "互联网", "scale": 6, "city": "北京", "website": "https://jobs.bytedance.com"},
    "tencent": {"name": "腾讯", "short": "腾讯", "industry": "互联网", "scale": 6, "city": "深圳", "website": "https://join.qq.com"},
    "alibaba": {"name": "阿里巴巴", "short": "阿里", "industry": "互联网", "scale": 6, "city": "杭州", "website": "https://campus-talent.alibaba.com"},
    "meituan": {"name": "美团", "short": "美团", "industry": "互联网", "scale": 6, "city": "北京", "website": "https://zhaopin.meituan.com"},
    "xiaohongshu": {"name": "小红书", "short": "小红书", "industry": "互联网", "scale": 5, "city": "上海", "website": "https://job.xiaohongshu.com"},
    "jd": {"name": "京东", "short": "京东", "industry": "互联网", "scale": 6, "city": "北京", "website": "https://campus.jd.com"},
    "kuaishou": {"name": "快手", "short": "快手", "industry": "互联网", "scale": 6, "city": "北京", "website": "https://campus.kuaishou.cn"},
    "baidu": {"name": "百度", "short": "百度", "industry": "互联网", "scale": 6, "city": "北京", "website": "https://talent.baidu.com"},
    "netease": {"name": "网易", "short": "网易", "industry": "互联网", "scale": 6, "city": "杭州", "website": "https://hr.163.com"},
    "didi": {"name": "滴滴出行", "short": "滴滴", "industry": "互联网", "scale": 6, "city": "北京", "website": "https://talent.didiglobal.com"},
    "bilibili": {"name": "哔哩哔哩", "short": "B站", "industry": "互联网", "scale": 5, "city": "上海", "website": "https://jobs.bilibili.com"},
    "pdd": {"name": "拼多多", "short": "拼多多", "industry": "互联网", "scale": 6, "city": "上海", "website": "https://careers.pinduoduo.com"},
    "huawei": {"name": "华为", "short": "华为", "industry": "通信设备", "scale": 6, "city": "深圳", "website": "https://career.huawei.com"},
    "xiaomi": {"name": "小米", "short": "小米", "industry": "智能硬件", "scale": 6, "city": "北京", "website": "https://xiaomi.jobs.f.mioffice.cn"},
    "antgroup": {"name": "蚂蚁集团", "short": "蚂蚁", "industry": "金融科技", "scale": 6, "city": "杭州", "website": "https://hrcareersweb.antgroup.com"},
    "oppo": {"name": "OPPO", "short": "OPPO", "industry": "智能硬件", "scale": 6, "city": "深圳", "website": "https://careers.oppo.com"},
    "trip": {"name": "携程", "short": "携程", "industry": "互联网", "scale": 5, "city": "上海", "website": "https://careers.ctrip.com"},
    "mihoyo": {"name": "米哈游", "short": "米哈游", "industry": "游戏", "scale": 5, "city": "上海", "website": "https://jobs.mihoyo.com"},
    "nio": {"name": "蔚来", "short": "蔚来", "industry": "新能源汽车", "scale": 5, "city": "上海", "website": "https://nio.jobs.feishu.cn"},
    "vivo": {"name": "vivo", "short": "vivo", "industry": "智能硬件", "scale": 6, "city": "东莞", "website": "https://hr.vivo.com"},
}

DIRECTION_RULES: list[tuple[str, list[str]]] = [
    ("人工智能", ["大模型", "LLM", "AIGC", "机器学习", "深度学习", "NLP", "计算机视觉", "CV算法", "人工智能", "AI算法", "多模态", "生成式", "Agent"]),
    ("算法工程", ["算法工程师", "推荐算法", "搜索算法", "广告算法", "风控算法", "策略算法", "算法"]),
    ("数据开发", ["数据开发", "大数据", "数据工程", "数据仓库", "数仓", "数据分析", "数据科学", "ETL", "Hive", "Spark", "Flink"]),
    ("前端开发", ["前端", "Web前端", "FE", "React", "Vue", "TypeScript", "JavaScript", "客户端H5"]),
    ("移动开发", ["Android", "iOS", "Flutter", "鸿蒙", "移动端", "客户端开发"]),
    ("云原生开发", ["云原生", "SRE", "DevOps", "Kubernetes", "K8s", "容器", "中间件"]),
    ("运维开发", ["运维", "稳定性", "基础设施", "系统工程师"]),
    ("测试开发", ["测试开发", "质量保证", "QA", "测试工程师", "质量工程"]),
    ("嵌入式开发", ["嵌入式", "固件", "单片机", "RTOS", "芯片"]),
    ("后端开发", ["后端", "服务端", "Server", "Java", "Go", "Golang", "C\\+\\+", "后台开发", "基础架构", "研发工程师"]),
    ("产品经理", ["产品经理", "产品运营", "PM"]),
    ("UI设计", ["UI设计", "UX", "视觉设计", "交互设计", "设计师"]),
]

SKILL_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Java", ["Java", "JVM"]),
    ("Spring Boot", ["Spring Boot", "SpringBoot"]),
    ("Spring Cloud", ["Spring Cloud", "SpringCloud"]),
    ("MySQL", ["MySQL"]),
    ("Redis", ["Redis"]),
    ("Kafka", ["Kafka"]),
    ("Go", ["Golang", "Go语言", " Go ", "Go/", "/Go"]),
    ("C++", ["C++", "Cpp"]),
    ("Docker", ["Docker"]),
    ("Kubernetes", ["Kubernetes", "K8s", "k8s"]),
    ("Vue", ["Vue"]),
    ("React", ["React"]),
    ("TypeScript", ["TypeScript", "TS"]),
    ("JavaScript", ["JavaScript", "JS"]),
    ("Node.js", ["Node.js", "NodeJS", "Node"]),
    ("Python", ["Python"]),
    ("Spark", ["Spark"]),
    ("Flink", ["Flink"]),
    ("Hadoop", ["Hadoop"]),
    ("Hive", ["Hive"]),
    ("SQL", ["SQL"]),
    ("PyTorch", ["PyTorch"]),
    ("TensorFlow", ["TensorFlow"]),
    ("机器学习", ["机器学习", "Machine Learning"]),
    ("大模型", ["大模型", "LLM", "AIGC"]),
    ("LangChain", ["LangChain"]),
    ("深度学习", ["深度学习", "Deep Learning"]),
    ("推荐系统", ["推荐系统", "推荐算法"]),
    ("Android", ["Android"]),
    ("iOS", ["iOS"]),
    ("Flutter", ["Flutter"]),
    ("Linux", ["Linux"]),
    ("Shell", ["Shell"]),
]


def db_config() -> dict:
    return {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "job"),
        "password": os.environ.get("MYSQL_PASSWORD", "job123"),
        "database": os.environ.get("MYSQL_DATABASE", "job_platform"),
        "charset": "utf8mb4",
        "autocommit": False,
        "connect_timeout": 10,
        "read_timeout": 180,
        "write_timeout": 180,
    }


def password_hash() -> str:
    hashed = REAL_PASSWORD_HASH
    if not bcrypt.checkpw(REAL_PASSWORD.encode(), hashed.encode()):
        hashed = bcrypt.hashpw(REAL_PASSWORD.encode(), bcrypt.gensalt(rounds=10)).decode()
    return hashed


def now() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True, help="campus_YYYYMMDD dir or all_jobs.jsonl")
    p.add_argument("--append-csv", action="store_true", help="Append real jobs to data/raw/jobs_raw.csv")
    p.add_argument("--replace-csv", action="store_true", help="Rewrite jobs_raw.csv from DB after import")
    p.add_argument("--inject-behaviors", action="store_true", help="Add CF signal from demo/seed students to real jobs")
    p.add_argument("--replace-demo-jobs", action="store_true", help="Also delete demo_ companies/jobs before import")
    p.add_argument("--seed", type=int, default=20261101)
    return p.parse_args()


def load_jobs(path: Path) -> list[dict[str, Any]]:
    if path.is_dir():
        jsonl = path / "all_jobs.jsonl"
        if not jsonl.exists():
            # merge per-company files
            rows = []
            for f in sorted(path.glob("*.jsonl")):
                if f.name == "all_jobs.jsonl":
                    continue
                rows.extend(load_jobs(f))
            return rows
        path = jsonl
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def infer_direction(title: str, project: str = "") -> str:
    text = f"{title} {project}"
    for direction, kws in DIRECTION_RULES:
        for kw in kws:
            if re.search(kw, text, flags=re.IGNORECASE):
                return direction
    # 非研发岗位不要默认落到后端
    if re.search(r"运营|市场|销售|商务|人力|HR|招聘|财务|法务|行政|品牌|公关|客户", text, re.I):
        return "产品经理"
    if re.search(r"设计|美术|原画|UI|UX", text, re.I):
        return "UI设计"
    if re.search(r"策划|编辑|内容|直播|游戏", text, re.I):
        return "产品经理"
    return "后端开发"


def match_skills(title: str, project: str, direction: str, skill_by_name: dict[str, int]) -> list[int]:
    text = f"{title} {project}"
    found: list[int] = []
    for name, kws in SKILL_KEYWORDS:
        tid = skill_by_name.get(name)
        if not tid:
            continue
        for kw in kws:
            if re.search(re.escape(kw) if kw.isalpha() else kw, text, flags=re.IGNORECASE):
                found.append(tid)
                break
    # ensure at least one tag from direction pool
    if not found:
        for name, tid in skill_by_name.items():
            # pick first skill whose direction matches — filled later with direction map
            pass
    return list(dict.fromkeys(found))[:6]


def parse_city(work_cities: str, fallback_city: str) -> tuple[str, str]:
    raw = (work_cities or "").replace("总部", "").replace(",", " ").replace("，", " ").replace("/", " ")
    tokens = [t.strip() for t in re.split(r"[\s、|/]+", raw) if t.strip()]
    for tok in tokens:
        # normalize e.g. 深圳总部 already stripped
        city = tok.replace("市", "")
        if city in CITY_PROVINCE:
            return CITY_PROVINCE[city], city
        # partial match
        for known in CITY_PROVINCE:
            if known in city:
                return CITY_PROVINCE[known], known
    fb = fallback_city
    return CITY_PROVINCE.get(fb, "北京"), fb


def estimate_salary(direction: str, city: str) -> tuple[int, int, int]:
    base = {
        "后端开发": (15000, 25000),
        "前端开发": (14000, 23000),
        "数据开发": (16000, 27000),
        "人工智能": (18000, 32000),
        "云原生开发": (16000, 28000),
        "算法工程": (20000, 35000),
        "测试开发": (11000, 19000),
        "运维开发": (11000, 19000),
        "移动开发": (14000, 24000),
        "嵌入式开发": (12000, 21000),
        "产品经理": (13000, 23000),
        "UI设计": (10000, 18000),
    }.get(direction, (14000, 24000))
    factor = 1.0 if city in {"北京", "上海", "深圳", "广州"} else 0.85 if city in {"杭州", "南京", "苏州", "成都", "武汉"} else 0.75
    low = int(round(base[0] * factor / 500.0) * 500)
    high = int(round(base[1] * factor / 500.0) * 500)
    return low, max(low + 2000, high), 12


def credit_code_for(company_key: str) -> str:
    digest = hashlib.md5(company_key.encode()).hexdigest()[:12].upper()
    return f"{CREDIT_PREFIX}{digest}"  # REAL + 12 = 16 chars


def delete_real_data(cur, replace_demo: bool = False) -> dict[str, int]:
    counts: dict[str, int] = {}

    def add(name: str, n: int) -> None:
        counts[name] = counts.get(name, 0) + n

    cur.execute("SELECT id FROM sys_user WHERE username LIKE %s AND deleted=0", (USER_PREFIX + "%",))
    real_user_ids = [r[0] for r in cur.fetchall()]
    if replace_demo:
        cur.execute("SELECT id FROM sys_user WHERE username REGEXP %s AND deleted=0", (r"^demo_(corp|stu)_[0-9]+$",))
        real_user_ids.extend(r[0] for r in cur.fetchall())

    if not real_user_ids and not replace_demo:
        return counts

    # company ids
    company_ids: list[int] = []
    if real_user_ids:
        fmt = ",".join(["%s"] * len(real_user_ids))
        cur.execute(f"SELECT id FROM ent_company WHERE user_id IN ({fmt})", real_user_ids)
        company_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id FROM ent_company WHERE credit_code LIKE %s", (CREDIT_PREFIX + "%",))
    for (cid,) in cur.fetchall():
        if cid not in company_ids:
            company_ids.append(cid)
    if replace_demo:
        cur.execute("SELECT id FROM ent_company WHERE credit_code REGEXP %s", (r"^DEMO[0-9]+$",))
        for (cid,) in cur.fetchall():
            if cid not in company_ids:
                company_ids.append(cid)

    position_ids: list[int] = []
    if company_ids:
        fmt = ",".join(["%s"] * len(company_ids))
        cur.execute(f"SELECT id FROM job_position WHERE company_id IN ({fmt})", company_ids)
        position_ids = [r[0] for r in cur.fetchall()]

    def delete_in(table: str, col: str, ids: list[int]) -> int:
        if not ids:
            return 0
        total = 0
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            fmt = ",".join(["%s"] * len(chunk))
            cur.execute(f"DELETE FROM {table} WHERE {col} IN ({fmt})", chunk)
            total += cur.rowcount
        return total

    # child tables first
    if position_ids:
        add("spark_recommend", delete_in("spark_recommend", "position_id", position_ids))
        # behavior targeting these positions (target_type=1 职位)
        if position_ids:
            total_b = 0
            for i in range(0, len(position_ids), 500):
                chunk = position_ids[i:i + 500]
                fmt = ",".join(["%s"] * len(chunk))
                cur.execute(
                    f"DELETE FROM user_behavior_log WHERE target_type=1 AND target_id IN ({fmt})",
                    chunk,
                )
                total_b += cur.rowcount
            add("user_behavior_log", total_b)
        add("job_position_tag", delete_in("job_position_tag", "position_id", position_ids))
        add("job_favorite", delete_in("job_favorite", "position_id", position_ids))
        # applications + logs + interviews
        fmt = ",".join(["%s"] * len(position_ids))
        cur.execute(f"SELECT id FROM job_application WHERE position_id IN ({fmt})", position_ids)
        app_ids = [r[0] for r in cur.fetchall()]
        if app_ids:
            add("job_interview", delete_in("job_interview", "application_id", app_ids))
            add("job_application_log", delete_in("job_application_log", "application_id", app_ids))
            add("job_application", delete_in("job_application", "id", app_ids))
        add("job_position", delete_in("job_position", "id", position_ids))

    if company_ids:
        add("ent_company", delete_in("ent_company", "id", company_ids))

    # null auditor refs then delete users — only real_/demo_corp, never seed
    seed_names = {"admin", "student", "company"}
    safe_ids = []
    if real_user_ids:
        fmt = ",".join(["%s"] * len(real_user_ids))
        cur.execute(f"SELECT id, username FROM sys_user WHERE id IN ({fmt})", real_user_ids)
        for uid, uname in cur.fetchall():
            if uname not in seed_names:
                safe_ids.append(uid)
    if safe_ids:
        fmt = ",".join(["%s"] * len(safe_ids))
        for table, col in [
            ("sys_user", "auditor_id"),
            ("ent_company", "auditor_id"),
            ("job_position", "auditor_id"),
        ]:
            cur.execute(f"UPDATE {table} SET {col}=NULL WHERE {col} IN ({fmt})", safe_ids)
        # student-related for demo stu if replace
        add("stu_skill", delete_in("stu_skill", "user_id", safe_ids))
        add("stu_resume", delete_in("stu_resume", "user_id", safe_ids))
        add("stu_profile", delete_in("stu_profile", "user_id", safe_ids))
        add("job_favorite", delete_in("job_favorite", "user_id", safe_ids))
        add("user_behavior_log", delete_in("user_behavior_log", "user_id", safe_ids))
        add("sys_user", delete_in("sys_user", "id", safe_ids))
    return counts


def fetch_maps(cur) -> tuple[dict[str, int], dict[str, int], dict[str, str], int]:
    cur.execute("SELECT id, name FROM job_category WHERE deleted=0")
    cat = {name: cid for cid, name in cur.fetchall()}
    cur.execute("SELECT id, name, direction FROM skill_tag WHERE deleted=0")
    skill_by_name = {}
    skill_dir = {}
    for tid, name, direction in cur.fetchall():
        skill_by_name[name] = tid
        skill_dir[name] = direction
    cur.execute("SELECT id FROM sys_user WHERE username='admin' AND deleted=0 LIMIT 1")
    row = cur.fetchone()
    admin_id = row[0] if row else 1
    return cat, skill_by_name, skill_dir, admin_id


def ensure_categories(cur, cat: dict[str, int]) -> dict[str, int]:
    needed = [d for d, _ in DIRECTION_RULES]
    # ensure parent 技术研发
    if "技术研发" not in cat:
        cur.execute(
            "INSERT INTO job_category (parent_id, name, sort_no, status, create_time, update_time, deleted) VALUES (NULL,%s,0,1,%s,%s,0)",
            ("技术研发", now(), now()),
        )
        cat["技术研发"] = cur.lastrowid
    parent = cat["技术研发"]
    for name in needed:
        if name not in cat:
            cur.execute(
                "INSERT INTO job_category (parent_id, name, sort_no, status, create_time, update_time, deleted) VALUES (%s,%s,0,1,%s,%s,0)",
                (parent, name, now(), now()),
            )
            cat[name] = cur.lastrowid
    # product parent
    if "产品设计" not in cat:
        cur.execute(
            "INSERT INTO job_category (parent_id, name, sort_no, status, create_time, update_time, deleted) VALUES (NULL,%s,0,1,%s,%s,0)",
            ("产品设计", now(), now()),
        )
        cat["产品设计"] = cur.lastrowid
    for name in ("产品经理", "UI设计"):
        if name not in cat:
            cur.execute(
                "INSERT INTO job_category (parent_id, name, sort_no, status, create_time, update_time, deleted) VALUES (%s,%s,0,1,%s,%s,0)",
                (cat["产品设计"], name, now(), now()),
            )
            cat[name] = cur.lastrowid
    return cat


def default_skills_for_direction(direction: str, skill_by_name: dict[str, int], skill_dir: dict[str, str]) -> list[int]:
    ids = [skill_by_name[n] for n, d in skill_dir.items() if d == direction and n in skill_by_name]
    # skill_dir maps name->direction; rebuild
    ids = [tid for name, tid in skill_by_name.items() if skill_dir.get(name) == direction]
    return ids[:3]


def import_jobs(cur, jobs: list[dict[str, Any]], pass_hash: str, admin_id: int, rng: random.Random) -> dict[str, Any]:
    cat, skill_by_name, skill_dir, admin_id2 = fetch_maps(cur)
    admin_id = admin_id or admin_id2
    cat = ensure_categories(cur, cat)

    # group by company
    by_co: dict[str, list[dict]] = {}
    for job in jobs:
        key = job.get("company_key") or "unknown"
        by_co.setdefault(key, []).append(job)

    stats = {"companies": 0, "jobs": 0, "tags": 0, "by_company": {}}
    t0 = now()

    for company_key, items in by_co.items():
        meta = COMPANY_META.get(company_key, {
            "name": items[0].get("company_label") or company_key,
            "short": items[0].get("company_label") or company_key,
            "industry": "互联网",
            "scale": 5,
            "city": "北京",
            "website": items[0].get("source") or "",
        })
        meta["short"] = meta.get("name") or meta.get("short") or company_key
        username = f"{USER_PREFIX}{company_key}"
        credit = credit_code_for(company_key)
        province = CITY_PROVINCE.get(meta["city"], "北京")
        created = t0 - timedelta(days=rng.randint(1, 20))

        cur.execute(
            """INSERT INTO sys_user
               (username, password, role, nickname, phone, email, avatar, status,
                audit_remark, audit_time, auditor_id, last_login_time, create_time, update_time, deleted)
               VALUES (%s,%s,2,%s,%s,%s,NULL,1,'真实校招企业账号',%s,%s,NULL,%s,%s,0)""",
            (
                username, pass_hash, f"{meta['short']}招聘",
                f"138{rng.randint(10000000, 99999999)}", f"hr@{company_key}.campus.local",
                created + timedelta(days=1), admin_id, created, created,
            ),
        )
        user_id = cur.lastrowid
        cur.execute(
            """INSERT INTO ent_company
               (user_id, company_name, short_name, logo_url, industry, scale, province, city, address,
                website, intro, credit_code, license_url, contact_name, contact_phone, contact_email,
                audit_status, audit_remark, audit_time, auditor_id, create_time, update_time, deleted)
               VALUES (%s,%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s,1,'真实校招数据导入',%s,%s,%s,%s,0)""",
            (
                user_id, meta["name"], meta["short"], meta["industry"], meta["scale"],
                province, meta["city"], f"{meta['city']}（校招官网同步）",
                meta.get("website") or "",
                f"{meta['name']}校招职位来自公开校园招聘接口同步，投递请以官网为准。",
                credit, f"{meta['short']}HR", f"138{rng.randint(10000000, 99999999)}",
                f"hr@{company_key}.campus.local",
                created + timedelta(days=1), admin_id, created, created,
            ),
        )
        company_id = cur.lastrowid
        stats["companies"] += 1
        co_job_count = 0

        # dedupe by post_id within company
        seen = set()
        for item in items:
            post_id = str(item.get("post_id") or "")
            if not post_id or post_id in seen:
                continue
            seen.add(post_id)
            title = (item.get("title") or "").strip()[:128]
            if not title:
                continue
            project = item.get("project") or ""
            direction = infer_direction(title, project)
            category_id = cat.get(direction) or cat.get("后端开发")
            province_j, city_j = parse_city(item.get("work_cities") or "", meta["city"])
            salary_min, salary_max, months = estimate_salary(direction, city_j)
            apply_url = item.get("apply_url") or ""
            source = item.get("source") or ""
            crawled_at = item.get("crawled_at") or now().isoformat()
            recruit_label = item.get("recruit_label") or "校招"
            desc = (
                f"【校招官网投递】{apply_url}\n"
                f"【来源】{source} / {meta['name']} / post_id={post_id}\n"
                f"【项目/方向】{project or direction} / {recruit_label}\n"
                f"【工作城市】{item.get('work_cities') or city_j}\n"
                f"【抓取时间】{crawled_at}\n\n"
                f"岗位名称：{title}\n"
                f"本条记录由公开校园招聘 API 同步，薪资为平台按方向与城市估算，实际以官网为准。"
            )
            requirement = json.dumps(
                {
                    "provenance": {
                        "company_key": company_key,
                        "company_label": meta["name"],
                        "source": source,
                        "post_id": post_id,
                        "apply_url": apply_url,
                        "crawled_at": crawled_at,
                        "recruit_label": recruit_label,
                        "project": project,
                        "work_cities": item.get("work_cities"),
                    }
                },
                ensure_ascii=False,
            )
            welfare = f"投递链接: {apply_url}"[:500] if apply_url else "详见官网"
            # job_type: intern vs campus
            label = f"{recruit_label}{project}{title}"
            job_type = 2 if re.search(r"实习|intern", label, re.I) else 3
            education = 3 if re.search(r"硕士|研究生|博士", title) else 2
            publish_time = now() - timedelta(hours=rng.randint(1, 24*14))

            cur.execute(
                """INSERT INTO job_position
                   (company_id, category_id, title, tech_direction, province, city, district, address,
                    salary_min, salary_max, salary_months, education, experience_req, job_type, headcount,
                    description, requirement, welfare, shelf_status, audit_status, audit_remark, audit_time,
                    auditor_id, publish_time, view_count, favorite_count, apply_count,
                    create_time, update_time, deleted)
                   VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s,%s,%s,1,%s,%s,%s,%s,%s,1,1,'真实校招同步',%s,%s,%s,%s,0,0,%s,%s,0)""",
                (
                    company_id, category_id, title, direction, province_j, city_j,
                    f"{city_j}（详见官网）", salary_min, salary_max, months, education, job_type,
                    rng.randint(1, 5), desc, requirement, welfare,
                    publish_time, admin_id, publish_time,
                    rng.randint(5, 80), publish_time, publish_time,
                ),
            )
            position_id = cur.lastrowid
            tag_ids = match_skills(title, project, direction, skill_by_name)
            if len(tag_ids) < 2:
                tag_ids = list(dict.fromkeys(tag_ids + default_skills_for_direction(direction, skill_by_name, skill_dir)))[:4]
            for tid in tag_ids:
                cur.execute(
                    "INSERT INTO job_position_tag (position_id, tag_id, create_time, update_time, deleted) VALUES (%s,%s,%s,%s,0)",
                    (position_id, tid, publish_time, publish_time),
                )
                stats["tags"] += 1
            co_job_count += 1
            stats["jobs"] += 1
        stats["by_company"][company_key] = co_job_count
    return stats


def inject_behaviors(cur, rng: random.Random) -> dict[str, int]:
    """Attach view/fav/apply behaviors from existing students onto real jobs for CF."""
    cur.execute(
        """SELECT p.id, p.tech_direction, p.city FROM job_position p
           JOIN ent_company c ON c.id=p.company_id
           WHERE c.credit_code LIKE %s AND p.deleted=0 AND p.shelf_status=1 AND p.audit_status=1""",
        (CREDIT_PREFIX + "%",),
    )
    real_jobs = cur.fetchall()
    if not real_jobs:
        return {"events": 0}
    by_dir: dict[str, list[tuple]] = {}
    for row in real_jobs:
        by_dir.setdefault(row[1], []).append(row)

    cur.execute(
        """SELECT u.id, IFNULL(p.expect_direction,'后端开发'), IFNULL(p.expect_city,'北京')
           FROM sys_user u
           LEFT JOIN stu_profile p ON p.user_id=u.id AND p.deleted=0
           WHERE u.role=1 AND u.deleted=0 AND u.status=1
           LIMIT 250"""
    )
    students = cur.fetchall()
    # resumes for apply
    cur.execute("SELECT user_id, id FROM stu_resume WHERE deleted=0")
    resume_map = {uid: rid for uid, rid in cur.fetchall()}

    events = 0
    favs = 0
    apps = 0
    t0 = now()
    for user_id, direction, city in students:
        pool = by_dir.get(direction) or real_jobs
        # prefer same city
        same_city = [j for j in pool if j[2] == city]
        choices = same_city or pool
        k = min(len(choices), rng.randint(3, 8))
        picked = rng.sample(choices, k)
        for idx, (pid, _d, _c) in enumerate(picked):
            ts = t0 - timedelta(hours=rng.randint(1, 72), minutes=rng.randint(0, 59))
            # view
            cur.execute(
                """INSERT INTO user_behavior_log
                   (user_id, behavior_type, target_type, target_id, weight, create_time, update_time, deleted)
                   VALUES (%s,1,1,%s,%s,%s,%s,0)""",
                (user_id, pid, 1, ts, ts),
            )
            events += 1
            if idx < 2 and rng.random() < 0.7:
                # favorite
                cur.execute(
                    """INSERT INTO job_favorite (user_id, position_id, create_time, update_time, deleted)
                       VALUES (%s,%s,%s,%s,0)
                       ON DUPLICATE KEY UPDATE deleted=0, update_time=VALUES(update_time)""",
                    (user_id, pid, ts, ts),
                )
                favs += 1
                cur.execute(
                    """INSERT INTO user_behavior_log
                       (user_id, behavior_type, target_type, target_id, weight, create_time, update_time, deleted)
                       VALUES (%s,2,1,%s,%s,%s,%s,0)""",
                    (user_id, pid, 3, ts, ts),
                )
                events += 1
            if idx == 0 and rng.random() < 0.35:
                # apply if resume exists and no existing application
                resume_id = resume_map.get(user_id)
                cur.execute(
                    "SELECT company_id FROM job_position WHERE id=%s", (pid,)
                )
                company_id = cur.fetchone()[0]
                try:
                    cur.execute(
                        """INSERT INTO job_application
                           (user_id, position_id, company_id, resume_id, status, remark, apply_time, create_time, update_time, deleted)
                           VALUES (%s,%s,%s,%s,0,'真实校招投递（演示行为）',%s,%s,%s,0)""",
                        (user_id, pid, company_id, resume_id, ts, ts, ts),
                    )
                    apps += 1
                    cur.execute(
                        """INSERT INTO user_behavior_log
                           (user_id, behavior_type, target_type, target_id, weight, create_time, update_time, deleted)
                           VALUES (%s,3,1,%s,%s,%s,%s,0)""",
                        (user_id, pid, 5, ts, ts),
                    )
                    events += 1
                    cur.execute("UPDATE job_position SET apply_count=apply_count+1 WHERE id=%s", (pid,))
                except pymysql.err.IntegrityError:
                    pass
    return {"events": events, "favorites": favs, "applications": apps}


def append_csv(jobs: list[dict[str, Any]], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    # dedupe by title+company against existing
    existing = set()
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                existing.add((row.get("title"), row.get("company")))
    n = 0
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["title", "company", "city", "salary_text", "education_text", "experience_text", "tags", "publish_date", "direction"],
        )
        if write_header:
            writer.writeheader()
        for item in jobs:
            meta = COMPANY_META.get(item.get("company_key") or "", {})
            company = meta.get("name") or item.get("company_label") or item.get("company_key")
            title = item.get("title") or ""
            if (title, company) in existing:
                continue
            direction = infer_direction(title, item.get("project") or "")
            _p, city = parse_city(item.get("work_cities") or "", meta.get("city") or "北京")
            smin, smax, _ = estimate_salary(direction, city)
            salary_text = f"{smin // 1000}-{smax // 1000}K"
            crawled = item.get("crawled_at") or now().isoformat()
            try:
                dt = datetime.fromisoformat(crawled.replace("Z", "+00:00"))
                publish_date = dt.strftime("%m/%d/%Y")
            except Exception:
                publish_date = now().strftime("%m/%d/%Y")
            writer.writerow({
                "title": title,
                "company": company,
                "city": city,
                "salary_text": salary_text,
                "education_text": "本科及以上",
                "experience_text": "应届生",
                "tags": direction,
                "publish_date": publish_date,
                "direction": direction,
            })
            existing.add((title, company))
            n += 1
    return n


def rewrite_csv_from_db(cur, path: Path) -> int:
    cur.execute(
        """SELECT p.title, c.company_name, p.city,
                  CONCAT(ROUND(p.salary_min/1000), '-', ROUND(p.salary_max/1000), 'K') AS salary_text,
                  CASE p.education WHEN 1 THEN '专科' WHEN 2 THEN '本科及以上' WHEN 3 THEN '硕士及以上' WHEN 4 THEN '博士' ELSE '学历不限' END,
                  CASE p.experience_req WHEN 1 THEN '应届生' WHEN 2 THEN '一年以内' ELSE '经验不限' END,
                  p.tech_direction,
                  DATE_FORMAT(IFNULL(p.publish_time, p.create_time), '%%m/%%d/%%Y')
           FROM job_position p
           JOIN ent_company c ON c.id=p.company_id
           WHERE p.deleted=0 AND p.audit_status=1"""
    )
    rows = cur.fetchall()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["title", "company", "city", "salary_text", "education_text", "experience_text", "tags", "publish_date", "direction"])
        for title, company, city, salary, edu, exp, direction, pub in rows:
            writer.writerow([title, company, city, salary, edu, exp, direction, pub, direction])
    return len(rows)


def main() -> int:
    args = parse_args()
    jobs = load_jobs(args.input)
    if not jobs:
        print("no jobs loaded", file=sys.stderr)
        return 1
    print(f"[import] loaded {len(jobs)} jobs from {args.input}")
    rng = random.Random(args.seed)
    conn = pymysql.connect(**db_config())
    try:
        with conn.cursor() as cur:
            deleted = delete_real_data(cur, replace_demo=args.replace_demo_jobs)
            print(f"[import] cleaned previous real data: {deleted}")
            pass_hash = password_hash()
            cur.execute("SELECT id FROM sys_user WHERE username='admin' LIMIT 1")
            admin_id = cur.fetchone()[0]
            stats = import_jobs(cur, jobs, pass_hash, admin_id, rng)
            print(f"[import] companies={stats['companies']} jobs={stats['jobs']} tags={stats['tags']}")
            print(f"[import] by_company={stats['by_company']}")
            behavior_stats = {}
            if args.inject_behaviors:
                behavior_stats = inject_behaviors(cur, rng)
                print(f"[import] behaviors={behavior_stats}")
            csv_path = ROOT / "data" / "raw" / "jobs_raw.csv"
            csv_n = 0
            if args.replace_csv:
                csv_n = rewrite_csv_from_db(cur, csv_path)
                print(f"[import] rewrote CSV rows={csv_n} -> {csv_path}")
            elif args.append_csv:
                csv_n = append_csv(jobs, csv_path)
                print(f"[import] appended CSV rows={csv_n} -> {csv_path}")
            conn.commit()
            # verify seed accounts intact
            cur.execute("SELECT username FROM sys_user WHERE username IN ('admin','student','company')")
            seeds = sorted(r[0] for r in cur.fetchall())
            assert seeds == ["admin", "company", "student"], seeds
            cur.execute(
                """SELECT c.company_name, COUNT(*) FROM job_position p
                   JOIN ent_company c ON c.id=p.company_id
                   WHERE c.credit_code LIKE %s AND p.deleted=0 GROUP BY c.company_name ORDER BY COUNT(*) DESC""",
                (CREDIT_PREFIX + "%",),
            )
            print("[import] verify counts:")
            for name, cnt in cur.fetchall():
                print(f"  {name}: {cnt}")
        summary = {
            "imported_jobs": stats["jobs"],
            "companies": stats["companies"],
            "by_company": stats["by_company"],
            "behaviors": behavior_stats,
            "csv_rows": csv_n,
            "password_hint": "real_* / Real@123",
        }
        out = Path(args.input)
        out = out if out.is_dir() else out.parent
        (out / "import_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[import] done")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
