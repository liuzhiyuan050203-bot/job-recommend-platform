"""一次性清理接口测试 / UX 审计在演示库里留下的夹具数据（逻辑删除，可回滚）。

背景：tests/api 早期版本用演示账号 student / company 跑招聘流程和越权用例，结束后不收尾，
久而久之演示企业「星澜科技」下堆了几十个「招聘流程测试*」「越权隔离职位*」职位，演示学生
「陈晓」有几十条「已录用」投递、几十份测试简历和面试提醒；测试注册的临时账号还给真实职位投递。
测试脚本现在会在退出时清理自己的夹具（见 tests/api/lib.sh 的 purge_fixtures），本脚本只处理
历史遗留。

识别规则（全部按名称/归属精确匹配，不按编号取模，不改任何正常数据的状态）：
- 夹具账号：学生/企业角色、用户名不属于演示账号 admin/student/company、demo_*、real_*、ext_*（外部扩充企业）的账号
  （测试脚本注册的 stu*/com*/rstu*/rcom*/cold*/secu*/m1*/rsm*/uxcom* 等）。
- 夹具职位：夹具企业的全部职位；演示企业职位中标题匹配测试前缀的（见 JOB_TITLE_PATTERNS）。
- 夹具简历：夹具账号的简历；演示学生名下标题匹配测试前缀的简历（见 RESUME_TITLE_PATTERNS）。
- 夹具投递：落在夹具职位上、由夹具账号发出、或使用夹具简历的投递，以及对应日志、面试、收藏、行为日志。
- 词表：名为「Rust测试」的技能标签、「测试分类」及测试脚本建的「父类*/子类*」职位分类（无引用时）。

用法：
  .venv/bin/python data/cleanup_test_fixtures.py            # 只统计，不写库
  .venv/bin/python data/cleanup_test_fixtures.py --apply    # 执行逻辑删除
执行前请先备份：mysqldump ... | gzip > backup.sql.gz
"""

from __future__ import annotations

import argparse
import os
import sys

import pymysql

DEMO_USERNAMES = ("admin", "student", "company")
DEMO_PREFIXES = ("demo\\_%", "real\\_%", "ext\\_%")
JOB_TITLE_PATTERNS = (
    "招聘流程测试%",
    "越权隔离职位%",
    "UX-IDOR%",
    "UX技能职位%",
    "用户体验审计岗位%",
    "薪资错误%",
)
RESUME_TITLE_PATTERNS = (
    "招聘流程测试简历%",
    "安全简历%",
    "推荐测试简历%",
    "E2E简历%",
    "解析测试简历%",
)
TAG_NAMES = ("Rust测试",)
CATEGORY_NAMES = ("测试分类",)
CATEGORY_PATTERNS = ("父类%", "子类%")
DEMO_STUDENT = "student"
DEMO_DEFAULT_RESUME_TITLE = "陈晓-校招简历"


def connect():
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "job"),
        password=os.environ.get("MYSQL_PASSWORD", "job123"),
        database=os.environ.get("MYSQL_DATABASE", "job_platform"),
        charset="utf8mb4",
        autocommit=False,
    )


def ids(cur, sql: str, args: tuple = ()) -> list[int]:
    cur.execute(sql, args)
    return sorted({int(row[0]) for row in cur.fetchall() if row[0] is not None})


def in_clause(values: list[int]) -> str:
    return ",".join(str(int(v)) for v in values) or "NULL"


def like_any(column: str, patterns: tuple[str, ...]) -> str:
    return "(" + " OR ".join(f"{column} LIKE %s" for _ in patterns) + ")"


def collect(cur) -> dict[str, list[int]]:
    demo_user_sql = (
        "username IN (%s,%s,%s) OR " + " OR ".join("username LIKE %s" for _ in DEMO_PREFIXES)
    )
    demo_args = DEMO_USERNAMES + DEMO_PREFIXES
    users = ids(
        cur,
        f"SELECT id FROM sys_user WHERE deleted = 0 AND role IN (1, 2) AND NOT ({demo_user_sql})",
        demo_args,
    )
    companies = ids(cur, f"SELECT id FROM ent_company WHERE deleted = 0 AND user_id IN ({in_clause(users)})")
    jobs = ids(cur, f"SELECT id FROM job_position WHERE deleted = 0 AND company_id IN ({in_clause(companies)})")
    jobs += ids(
        cur,
        f"SELECT id FROM job_position WHERE deleted = 0 AND {like_any('title', JOB_TITLE_PATTERNS)}",
        JOB_TITLE_PATTERNS,
    )
    jobs = sorted(set(jobs))
    resumes = ids(cur, f"SELECT id FROM stu_resume WHERE deleted = 0 AND user_id IN ({in_clause(users)})")
    resumes += ids(
        cur,
        f"SELECT id FROM stu_resume WHERE deleted = 0 AND {like_any('title', RESUME_TITLE_PATTERNS)}",
        RESUME_TITLE_PATTERNS,
    )
    resumes = sorted(set(resumes))
    apps = ids(
        cur,
        f"""SELECT id FROM job_application WHERE deleted = 0 AND (
              position_id IN ({in_clause(jobs)}) OR user_id IN ({in_clause(users)})
              OR company_id IN ({in_clause(companies)}) OR resume_id IN ({in_clause(resumes)}))""",
    )
    touched_jobs = ids(cur, f"SELECT DISTINCT position_id FROM job_application WHERE id IN ({in_clause(apps)})")
    touched_jobs += ids(
        cur,
        f"SELECT DISTINCT position_id FROM job_favorite WHERE deleted = 0 AND user_id IN ({in_clause(users)})",
    )
    tags = ids(
        cur,
        "SELECT id FROM skill_tag WHERE deleted = 0 AND name IN (" + ",".join(["%s"] * len(TAG_NAMES)) + ")",
        TAG_NAMES,
    )
    tags = [t for t in tags if not ids(cur, "SELECT 1 FROM job_position_tag WHERE tag_id = %s LIMIT 1", (t,))]
    categories = ids(
        cur,
        "SELECT id FROM job_category WHERE deleted = 0 AND (name IN ("
        + ",".join(["%s"] * len(CATEGORY_NAMES))
        + ") OR "
        + like_any("name", CATEGORY_PATTERNS)
        + ")",
        CATEGORY_NAMES + CATEGORY_PATTERNS,
    )
    categories = [
        c for c in categories
        if not ids(cur, "SELECT 1 FROM job_position WHERE category_id = %s AND deleted = 0 LIMIT 1", (c,))
    ]
    return {
        "users": users,
        "companies": companies,
        "jobs": jobs,
        "resumes": resumes,
        "applications": apps,
        "touched_jobs": sorted(set(touched_jobs) - set(jobs)),
        "tags": tags,
        "categories": categories,
    }


