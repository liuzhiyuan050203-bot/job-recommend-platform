"""按角色注册的只读或生成类工具。

user_id 与 role 只来自调用方上下文，忽略模型自行填写的身份字段。
统计查询全部使用参数化 SQL，不拼接模型给出的语句。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.core.response import AppException
from app.spark.db import connect
from app.spark.dicts import EDU_TEXT

logger = logging.getLogger(__name__)

EDU_LABEL = {0: "不限", 1: "专科", 2: "本科", 3: "硕士", 4: "博士"}
APP_STATUS = {0: "待初筛", 1: "笔试", 2: "面试中", 3: "已录用", 4: "未通过"}


@dataclass
class Caller:
    user_id: int
    role: str
    nickname: str = ""


def deny(message: str) -> dict[str, Any]:
    return {"ok": False, "denied": True, "message": message}


def _norm(name: str) -> str:
    return re.sub(r"\s+", "", str(name or "")).lower()


def _money(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{int(value)}元"


def _clip(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _coerce_edu(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, str) and not value.isdigit():
        mapped = EDU_TEXT.get(value.strip())
        if mapped in (1, 2, 3, 4):
            return int(mapped)
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number in (1, 2, 3, 4) else None


def _profile(user_id: int) -> dict[str, Any]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT real_name, major, education, expect_city, expect_direction, self_intro
                FROM stu_profile
                WHERE user_id = %s AND deleted = 0
                """,
                (user_id,),
            )
            row = cur.fetchone() or {}
            cur.execute(
                """
                SELECT skill_desc FROM stu_resume
                WHERE user_id = %s AND deleted = 0
                ORDER BY is_default DESC, id DESC
                LIMIT 1
                """,
                (user_id,),
            )
            resume = cur.fetchone() or {}
    finally:
        conn.close()
    row["skill_desc"] = resume.get("skill_desc") or ""
    return row


def _skill_names(user_id: int) -> list[str]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.name
                FROM stu_skill s
                INNER JOIN skill_tag t ON t.id = s.tag_id AND t.deleted = 0
                WHERE s.user_id = %s AND s.deleted = 0
                ORDER BY s.proficiency DESC, t.name
                """,
                (user_id,),
            )
            return [row["name"] for row in cur.fetchall()]
    finally:
        conn.close()


def _job_skill_names(position_id: int) -> list[str]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.name
                FROM job_position_tag pt
                INNER JOIN skill_tag t ON t.id = pt.tag_id AND t.deleted = 0
                WHERE pt.position_id = %s AND pt.deleted = 0
                ORDER BY t.name
                """,
                (position_id,),
            )
            return [row["name"] for row in cur.fetchall()]
    finally:
        conn.close()


def _company_of(user_id: int) -> dict[str, Any] | None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, company_name, city
                FROM ent_company
                WHERE user_id = %s AND deleted = 0
                """,
                (user_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def search_jobs(
    caller: Caller,
    keyword: str = "",
    city: str = "",
    direction: str = "",
    education: Any = None,
    salary_min: Any = None,
    limit: int = 5,
) -> dict[str, Any]:
    if caller.role != "student":
        return deny("检索在招职位仅学生就业助手可用。")
    limit = max(1, min(int(limit or 5), 8))
    edu = _coerce_edu(education)
    try:
        salary = int(salary_min) if salary_min not in (None, "", 0) else None
    except (TypeError, ValueError):
        salary = None
    keyword = (keyword or "").strip()[:40]
    city = (city or "").strip()[:32]
    direction = (direction or "").strip()[:64]
    like = f"%{keyword}%" if keyword else ""
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.title, c.company_name, p.city, p.tech_direction,
                       p.salary_min, p.salary_max, p.salary_months, p.education,
                       (
                         SELECT GROUP_CONCAT(t.name ORDER BY t.name SEPARATOR '、')
                         FROM job_position_tag pt
                         INNER JOIN skill_tag t ON t.id = pt.tag_id AND t.deleted = 0
                         WHERE pt.position_id = p.id AND pt.deleted = 0
                       ) AS skills
                FROM job_position p
                INNER JOIN ent_company c ON c.id = p.company_id AND c.deleted = 0
                WHERE p.deleted = 0 AND p.shelf_status = 1 AND p.audit_status = 1
                  AND (%s = '' OR p.city = %s)
                  AND (%s = '' OR p.tech_direction = %s)
                  AND (%s IS NULL OR p.education = 0 OR p.education <= %s)
                  AND (%s IS NULL OR p.salary_max >= %s)
                  AND (
                        %s = ''
                        OR p.title LIKE %s
                        OR p.tech_direction LIKE %s
                        OR EXISTS (
                            SELECT 1 FROM job_position_tag pt
                            INNER JOIN skill_tag t ON t.id = pt.tag_id AND t.deleted = 0
                            WHERE pt.position_id = p.id AND pt.deleted = 0 AND t.name LIKE %s
                        )
                  )
                ORDER BY (CASE WHEN %s <> '' AND p.title LIKE %s THEN 0 ELSE 1 END), p.publish_time DESC
                LIMIT %s
                """,
                (
                    city, city,
                    direction, direction,
                    edu, edu,
                    salary, salary,
                    keyword, like, like, like,
                    keyword, like,
                    limit,
                ),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    items = [
        {
            "id": int(row["id"]),
            "title": row["title"],
            "company": row["company_name"],
            "city": row["city"],
            "direction": row["tech_direction"],
            "salary": f"{int(row['salary_min'])}-{int(row['salary_max'])}元/{int(row['salary_months'] or 12)}薪",
            "education": EDU_LABEL.get(int(row["education"] or 0), "不限"),
            "skills": row["skills"] or "",
        }
        for row in rows
    ]
    return {"ok": True, "total": len(items), "items": items}


