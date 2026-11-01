#!/usr/bin/env python3
"""把平台库中的职位导出为实验快照：synthetic（demo_ 合成，薪资由生成器公式产生）
与 campus_estimated（真实校招职位，薪资为估算，不可作为真值）。

.venv/bin/python experiments/salary/export_platform_jobs.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import jieba
import warnings

import pandas as pd
import pymysql

warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import DATA  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_real_salary import tokens_of  # noqa: E402

jieba.setLogLevel(60)
EDU_YEARS = {0: 16.0, 1: 15.0, 2: 16.0, 3: 19.0, 4: 22.0}
EXP_REQ_YEARS = {0: 1.0, 1: 0.0, 2: 1.0, 3: 2.0, 4: 4.0, 5: 6.0}
TIER1 = {"北京", "上海", "深圳", "广州"}
TIER2 = {"杭州", "南京", "苏州", "厦门", "成都", "武汉", "西安", "天津"}

SQL = """
SELECT p.id, p.title, p.city, p.province, p.tech_direction, p.education, p.experience_req, p.job_type,
       p.salary_min, p.salary_max, LEFT(c.credit_code, 4) AS src,
       (SELECT GROUP_CONCAT(st.name SEPARATOR ' ') FROM job_position_tag pt JOIN skill_tag st ON st.id = pt.tag_id
         WHERE pt.position_id = p.id AND pt.deleted = 0) AS skills
FROM job_position p JOIN ent_company c ON c.id = p.company_id
WHERE p.deleted = 0 AND p.audit_status = 1 AND p.salary_max >= p.salary_min
  AND (c.credit_code LIKE 'DEMO%%' OR c.credit_code LIKE 'REAL%%')
"""


def main() -> int:
    conn = pymysql.connect(host=os.environ.get("MYSQL_HOST", "127.0.0.1"), port=int(os.environ.get("MYSQL_PORT", 3306)),
                           user=os.environ.get("MYSQL_USER", "job"), password=os.environ.get("MYSQL_PASSWORD", "job123"),
                           database=os.environ.get("MYSQL_DATABASE", "job_platform"), charset="utf8mb4")
    try:
        df = pd.read_sql(SQL, conn)
    finally:
        conn.close()
    df["source"] = df["src"].map({"DEMO": "synthetic", "REAL": "campus_estimated"})
    df["skills"] = df["skills"].fillna("")
    df["avg_salary"] = (df["salary_min"] + df["salary_max"]) / 2.0
    df["exp_years"] = df["experience_req"].map(EXP_REQ_YEARS).fillna(1.0)
    df["edu_years"] = df["education"].map(EDU_YEARS).fillna(16.0)
    df["city_tier"] = df["city"].map(lambda c: 1 if c in TIER1 else 2 if c in TIER2 else 3)
    df["company_size"] = 0
    df["industry"] = "未知"
    df["tokens"] = [tokens_of(t, s) for t, s in zip(df["title"], df["skills"])]
    cols = ["id", "source", "title", "city", "province", "city_tier", "education", "edu_years", "exp_years",
            "job_type", "tech_direction", "company_size", "industry", "skills", "salary_min", "salary_max",
            "avg_salary", "tokens"]
    for name, part in df.groupby("source"):
        path = DATA / f"platform_{name}.csv"
        part[cols].to_csv(path, index=False)
        print(name, len(part), "->", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
