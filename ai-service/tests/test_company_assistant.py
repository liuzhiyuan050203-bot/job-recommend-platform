"""企业招聘助手：投递统计意图路由、工具与角色隔离兜底（标准库 unittest，需本机 MySQL）。

运行：cd ai-service && ../.venv/bin/python -m unittest -v tests.test_company_assistant
"""

from __future__ import annotations

import unittest

from app.agent import chat
from app.agent.router import COMPANY_DOC_TYPES, allowed_tool_names, route
from app.agent.tools import Caller, execute, render
from app.spark.db import connect

STUDENT_ONLY_DOC_TYPES = {1, 2, 3, 5}


def _demo_company_user() -> tuple[int, int]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id AS uid, c.id AS cid FROM sys_user u
                INNER JOIN ent_company c ON c.user_id = u.id AND c.deleted = 0
                WHERE u.username = 'company' AND u.deleted = 0
                """
            )
            row = cur.fetchone()
            return int(row["uid"]), int(row["cid"])
    finally:
        conn.close()


class CompanyStatsRouteTest(unittest.TestCase):
    def tool_names(self, question: str, role: str = "company") -> list[str]:
        return [item.name for item in route(question, role).tools]

    def test_weekly_overview_routes_to_stats(self):
        decided = route("本周投递概况", "company")
        self.assertEqual([t.name for t in decided.tools], ["application_stats"])
        self.assertEqual(decided.tools[0].args.get("days"), 7)
        self.assertEqual(decided.doc_types, [])
        self.assertNotIn("学校就业指导中心", decided.instruction.replace("不要提及学校就业指导中心", ""))

    def test_stats_variants(self):
        for question, days in [
            ("最近收到了多少简历", 7),
            ("这个月各岗位投递统计", 30),
            ("今天新增几份投递", 1),
            ("近14天的投递情况怎么样", 14),
            ("帮我看看招聘看板数据", 7),
        ]:
            with self.subTest(question=question):
                decided = route(question, "company")
                self.assertEqual([t.name for t in decided.tools], ["application_stats"])
                self.assertEqual(decided.tools[0].args.get("days"), days)

    def test_existing_company_intents_unchanged(self):
        self.assertEqual(self.tool_names("帮我筛选职位 1 的候选人"), ["screen_applicants"])
        self.assertEqual(self.tool_names("列出我发布的职位"), ["list_my_jobs"])
        self.assertEqual(self.tool_names("帮我写一份Java后端开发的JD"), ["generate_job_description"])

    def test_company_fallback_never_uses_student_docs(self):
        for question in ["你好", "怎么提高招聘效率", "三方协议违约金怎么约定", "面试技巧有哪些", "就业政策补贴"]:
            with self.subTest(question=question):
                decided = route(question, "company")
                self.assertTrue(decided.doc_types, "企业兜底应检索企业侧资料")
                self.assertTrue(set(decided.doc_types) <= set(COMPANY_DOC_TYPES))
                self.assertFalse(set(decided.doc_types) & STUDENT_ONLY_DOC_TYPES)

    def test_agent_doc_types_filtered_for_company(self):
        from app.agent.lc_chain import doc_types_for_tools
        from app.agent.router import ToolRequest

        picked = [ToolRequest("generate_job_description", {"title": "Java"})]
        self.assertEqual(doc_types_for_tools(picked, "company"), [4])
        self.assertEqual(doc_types_for_tools(picked, "student"), [5, 4])

    def test_stats_tool_whitelisted_only_for_company(self):
        self.assertIn("application_stats", allowed_tool_names("company"))
        self.assertNotIn("application_stats", allowed_tool_names("student"))
        self.assertNotIn("application_stats", allowed_tool_names("admin"))

    def test_student_route_unaffected(self):
        decided = route("本周投递概况", "student")
        self.assertNotIn("application_stats", [t.name for t in decided.tools])

    def test_compliance_does_not_screen(self):
        for question in [
            "招候选人只限男性合不合规",
            "职位描述里写只招女生是否合规",
            "向候选人收培训费合不合法",
            "入职收费算不算可以写进任职要求",
        ]:
            with self.subTest(question=question):
                decided = route(question, "company")
                names = [item.name for item in decided.tools]
                self.assertNotIn("screen_applicants", names, question)
                self.assertTrue(decided.doc_types, question)
                self.assertTrue(set(decided.doc_types) <= set(COMPANY_DOC_TYPES))
                self.assertIn("合规", decided.instruction)


class CompanyStatsToolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user_id, cls.company_id = _demo_company_user()

    def test_stats_match_database_for_callers_company(self):
        result = execute("application_stats", {"days": 7, "company_id": 999999}, Caller(self.user_id, "company"))
        self.assertTrue(result.get("ok"), result)
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS total,
                           SUM(a.apply_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)) AS recent,
                           SUM(a.status = 0) AS pending
                    FROM job_application a
                    INNER JOIN job_position p ON p.id = a.position_id AND p.deleted = 0
                    WHERE a.company_id = %s AND a.deleted = 0
                    """,
                    (self.company_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        self.assertEqual(result["total"], int(row["total"] or 0))
        self.assertEqual(result["recent"], int(row["recent"] or 0))
        self.assertEqual(result["pending"], int(row["pending"] or 0))
        self.assertEqual(len(result["statuses"]), 5)
        self.assertLessEqual(len(result["topJobs"]), 3)
        text, summary = render("application_stats", result)
        self.assertIn("结论：", text)
        self.assertIn("待办提醒", text)
        self.assertNotIn("学校", text)
        self.assertIn("新增", summary)

    def test_student_and_admin_denied(self):
        self.assertTrue(execute("application_stats", {}, Caller(self.user_id, "student")).get("denied"))
        self.assertTrue(execute("application_stats", {}, Caller(self.user_id, "admin")).get("denied"))

    def test_user_without_company_denied(self):
        result = execute("application_stats", {}, Caller(-1, "company"))
        self.assertTrue(result.get("denied"))


class CompanyFallbackTextTest(unittest.TestCase):
    def test_no_hit_text_company_has_no_student_phrasing(self):
        for text in [
            chat._no_hit_text("company"),
            chat._offline_text("随便问问", [], "", role="company"),
            chat._offline_text("随便问问", [], "", timed_out=True, role="company"),
            chat._system_prompt(chat.AGENT_NAMES["company"], False).replace("不要建议咨询学校就业指导中心", ""),
        ]:
            self.assertNotIn("学校就业指导中心", text)
            self.assertNotIn("以学校和当地最新政策为准", text)

    def test_student_fallback_kept(self):
        self.assertIn("学校就业指导中心", chat._no_hit_text("student"))


if __name__ == "__main__":
    unittest.main()