def get_my_recommendations(caller: Caller, limit: int = 5) -> dict[str, Any]:
    if caller.role != "student":
        return deny("个性化推荐仅学生本人可查看。")
    limit = max(1, min(int(limit or 5), 8))
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.position_id, r.match_score, r.rank_no, r.reason, r.algo,
                       p.title, p.city, p.tech_direction, p.salary_min, p.salary_max,
                       c.company_name
                FROM spark_recommend r
                INNER JOIN job_position p
                    ON p.id = r.position_id AND p.deleted = 0 AND p.shelf_status = 1 AND p.audit_status = 1
                INNER JOIN ent_company c ON c.id = p.company_id AND c.deleted = 0
                WHERE r.user_id = %s AND r.is_latest = 1 AND r.deleted = 0
                ORDER BY CASE r.algo WHEN 3 THEN 0 WHEN 2 THEN 1 ELSE 2 END, r.rank_no
                LIMIT 30
                """,
                (caller.user_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    items = []
    seen: set[int] = set()
    for row in rows:
        position_id = int(row["position_id"])
        if position_id in seen:
            continue
        seen.add(position_id)
        items.append(
            {
                "id": position_id,
                "title": row["title"],
                "company": row["company_name"],
                "city": row["city"],
                "direction": row["tech_direction"],
                "salary": f"{int(row['salary_min'])}-{int(row['salary_max'])}元",
                "score": float(row["match_score"]),
                "reason": row["reason"] or "",
            }
        )
        if len(items) >= limit:
            break
    source = "spark_recommend"
    if not items:
        from app.spark.recommend_online import recommend_for_user

        data = recommend_for_user(caller.user_id, limit)
        source = data.get("source") or "realtime"
        for row in data.get("items") or []:
            items.append(
                {
                    "id": int(row["positionId"]),
                    "title": row["title"],
                    "company": row.get("companyName") or "",
                    "city": row.get("city") or "",
                    "direction": row.get("techDirection") or "",
                    "salary": f"{int(row.get('salaryMin') or 0)}-{int(row.get('salaryMax') or 0)}元",
                    "score": row.get("matchScore"),
                    "reason": row.get("reason") or "",
                }
            )
    return {"ok": True, "source": source, "items": items[:limit]}


def predict_salary(
    caller: Caller,
    city: str = "",
    direction: str = "",
    education: Any = None,
    experience_years: Any = None,
) -> dict[str, Any]:
    if caller.role != "student":
        return deny("薪资预测仅学生就业助手可用。")
    profile = _profile(caller.user_id)
    city = (city or profile.get("expect_city") or "").strip()
    direction = (direction or profile.get("expect_direction") or "").strip()
    edu = _coerce_edu(education)
    if edu is None:
        edu = _coerce_edu(profile.get("education"))
    if experience_years is None or experience_years == "":
        years = 0.0
    else:
        try:
            years = float(experience_years)
        except (TypeError, ValueError):
            return {"ok": False, "message": "工作年限无法识别。"}
    if not city or not direction or edu is None:
        return {"ok": False, "message": "请补充城市、技术方向和学历后再预测薪资。"}
    from app.spark.predict import predict_salary as run_predict
    from app.spark.runner import call_exclusive

    try:
        data = call_exclusive(
            lambda: run_predict(city, direction, edu, years, allow_model=True)
        )
        if data is None:
            data = run_predict(city, direction, edu, years, allow_model=False)
    except AppException as exc:
        return {"ok": False, "message": exc.msg}
    except Exception as exc:
        logger.exception("薪资预测失败")
        return {"ok": False, "message": "薪资预测暂时不可用。"}
    return {
        "ok": True,
        "city": data.get("city"),
        "direction": data.get("techDirection"),
        "education": EDU_LABEL.get(int(data.get("education") or 0), str(data.get("education"))),
        "experienceYears": data.get("experienceYears"),
        "predictedSalary": data.get("predictedSalary"),
        "ciLow": data.get("ciLow"),
        "ciHigh": data.get("ciHigh"),
        "source": data.get("source"),
    }


def _resolve_job_for_student(caller: Caller, job_id: int | None, keyword: str) -> dict | None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            if job_id:
                cur.execute(
                    """
                    SELECT p.id, p.title, c.company_name, p.city, p.tech_direction
                    FROM job_position p
                    INNER JOIN ent_company c ON c.id = p.company_id
                    WHERE p.id = %s AND p.deleted = 0 AND p.shelf_status = 1 AND p.audit_status = 1
                    """,
                    (int(job_id),),
                )
                row = cur.fetchone()
                if row:
                    return row
            if keyword:
                cur.execute(
                    """
                    SELECT p.id, p.title, c.company_name, p.city, p.tech_direction
                    FROM job_position p
                    INNER JOIN ent_company c ON c.id = p.company_id
                    WHERE p.deleted = 0 AND p.shelf_status = 1 AND p.audit_status = 1
                      AND (p.title LIKE %s OR p.tech_direction = %s)
                    ORDER BY p.publish_time DESC
                    LIMIT 1
                    """,
                    (f"%{keyword}%", keyword),
                )
                row = cur.fetchone()
                if row:
                    return row
            cur.execute(
                """
                SELECT p.id, p.title, c.company_name, p.city, p.tech_direction
                FROM spark_recommend r
                INNER JOIN job_position p
                    ON p.id = r.position_id AND p.deleted = 0 AND p.shelf_status = 1 AND p.audit_status = 1
                INNER JOIN ent_company c ON c.id = p.company_id
                WHERE r.user_id = %s AND r.is_latest = 1 AND r.deleted = 0
                ORDER BY r.rank_no
                LIMIT 1
                """,
                (caller.user_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def analyze_resume_gap(caller: Caller, job_id: Any = None, keyword: str = "") -> dict[str, Any]:
    if caller.role != "student":
        return deny("技能差距只对照当前学生本人的档案，不能查询其他人。")
    try:
        parsed_id = int(job_id) if job_id not in (None, "", 0) else None
    except (TypeError, ValueError):
        parsed_id = None
    job = _resolve_job_for_student(caller, parsed_id, (keyword or "").strip())
    if not job:
        return {"ok": False, "message": "没有找到可对照的在架职位，请说明职位编号或关键词。"}
    required = _job_skill_names(int(job["id"]))
    owned = _skill_names(caller.user_id)
    profile = _profile(caller.user_id)
    blob = f"{profile.get('skill_desc') or ''} {profile.get('self_intro') or ''}"
    owned_norm = {_norm(name): name for name in owned}
    for name in required:
        if _norm(name) not in owned_norm and name and name.lower() in blob.lower():
            owned_norm[_norm(name)] = name
    matched = [name for name in required if _norm(name) in owned_norm]
    missing = [name for name in required if _norm(name) not in owned_norm]
    percent = int(round(100 * len(matched) / len(required))) if required else 0
    suggestions = [f"可用课程或项目补充 {name}，并在简历中写明你做过的部分。" for name in missing[:4]]
    if not missing:
        suggestions.append("要求中的技能已覆盖，建议把对应项目写清楚你的个人贡献。")
    return {
        "ok": True,
        "jobId": int(job["id"]),
        "title": job["title"],
        "company": job["company_name"],
        "city": job["city"],
        "direction": job["tech_direction"],
        "matched": matched,
        "missing": missing,
        "matchPercent": percent,
        "studentSkills": owned[:12],
        "suggestions": suggestions,
    }


def _direction_skills(direction: str) -> list[str]:
    if not direction:
        return []
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.name, COUNT(*) AS cnt
                FROM job_position p
                INNER JOIN job_position_tag pt ON pt.position_id = p.id AND pt.deleted = 0
                INNER JOIN skill_tag t ON t.id = pt.tag_id AND t.deleted = 0
                WHERE p.deleted = 0 AND p.shelf_status = 1 AND p.audit_status = 1
                  AND p.tech_direction = %s
                GROUP BY t.name
                ORDER BY cnt DESC
                LIMIT 6
                """,
                (direction,),
            )
            return [row["name"] for row in cur.fetchall()]
    finally:
        conn.close()