def apply(cur, found: dict[str, list[int]]) -> dict[str, int]:
    users, jobs, apps = in_clause(found["users"]), in_clause(found["jobs"]), in_clause(found["applications"])
    companies, resumes = in_clause(found["companies"]), in_clause(found["resumes"])
    statements = {
        "job_interview": f"""UPDATE job_interview SET deleted = 1 WHERE deleted = 0 AND (
            application_id IN ({apps}) OR position_id IN ({jobs}) OR user_id IN ({users}) OR company_id IN ({companies}))""",
        "job_application_log": f"UPDATE job_application_log SET deleted = 1 WHERE deleted = 0 AND application_id IN ({apps})",
        "job_application": f"UPDATE job_application SET deleted = 1 WHERE deleted = 0 AND id IN ({apps})",
        "job_favorite": f"""UPDATE job_favorite SET deleted = 1 WHERE deleted = 0 AND (
            position_id IN ({jobs}) OR user_id IN ({users}))""",
        "user_behavior_log": f"""UPDATE user_behavior_log SET deleted = 1 WHERE deleted = 0 AND (
            (target_type = 1 AND target_id IN ({jobs})) OR user_id IN ({users}))""",
        "job_position": f"UPDATE job_position SET deleted = 1, shelf_status = 0 WHERE deleted = 0 AND id IN ({jobs})",
        "stu_resume": f"UPDATE stu_resume SET deleted = 1, is_default = 0 WHERE deleted = 0 AND id IN ({resumes})",
        "stu_skill": f"UPDATE stu_skill SET deleted = 1 WHERE deleted = 0 AND user_id IN ({users})",
        "stu_profile": f"UPDATE stu_profile SET deleted = 1 WHERE deleted = 0 AND user_id IN ({users})",
        "com_post": f"UPDATE com_post SET deleted = 1 WHERE deleted = 0 AND (user_id IN ({users}) OR position_id IN ({jobs}))",
        "ai_session": f"UPDATE ai_session SET deleted = 1 WHERE deleted = 0 AND user_id IN ({users})",
        "ent_company": f"UPDATE ent_company SET deleted = 1 WHERE deleted = 0 AND id IN ({companies})",
        "sys_user": f"UPDATE sys_user SET deleted = 1 WHERE deleted = 0 AND id IN ({users})",
        "skill_tag": f"UPDATE skill_tag SET deleted = 1 WHERE deleted = 0 AND id IN ({in_clause(found['tags'])})",
        "job_category": f"UPDATE job_category SET deleted = 1 WHERE deleted = 0 AND id IN ({in_clause(found['categories'])})",
    }
    done: dict[str, int] = {}
    for table, sql in statements.items():
        done[table] = cur.execute(sql)
    touched = in_clause(found["touched_jobs"])
    done["job_position(计数重算)"] = cur.execute(
        f"""UPDATE job_position p SET
              apply_count = (SELECT COUNT(*) FROM job_application a WHERE a.position_id = p.id AND a.deleted = 0),
              favorite_count = (SELECT COUNT(*) FROM job_favorite f WHERE f.position_id = p.id AND f.deleted = 0)
            WHERE p.id IN ({touched})"""
    )
    # 演示学生恢复种子里的默认简历
    cur.execute(
        """UPDATE stu_resume r JOIN sys_user u ON u.id = r.user_id
           SET r.is_default = (r.title = %s)
           WHERE u.username = %s AND r.deleted = 0""",
        (DEMO_DEFAULT_RESUME_TITLE, DEMO_STUDENT),
    )
    done["stu_resume(恢复演示默认简历)"] = cur.rowcount
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="执行逻辑删除；默认只统计")
    args = parser.parse_args()
    conn = connect()
    try:
        with conn.cursor() as cur:
            found = collect(cur)
            for key, values in found.items():
                print(f"{key:14s} {len(values)}")
            if not args.apply:
                print("仅统计（加 --apply 执行）")
                return 0
            done = apply(cur, found)
        conn.commit()
        for table, count in done.items():
            print(f"已处理 {table}: {count}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
