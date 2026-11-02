"""把演示投递推进成真实的招聘漏斗，并给演示企业 / 演示学生补一批可复现的投递。

为什么需要：generate_demo_data.py 和 import_real_jobs.py 写入的投递全部停在「待初筛」，
而演示账号上能看到的「已录用」几乎都来自测试脚本（已由 cleanup_test_fixtures.py 清理），
于是看板要么是倒漏斗（已录用 > 待初筛），要么全是待初筛。

做法（可复现，不按编号取模）：
1. 补充投递（只做一次，按备注识别）：
   - 演示企业 company（星澜科技）的在架职位：从 demo_stu_* 里选技能与职位标签重合最多、
     期望方向一致的学生，每个职位补 SEED_PER_JOB 份投递，投递时间落在锚点前 1–24 天。
   - 演示学生 student（陈晓）：在期望方向的在架职位里选技能重合最多的 SEED_FOR_STUDENT 个投递。
   同时写投递日志、投递行为日志（权重 5）并更新职位投递数。
2. 推进漏斗：对只有一条「提交投递」日志、仍是待初筛的投递，按投递时长和技能匹配度决定
   HR 是否处理、是否进入笔试 / 面试 / 录用或未通过。每条投递用 random.Random(f"{seed}:{id}")
   抽样，同一种子、同一锚点重复运行结果一致；已推进过的投递（日志多于 1 条）不再改动。
   每一步都按状态机写 job_application_log，笔试 / 面试写 job_interview，时间都不晚于锚点；
   仍在笔试 / 面试中的投递把下一场安排在锚点之后几天，作为「即将到来的安排」。

用法：
  .venv/bin/python data/rebalance_demo_funnel.py                 # 只预览
  .venv/bin/python data/rebalance_demo_funnel.py --apply
  .venv/bin/python data/rebalance_demo_funnel.py --apply --seed 20261103 --anchor "2026-11-03 00:00:00"
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from collections import Counter
from datetime import datetime, timedelta

import pymysql

SEED_REMARK = "校园招聘网申（演示补充）"
SEED_PER_JOB = 12
SEED_FOR_STUDENT = 5
STATUS = {0: "待初筛", 1: "笔试", 2: "面试中", 3: "已录用", 4: "未通过"}


def connect():
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "job"),
        password=os.environ.get("MYSQL_PASSWORD", "job123"),
        database=os.environ.get("MYSQL_DATABASE", "job_platform"),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def skills_of(cur, user_ids: list[int]) -> dict[int, set[int]]:
    if not user_ids:
        return {}
    marks = ",".join(["%s"] * len(user_ids))
    cur.execute(f"SELECT user_id, tag_id FROM stu_skill WHERE deleted = 0 AND user_id IN ({marks})", user_ids)
    out: dict[int, set[int]] = {uid: set() for uid in user_ids}
    for row in cur.fetchall():
        out[int(row["user_id"])].add(int(row["tag_id"]))
    return out


def tags_of(cur, job_ids: list[int]) -> dict[int, set[int]]:
    if not job_ids:
        return {}
    out: dict[int, set[int]] = {jid: set() for jid in job_ids}
    for start in range(0, len(job_ids), 1000):
        part = job_ids[start:start + 1000]
        cur.execute(
            f"SELECT position_id, tag_id FROM job_position_tag WHERE position_id IN ({','.join(['%s'] * len(part))})",
            part,
        )
        for row in cur.fetchall():
            out[int(row["position_id"])].add(int(row["tag_id"]))
    return out


def match_ratio(student: set[int], job: set[int]) -> float:
    return len(student & job) / len(job) if job else 0.0


def default_resume(cur, user_id: int) -> int | None:
    cur.execute(
        "SELECT id FROM stu_resume WHERE user_id = %s AND deleted = 0 ORDER BY is_default DESC, id ASC LIMIT 1",
        (user_id,),
    )
    row = cur.fetchone()
    return int(row["id"]) if row else None


def insert_application(cur, user_id: int, job: dict, when: datetime) -> bool:
    resume_id = default_resume(cur, user_id)
    if resume_id is None:
        return False
    cur.execute("SELECT 1 FROM job_application WHERE user_id = %s AND position_id = %s", (user_id, job["id"]))
    if cur.fetchone():
        return False
    cur.execute(
        """INSERT INTO job_application (user_id, position_id, company_id, resume_id, status, remark,
               apply_time, create_time, update_time, deleted)
           VALUES (%s, %s, %s, %s, 0, %s, %s, %s, %s, 0)""",
        (user_id, job["id"], job["company_id"], resume_id, SEED_REMARK, when, when, when),
    )
    app_id = cur.lastrowid
    cur.execute(
        """INSERT INTO job_application_log (application_id, from_status, to_status, operator_id, remark,
               create_time, update_time, deleted) VALUES (%s, NULL, 0, %s, '学生提交投递', %s, %s, 0)""",
        (app_id, user_id, when, when),
    )
    cur.execute(
        """INSERT INTO user_behavior_log (user_id, behavior_type, target_type, target_id, weight,
               create_time, update_time, deleted) VALUES (%s, 3, 1, %s, 5, %s, %s, 0)""",
        (user_id, job["id"], when, when),
    )
    cur.execute("UPDATE job_position SET apply_count = apply_count + 1 WHERE id = %s", (job["id"],))
    return True


def seed_applications(cur, rng: random.Random, anchor: datetime) -> dict[str, int]:
    cur.execute("SELECT COUNT(*) AS n FROM job_application WHERE remark = %s", (SEED_REMARK,))
    if int(cur.fetchone()["n"]):
        return {"已存在补充投递，跳过": 1}
    written = Counter()
    # 1) 演示企业的在架职位
    cur.execute(
        """SELECT p.id, p.company_id, p.tech_direction, p.publish_time FROM job_position p
           JOIN ent_company c ON c.id = p.company_id JOIN sys_user u ON u.id = c.user_id
           WHERE u.username = 'company' AND p.deleted = 0 AND p.audit_status = 1 AND p.shelf_status = 1
           ORDER BY p.id"""
    )
    company_jobs = cur.fetchall()
    cur.execute(
        """SELECT u.id, s.expect_direction FROM sys_user u JOIN stu_profile s ON s.user_id = u.id AND s.deleted = 0
           WHERE u.deleted = 0 AND u.username LIKE 'demo\\_stu\\_%%' ORDER BY u.id"""
    )
    students = cur.fetchall()
    student_skills = skills_of(cur, [int(s["id"]) for s in students])
    job_tags = tags_of(cur, [int(j["id"]) for j in company_jobs])
    for job in company_jobs:
        scored = []
        for student in students:
            uid = int(student["id"])
            score = match_ratio(student_skills.get(uid, set()), job_tags.get(int(job["id"]), set()))
            score += 0.3 if student["expect_direction"] == job["tech_direction"] else 0.0
            scored.append((-score, uid))
        scored.sort()
        picked = [uid for _score, uid in scored[: SEED_PER_JOB * 2]]
        rng.shuffle(picked)
        for uid in picked[:SEED_PER_JOB]:
            when = anchor - timedelta(days=rng.randint(1, 24), hours=rng.randint(0, 9), minutes=rng.randint(0, 59))
            if job["publish_time"] and when < job["publish_time"]:
                when = job["publish_time"] + timedelta(hours=rng.randint(2, 30))
            if insert_application(cur, uid, job, when):
                written["演示企业补充投递"] += 1
    # 2) 演示学生
    cur.execute(
        """SELECT u.id, s.expect_direction, s.expect_city FROM sys_user u
           JOIN stu_profile s ON s.user_id = u.id AND s.deleted = 0 WHERE u.username = 'student' AND u.deleted = 0"""
    )
    me = cur.fetchone()
    if me:
        uid = int(me["id"])
        cur.execute(
            """SELECT p.id, p.company_id, p.city, p.publish_time FROM job_position p
               JOIN ent_company c ON c.id = p.company_id AND c.deleted = 0
               JOIN sys_user u ON u.id = c.user_id AND (u.username LIKE 'demo\\_%%' OR u.username LIKE 'real\\_%%')
               WHERE p.deleted = 0 AND p.audit_status = 1 AND p.shelf_status = 1 AND p.tech_direction = %s
                 AND p.publish_time < %s
                 AND NOT EXISTS (SELECT 1 FROM job_application a WHERE a.user_id = %s AND a.position_id = p.id)""",
            (me["expect_direction"], anchor - timedelta(days=30), uid),
        )
        pool = cur.fetchall()
        mine = skills_of(cur, [uid]).get(uid, set())
        tags = tags_of(cur, [int(j["id"]) for j in pool])
        ranked = sorted(
            pool,
            key=lambda j: (-(match_ratio(mine, tags.get(int(j["id"]), set())) + (0.2 if j["city"] == me["expect_city"] else 0)), int(j["id"])),
        )
        used_companies: set[int] = set()
        for job in ranked:
            if len(used_companies) >= SEED_FOR_STUDENT:
                break
            if int(job["company_id"]) in used_companies:
                continue
            when = anchor - timedelta(days=rng.randint(4, 28), hours=rng.randint(0, 9))
            if insert_application(cur, uid, job, when):
                used_companies.add(int(job["company_id"]))
                written["演示学生补充投递"] += 1
    return dict(written)


def plan(rng: random.Random, apply_time: datetime, anchor: datetime, match: float, same_direction: bool) -> list[tuple]:
    """返回 [(to_status, when, remark, interview)]，interview 为 None 或 (round_no, round_name, time, status, remark)。"""
    age = (anchor - apply_time).total_seconds() / 86400
    if age < 1.5:
        return []
    if rng.random() >= min(0.75, (age - 1) / 28):
        return []  # HR 还没处理
    steps: list[tuple] = []
    t_screen = apply_time + timedelta(days=rng.uniform(0.5, min(5.0, age - 0.5)))
    p_screen = 0.22 + 0.5 * match + (0.1 if same_direction else 0.0)
    if rng.random() >= p_screen:
        steps.append((4, t_screen, "简历初筛未通过：技能与岗位要求差距较大", None))
        return steps
    exam_time = (t_screen + timedelta(days=rng.randint(2, 4))).replace(hour=rng.choice([10, 14, 19]), minute=0, second=0, microsecond=0)
    if exam_time >= anchor:
        exam_time = (anchor + timedelta(days=rng.randint(1, 5))).replace(hour=rng.choice([10, 14, 19]), minute=0, second=0, microsecond=0)
        steps.append((1, t_screen, "初筛通过，已发送笔试通知", (1, "笔试", exam_time, 0, "在线笔试，请提前 10 分钟进入")))
        return steps
    passed_exam = rng.random() < 0.4 + 0.35 * match
    exam_result = "笔试通过" if passed_exam else "笔试未通过"
    steps.append((1, t_screen, "初筛通过，已发送笔试通知", (1, "笔试", exam_time, 1, exam_result)))
    t_exam_done = exam_time + timedelta(days=rng.uniform(0.5, 2.0))
    if t_exam_done >= anchor:
        return steps
    if not passed_exam:
        steps.append((4, t_exam_done, "笔试未通过", None))
        return steps
    meet_time = (t_exam_done + timedelta(days=rng.randint(2, 5))).replace(hour=rng.choice([10, 14, 16]), minute=0, second=0, microsecond=0)
    if meet_time >= anchor:
        meet_time = (anchor + timedelta(days=rng.randint(1, 6))).replace(hour=rng.choice([10, 14, 16]), minute=0, second=0, microsecond=0)
        steps.append((2, t_exam_done, "笔试通过，已安排技术一面", (2, "技术一面", meet_time, 0, "请准备项目介绍")))
        return steps
    outcome = rng.random()
    meet_remark = "面试通过" if outcome < 0.3 else ("面试未通过" if outcome < 0.7 else "面试表现待定，等待复试")
    steps.append((2, t_exam_done, "笔试通过，已安排技术一面", (2, "技术一面", meet_time, 1, meet_remark)))
    t_decide = meet_time + timedelta(days=rng.uniform(1.0, 4.0))
    if t_decide >= anchor:
        return steps
    if outcome < 0.3:
        steps.append((3, t_decide, "综合评估通过，发放录用意向", None))
    elif outcome < 0.7:
        steps.append((4, t_decide, "面试未通过", None))
    return steps


def advance(cur, seed: int, anchor: datetime) -> Counter:
    cur.execute(
        """SELECT a.id, a.user_id, a.position_id, a.company_id, a.apply_time,
                  p.tech_direction, s.expect_direction, c.user_id AS hr_id, c.contact_name, c.contact_phone,
                  c.city AS company_city
           FROM job_application a
           JOIN job_position p ON p.id = a.position_id AND p.deleted = 0
           JOIN ent_company c ON c.id = a.company_id AND c.deleted = 0
           LEFT JOIN stu_profile s ON s.user_id = a.user_id AND s.deleted = 0
           WHERE a.deleted = 0 AND a.status = 0 AND a.apply_time < %s
             AND (SELECT COUNT(*) FROM job_application_log l WHERE l.application_id = a.id AND l.deleted = 0) <= 1
           ORDER BY a.id""",
        (anchor,),
    )
    rows = cur.fetchall()
    skills = skills_of(cur, sorted({int(r["user_id"]) for r in rows}))
    tags = tags_of(cur, sorted({int(r["position_id"]) for r in rows}))
    moved = Counter()
    for row in rows:
        rng = random.Random(f"{seed}:{row['id']}")
        match = match_ratio(skills.get(int(row["user_id"]), set()), tags.get(int(row["position_id"]), set()))
        steps = plan(rng, row["apply_time"], anchor, match, row["expect_direction"] == row["tech_direction"])
        if not steps:
            continue
        status = 0
        for to_status, when, remark, interview in steps:
            cur.execute(
                """INSERT INTO job_application_log (application_id, from_status, to_status, operator_id, remark,
                       create_time, update_time, deleted) VALUES (%s, %s, %s, %s, %s, %s, %s, 0)""",
                (row["id"], status, to_status, row["hr_id"], remark, when, when),
            )
            if interview:
                round_no, round_name, at, iv_status, iv_remark = interview
                online = round_no == 1 or rng.random() < 0.5
                past = iv_status != 0
                cur.execute(
                    """INSERT INTO job_interview (application_id, user_id, company_id, position_id, round_no, round_name,
                           interview_time, interview_type, location, meeting_url, contact_name, contact_phone,
                           interview_status, remind_ahead_minutes, remind_status, remind_time, remark,
                           create_time, update_time, deleted)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1440,%s,%s,%s,%s,%s,0)""",
                    (
                        row["id"], row["user_id"], row["company_id"], row["position_id"], round_no, round_name,
                        at, 1 if online else 2,
                        None if online else f"{row['company_city'] or ''}公司总部会议室",
                        f"https://meet.example.com/app-{row['id']}-{round_no}" if online else None,
                        row["contact_name"], row["contact_phone"], iv_status,
                        1 if past else 0, (at - timedelta(days=1)) if past else None, iv_remark,
                        when, when if not past else at,
                    ),
                )
            status = to_status
        cur.execute(
            "UPDATE job_application SET status = %s, remark = %s, update_time = %s WHERE id = %s",
            (status, steps[-1][2], steps[-1][1], row["id"]),
        )
        moved[STATUS[status]] += 1
    return moved


def distribution(cur, where: str = "", args: tuple = ()) -> dict[str, int]:
    cur.execute(
        f"""SELECT a.status, COUNT(*) AS n FROM job_application a
            JOIN job_position p ON p.id = a.position_id AND p.deleted = 0
            WHERE a.deleted = 0 {where} GROUP BY a.status ORDER BY a.status""",
        args,
    )
    return {STATUS[int(r["status"])]: int(r["n"]) for r in cur.fetchall()}


def main() -> int:
    parser = argparse.ArgumentParser(description="演示投递漏斗再平衡")
    parser.add_argument("--apply", action="store_true", help="写库；默认预览后回滚")
    parser.add_argument("--seed", type=int, default=20261103)
    parser.add_argument("--anchor", default="2026-11-03 00:00:00", help="时间锚点，所有推进都不晚于它")
    args = parser.parse_args()
    anchor = datetime.strptime(args.anchor, "%Y-%m-%d %H:%M:%S")
    conn = connect()
    try:
        with conn.cursor() as cur:
            print("推进前 全平台:", distribution(cur))
            seeded = seed_applications(cur, random.Random(args.seed), anchor)
            print("补充投递:", seeded)
            moved = advance(cur, args.seed, anchor)
            print("本次推进到:", dict(moved))
            print("推进后 全平台:", distribution(cur))
            print("推进后 演示企业:", distribution(cur, "AND a.company_id = (SELECT c.id FROM ent_company c JOIN sys_user u ON u.id = c.user_id WHERE u.username = 'company')"))
            print("推进后 演示学生:", distribution(cur, "AND a.user_id = (SELECT id FROM sys_user WHERE username = 'student')"))
        if args.apply:
            conn.commit()
            print("已提交")
        else:
            conn.rollback()
            print("预览结束，已回滚（加 --apply 写库）")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