def generate_job_description(
    caller: Caller,
    title: str = "",
    direction: str = "",
    city: str = "",
    skills: str = "",
    highlights: str = "",
) -> dict[str, Any]:
    if caller.role != "company":
        return deny("生成职位描述仅企业招聘助手可用。")
    company = _company_of(caller.user_id)
    if not company:
        return deny("当前账号没有企业资料，不能生成职位描述。")
    title = (title or direction or "软件开发工程师").strip()[:40]
    direction = (direction or "").strip()[:64]
    city = (city or company.get("city") or "").strip()[:32]
    skill_list = [part.strip() for part in re.split(r"[、,，/\s]+", skills or "") if part.strip()]
    if not skill_list:
        skill_list = _direction_skills(direction)
    return {
        "ok": True,
        "mode": "draft",
        "title": title,
        "direction": direction or "未指定",
        "city": city or "未指定",
        "company": company["company_name"],
        "skills": skill_list[:6],
        "highlights": _clip(highlights, 120),
    }


def polish_job_description(caller: Caller, text: str = "") -> dict[str, Any]:
    if caller.role != "company":
        return deny("润色职位描述仅企业招聘助手可用。")
    body = (text or "").strip()
    if len(body) < 8:
        return {"ok": False, "message": "请贴出需要润色的职位描述。"}
    return {"ok": True, "mode": "polish", "text": body[:1200]}


