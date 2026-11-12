"""薪资问题同时预测并检索在招岗位；企业名可识别外部扩充库。

运行：cd ai-service && ../.venv/bin/python -m unittest -v tests.test_route_salary
"""

from __future__ import annotations

import unittest

from app.agent.lc_chain import doc_types_for_tools
from app.agent.router import ToolRequest, route


class SalaryRouteTest(unittest.TestCase):
    def test_salary_uses_predict_and_live_jobs(self):
        decided = route("杭州 Java 后端月薪多少", "student")
        names = [item.name for item in decided.tools]
        self.assertEqual(names[0], "predict_salary")
        self.assertIn("search_jobs", names)
        self.assertEqual(decided.doc_types, [7])
        self.assertIn("在招", decided.instruction)
        self.assertIn("估算", decided.instruction)
        args = decided.tools[0].args
        self.assertEqual(args.get("city"), "杭州")
        self.assertTrue(args.get("direction") or decided.tools[1].args.get("direction") or decided.tools[1].args.get("keyword"))

    def test_salary_paraphrase(self):
        for question in ["我在杭州做后端能拿多少", "上海算法岗薪资大概多少", "帮我预测一下北京产品经理的薪资"]:
            with self.subTest(question=question):
                decided = route(question, "student")
                names = [item.name for item in decided.tools]
                self.assertIn("predict_salary", names)
                self.assertIn("search_jobs", names)
                self.assertEqual(decided.doc_types, [7])

    def test_job_search_without_salary_unchanged(self):
        decided = route("杭州有哪些 Java 后端岗位", "student")
        names = [item.name for item in decided.tools]
        self.assertEqual(names, ["search_jobs"])
        self.assertEqual(decided.doc_types, [7])
        self.assertEqual(decided.answer_shape, "job_list")

    def test_predict_salary_doc_types_for_agent(self):
        picked = [ToolRequest("predict_salary", {"city": "杭州"})]
        self.assertEqual(doc_types_for_tools(picked, "student"), [7])

    def test_dongchedi_company_slot(self):
        decided = route("懂车帝在招哪些产品经理", "student")
        self.assertEqual([item.name for item in decided.tools], ["search_jobs"])
        self.assertEqual(decided.slots.get("keyword"), "懂车帝")
        self.assertEqual(decided.doc_types, [7])


if __name__ == "__main__":
    unittest.main()