def _pick_company_job(company_id: int, job_id: int | None) -> dict | None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            if job_id:
                cur.execute(
                    """
                    SELECT id, title, city, company_id, apply_count
                    FROM job_position
                    WHERE id = %s AND deleted = 0
                    """,
                    (int(job_id),),
                )
                return cur.fetchone()
            cur.execute(
                """
                SELECT id, title, city, company_id, apply_count
                FROM job_position
                WHERE company_id = %s AND deleted = 0
                ORDER BY (title NOT LIKE %s) DESC, apply_count DESC, id ASC
                LIMIT 1
                """,
                (company_id, "招聘流程测试%"),
            )
            return cur.fetchone()
    finally:
        conn.close()


def screen_applicants(caller: Caller, job_id: Any = None) -> dict[str, Any]:
    if caller.role != "company":
        return deny("筛选候选人仅企业招聘助手可用。")
    company = _company_of(caller.user_id)
    if not company:
        return deny("当前账号没有企业资料。")
    try:
        parsed_id = int(job_id) if job_id not in (None, "", 0) else None
    except (TypeError, ValueError):
        parsed_id = None
    job = _pick_company_job(int(company["id"]), parsed_id)
    if not job:
        return {"ok": False, "message": "没有找到可筛选的职位。"}
    if int(job["company_id"]) != int(company["id"]):
        return deny("只能筛选本公司发布的职位，不能查看其他企业的候选人。")
    required = _job_skill_names(int(job["id"]))
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.user_id, a.status, u.nickname
                FROM job_application a
                INNER JOIN sys_user u ON u.id = a.user_id AND u.deleted = 0
                WHERE a.position_id = %s AND a.company_id = %s AND a.deleted = 0
                ORDER BY a.apply_time DESC
                LIMIT 30
                """,
                (int(job["id"]), int(company["id"])),
            )
            applicants = cur.fetchall()
            skills: dict[int, list[str]] = {}
            if applicants:
                marks = ", ".join(["%s"] * len(applicants))
                cur.execute(
                    f"""
                    SELECT s.user_id, t.name
                    FROM stu_skill s
                    INNER JOIN skill_tag t ON t.id = s.tag_id AND t.deleted = 0
                    WHERE s.deleted = 0 AND s.user_id IN ({marks})
                    """,
                    [int(row["user_id"]) for row in applicants],
                )
                for row in cur.fetchall():
                    skills.setdefault(int(row["user_id"]), []).append(row["name"])
    finally:
        conn.close()
    ranked = []
    required_norm = {_norm(name) for name in required}
    for row in applicants:
        owned = skills.get(int(row["user_id"]), [])
        owned_norm = {_norm(name) for name in owned}
        matched = [name for name in required if _norm(name) in owned_norm]
        missing = [name for name in required if _norm(name) not in owned_norm]
        percent = int(round(100 * len(matched) / len(required_norm))) if required_norm else 0
        ranked.append(
            {
                "nickname": row["nickname"] or "候选人",
                "status": APP_STATUS.get(int(row["status"]), str(row["status"])),
                "matchPercent": percent,
                "matched": matched[:6],
                "missing": missing[:6],
            }
        )
    ranked.sort(key=lambda item: item["matchPercent"], reverse=True)
    return {
        "ok": True,
        "jobId": int(job["id"]),
        "title": job["title"],
        "city": job["city"],
        "applicantCount": len(ranked),
        "applicants": ranked[:8],
    }


def list_my_jobs(caller: Caller, limit: int = 8) -> dict[str, Any]:
    if caller.role != "company":
        return deny("企业职位列表仅企业招聘助手可用。")
    company = _company_of(caller.user_id)
    if not company:
        return deny("当前账号没有企业资料。")
    limit = max(1, min(int(limit or 8), 8))
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, city, tech_direction, shelf_status, audit_status, apply_count
                FROM job_position
                WHERE company_id = %s AND deleted = 0
                ORDER BY (title NOT LIKE %s) DESC, apply_count DESC, id ASC
                LIMIT %s
                """,
                (int(company["id"]), "招聘流程测试%", limit),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    audit = {0: "待审核", 1: "已通过", 2: "已驳回"}
    items = [
        {
            "id": int(row["id"]),
            "title": row["title"],
            "city": row["city"],
            "direction": row["tech_direction"],
            "shelf": "上架" if int(row["shelf_status"]) == 1 else "下架",
            "audit": audit.get(int(row["audit_status"]), ""),
            "applyCount": int(row["apply_count"] or 0),
        }
        for row in rows
    ]
    return {"ok": True, "company": company["company_name"], "items": items}


def salary_stats(caller: Caller, city: str = "", direction: str = "") -> dict[str, Any]:
    if caller.role != "admin":
        return deny("薪资统计仅管理员数据助手可用。")
    city = (city or "").strip()
    direction = (direction or "").strip()
    conn = connect()
    try:
        with conn.cursor() as cur:
            if not city and not direction:
                cur.execute(
                    """
                    SELECT city,
                           ROUND(SUM(avg_salary * job_count) / SUM(job_count), 0) AS avg_salary,
                           SUM(job_count) AS job_count
                    FROM spark_salary_stat
                    WHERE is_latest = 1 AND deleted = 0
                    GROUP BY city
                    HAVING SUM(job_count) > 0
                    ORDER BY avg_salary DESC
                    LIMIT 8
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT city, tech_direction,
                           ROUND(avg_salary, 0) AS avg_salary,
                           job_count
                    FROM spark_salary_stat
                    WHERE is_latest = 1 AND deleted = 0
                      AND (%s = '' OR city = %s)
                      AND (%s = '' OR tech_direction = %s)
                    ORDER BY avg_salary DESC
                    LIMIT 8
                    """,
                    (city, city, direction, direction),
                )
            rows = cur.fetchall()
    finally:
        conn.close()
    items = [
        {
            "city": row["city"],
            "direction": row.get("tech_direction") or "",
            "avgSalary": int(row["avg_salary"] or 0),
            "jobCount": int(row["job_count"] or 0),
        }
        for row in rows
    ]
    return {"ok": True, "items": items}


def tech_trend(caller: Caller, skill: str = "", top_n: int = 5) -> dict[str, Any]:
    if caller.role != "admin":
        return deny("技术趋势仅管理员数据助手可用。")
    top_n = max(1, min(int(top_n or 5), 10))
    skill = (skill or "").strip()[:64]
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT MAX(stat_month) AS latest_month
                FROM spark_tech_trend
                WHERE is_latest = 1 AND deleted = 0 AND mom_rate IS NOT NULL
                """
            )
            latest = (cur.fetchone() or {}).get("latest_month")
            cur.execute(
                """
                SELECT tag_name, tech_direction, stat_month, demand_count, mom_rate
                FROM spark_tech_trend
                WHERE is_latest = 1 AND deleted = 0 AND mom_rate IS NOT NULL
                  AND (%s = '' OR stat_month = %s)
                  AND (%s = '' OR tag_name = %s)
                ORDER BY mom_rate DESC
                LIMIT %s
                """,
                (latest or "", latest or "", skill, skill, top_n),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    items = [
        {
            "skill": row["tag_name"],
            "direction": row["tech_direction"],
            "month": row["stat_month"],
            "demand": int(row["demand_count"] or 0),
            "momRate": float(row["mom_rate"]),
        }
        for row in rows
    ]
    return {"ok": True, "items": items}


def city_distribution(caller: Caller, top_n: int = 8) -> dict[str, Any]:
    """在架且审核通过的职位按城市计数。口径是 job_position，不是省份汇总表。"""
    if caller.role != "admin":
        return deny("城市分布仅管理员数据助手可用。")
    top_n = max(1, min(int(top_n or 8), 20))
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT city, province, COUNT(*) AS job_count
                FROM job_position
                WHERE deleted = 0 AND shelf_status = 1 AND audit_status = 1
                  AND city IS NOT NULL AND city <> ''
                GROUP BY city, province
                ORDER BY job_count DESC, city
                LIMIT %s
                """,
                (top_n,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    items = [
        {
            "city": row["city"],
            "province": row["province"],
            "jobCount": int(row["job_count"] or 0),
        }
        for row in rows
    ]
    return {"ok": True, "items": items}


def region_distribution(caller: Caller, top_n: int = 8) -> dict[str, Any]:
    if caller.role != "admin":
        return deny("地区分布仅管理员数据助手可用。")
    top_n = max(1, min(int(top_n or 8), 15))
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT province_name, job_count, company_count, avg_salary
                FROM spark_region_dist
                WHERE is_latest = 1 AND deleted = 0
                ORDER BY job_count DESC
                LIMIT %s
                """,
                (top_n,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    items = [
        {
            "province": row["province_name"],
            "jobCount": int(row["job_count"] or 0),
            "companyCount": int(row["company_count"] or 0),
            "avgSalary": int(row["avg_salary"] or 0) if row["avg_salary"] is not None else None,
        }
        for row in rows
    ]
    return {"ok": True, "items": items}


def recommend_eval(caller: Caller) -> dict[str, Any]:
    if caller.role != "admin":
        return deny("推荐评估仅管理员数据助手可用。")
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT algo, k, precision_at_k, recall_at_k, ndcg_at_k, coverage, user_count
                FROM spark_recommend_eval
                WHERE is_latest = 1 AND deleted = 0
                ORDER BY algo, k
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    items = [
        {
            "algo": row["algo"],
            "k": int(row["k"]),
            "precision": float(row["precision_at_k"]),
            "recall": float(row["recall_at_k"]),
            "ndcg": float(row["ndcg_at_k"]),
            "coverage": float(row["coverage"]),
            "users": int(row["user_count"] or 0),
        }
        for row in rows
    ]
    return {"ok": True, "items": items}


def platform_overview(caller: Caller) -> dict[str, Any]:
    if caller.role != "admin":
        return deny("平台概况仅管理员数据助手可用。")
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM sys_user WHERE deleted = 0 AND role = 1) AS students,
                  (SELECT COUNT(*) FROM ent_company WHERE deleted = 0) AS companies,
                  (SELECT COUNT(*) FROM job_position
                    WHERE deleted = 0 AND shelf_status = 1 AND audit_status = 1) AS jobs,
                  (SELECT COUNT(*) FROM job_application WHERE deleted = 0) AS applications,
                  (SELECT COUNT(*) FROM cms_article WHERE deleted = 0 AND status = 1) AS articles
                """
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return {
        "ok": True,
        "students": int(row["students"]),
        "companies": int(row["companies"]),
        "jobs": int(row["jobs"]),
        "applications": int(row["applications"]),
        "articles": int(row["articles"]),
    }


_FUNCS = {
    "search_jobs": search_jobs,
    "get_my_recommendations": get_my_recommendations,
    "predict_salary": predict_salary,
    "analyze_resume_gap": analyze_resume_gap,
    "generate_job_description": generate_job_description,
    "polish_job_description": polish_job_description,
    "screen_applicants": screen_applicants,
    "list_my_jobs": list_my_jobs,
    "salary_stats": salary_stats,
    "tech_trend": tech_trend,
    "region_distribution": region_distribution,
    "city_distribution": city_distribution,
    "recommend_eval": recommend_eval,
    "platform_overview": platform_overview,
}

_ARG_KEYS = {
    "search_jobs": {"keyword", "city", "direction", "education", "salary_min", "limit"},
    "get_my_recommendations": {"limit"},
    "predict_salary": {"city", "direction", "education", "experience_years"},
    "analyze_resume_gap": {"job_id", "keyword"},
    "generate_job_description": {"title", "direction", "city", "skills", "highlights"},
    "polish_job_description": {"text"},
    "screen_applicants": {"job_id"},
    "list_my_jobs": {"limit"},
    "salary_stats": {"city", "direction"},
    "tech_trend": {"skill", "top_n"},
    "region_distribution": {"top_n"},
    "city_distribution": {"top_n"},
    "recommend_eval": set(),
    "platform_overview": set(),
}


def execute(name: str, args: dict | None, caller: Caller) -> dict[str, Any]:
    func = _FUNCS.get(name)
    if func is None:
        return {"ok": False, "message": "未知工具。"}
    from app.agent.router import allowed_tool_names

    if name not in allowed_tool_names(caller.role):
        return deny("当前角色不能使用该工具。")
    clean = {}
    for key, value in (args or {}).items():
        if key in _ARG_KEYS.get(name, set()) and key not in {"user_id", "role"}:
            clean[key] = value
    try:
        return func(caller, **clean)
    except Exception:
        logger.exception("工具 %s 执行失败", name)
        return {"ok": False, "message": "工具执行失败。"}


def render(name: str, result: dict[str, Any]) -> tuple[str, str]:
    """返回放进提示词的紧凑文本，以及给前端的一行摘要。"""
    if not result.get("ok"):
        message = result.get("message") or "无法完成。"
        return message, message
    if name == "search_jobs":
        lines = [f"找到 {result['total']} 个在架职位："]
        for item in result["items"]:
            lines.append(
                f"- {item['title']}｜{item['company']}｜{item['city']}｜{item['direction']}｜{item['salary']}｜{item['skills']}"
            )
        summary = f"检索到 {result['total']} 个职位"
        return "\n".join(lines), summary
    if name == "get_my_recommendations":
        lines = [f"推荐来源 {result.get('source')}："]
        for item in result["items"]:
            lines.append(
                f"- {item['title']}｜{item['company']}｜{item['city']}｜{item['salary']}｜匹配 {item['score']}｜{item['reason']}"
            )
        return "\n".join(lines), f"返回 {len(result['items'])} 条推荐"
    if name == "predict_salary":
        text = (
            f"{result['city']} {result['direction']} {result['education']} "
            f"经验 {result['experienceYears']} 年，预测月薪 {result['predictedSalary']} 元，"
            f"区间 {result['ciLow']} 到 {result['ciHigh']}（来源 {result['source']}）。"
        )
        return text, "已完成薪资预测"
    if name == "analyze_resume_gap":
        text = (
            f"对照职位 {result['title']}（{result['company']}，编号 {result['jobId']}）。"
            f"匹配 {result['matchPercent']}%。已匹配：{'、'.join(result['matched']) or '无'}。"
            f"缺失：{'、'.join(result['missing']) or '无'}。"
            f"建议：{' '.join(result['suggestions'])}"
        )
        return text, f"与职位 {result['jobId']} 的技能匹配 {result['matchPercent']}%"
    if name == "generate_job_description":
        skills = "、".join(result["skills"]) or "未指定"
        text = (
            f"请为{result['company']}撰写职位。标题：{result['title']}。方向：{result['direction']}。"
            f"城市：{result['city']}。可参考技能：{skills}。亮点：{result['highlights'] or '无'}。"
        )
        return text, f"已整理《{result['title']}》的职位要点"
    if name == "polish_job_description":
        return "待润色原文：\n" + result["text"], "已接收待润色文本"
    if name == "screen_applicants":
        lines = [f"职位 {result['title']}（编号 {result['jobId']}）共 {result['applicantCount']} 份投递："]
        for item in result["applicants"]:
            lines.append(
                f"- {item['nickname']}｜{item['status']}｜匹配 {item['matchPercent']}%"
                f"｜重合 {'、'.join(item['matched']) or '无'}｜缺失 {'、'.join(item['missing']) or '无'}"
            )
        if not result["applicants"]:
            lines.append("- 暂无投递")
        return "\n".join(lines), f"已筛选职位 {result['jobId']} 的 {result['applicantCount']} 位候选人"
    if name == "list_my_jobs":
        lines = [f"{result['company']}的职位："]
        for item in result["items"]:
            lines.append(
                f"- {item['id']} {item['title']}｜{item['city']}｜{item['shelf']}/{item['audit']}｜投递 {item['applyCount']}"
            )
        return "\n".join(lines), f"列出 {len(result['items'])} 个职位"
    if name == "salary_stats":
        lines = []
        if result["items"]:
            top = result["items"][0]
            lines.append(
                f"结论：平均月薪最高的是{top['city']}，{top['avgSalary']}元，样本 {top['jobCount']}。"
            )
        lines.append("平均月薪：")
        for item in result["items"]:
            extra = f"｜{item['direction']}" if item["direction"] else ""
            lines.append(f"- {item['city']}{extra}｜{item['avgSalary']}元｜样本 {item['jobCount']}")
        return "\n".join(lines), f"最高 {result['items'][0]['city']}" if result["items"] else "无薪资统计"
    if name == "tech_trend":
        lines = []
        if result["items"]:
            top = result["items"][0]
            lines.append(
                f"结论：增长最快的是{top['skill']}，月份 {top['month']}，环比 {top['momRate']:.2%}，需求 {top['demand']}。"
            )
        lines.append("技术需求环比：")
        for item in result["items"]:
            lines.append(
                f"- {item['skill']}｜{item['month']}｜需求 {item['demand']}｜环比 {item['momRate']:.2%}"
            )
        summary = f"最快 {result['items'][0]['skill']}" if result["items"] else "无趋势数据"
        return "\n".join(lines), summary
    if name == "region_distribution":
        lines = ["地区分布："]
        for item in result["items"]:
            lines.append(f"- {item['province']}｜职位 {item['jobCount']}｜企业 {item['companyCount']}｜均薪 {item['avgSalary']}")
        return "\n".join(lines), f"返回 {len(result['items'])} 个省份"
    if name == "city_distribution":
        lines = []
        if result["items"]:
            top = result["items"][0]
            lines.append(f"结论：岗位最多的城市是{top['city']}，职位 {top['jobCount']}。")
        lines.append("城市分布：")
        for item in result["items"]:
            province = f"（{item['province']}）" if item.get("province") else ""
            lines.append(f"- {item['city']}{province}｜职位 {item['jobCount']}")
        summary = f"最多 {result['items'][0]['city']}" if result["items"] else "无城市数据"
        return "\n".join(lines), summary
    if name == "recommend_eval":
        lines = ["推荐离线评估："]
        for item in result["items"]:
            if int(item["k"]) != 10:
                continue
            lines.append(
                f"- {item['algo']} K=10 P={item['precision']:.4f} R={item['recall']:.4f} "
                f"NDCG={item['ndcg']:.4f} 覆盖={item['coverage']:.4f}"
            )
        if len(lines) == 1:
            lines.append("- 暂无评估")
        return "\n".join(lines), "已读取推荐评估"
    if name == "platform_overview":
        text = (
            f"学生 {result['students']}，企业 {result['companies']}，在架职位 {result['jobs']}，"
            f"投递 {result['applications']}，已发布公告 {result['articles']}。"
        )
        return text, "已汇总平台规模"
    return str(result), name
