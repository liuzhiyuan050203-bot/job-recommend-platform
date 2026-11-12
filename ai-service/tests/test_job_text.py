"""职位知识库文本清洗与检索多样性。

运行：cd ai-service && ../.venv/bin/python -m unittest -v tests.test_job_text
"""

from __future__ import annotations

import unittest

from app.rag.diversity import diversify_hits
from app.rag.job_text import build_job_text, clean_job_fields

REAL_REQ = (
    '{"provenance": {"company_key": "bytedance", "company_label": "字节跳动", '
    '"source": "jobs.bytedance.com", "post_id": "1", '
    '"apply_url": "https://jobs.bytedance.com/campus/position/1/detail", '
    '"crawled_at": "2026-11-01T02:28:57+08:00", "recruit_label": "正式", '
    '"project": "算法", "work_cities": "北京 / 上海"}}'
)
REAL_DESC = (
    "【校招官网投递】https://jobs.bytedance.com/campus/position/1/detail\n"
    "【来源】jobs.bytedance.com / 字节跳动 / post_id=1\n【项目/方向】算法 / 正式\n"
    "【工作城市】北京 / 上海\n【抓取时间】2026-11-01T02:28:57+08:00\n\n"
    "岗位名称：算法工程师\n"
    "本条记录由公开校园招聘 API 同步，薪资为平台按方向与城市估算，实际以官网为准。\n"
    "负责推荐算法研发"
)
EXT_REQ = (
    '{"provenance": {"company_key": "dcar", "company_label": "懂车帝", '
    '"source": "dcar.jobs.feishu.cn", "post_id": "1", '
    '"apply_url": "https://dcar.jobs.feishu.cn/x", '
    '"crawled_at": "2026-11-11T21:54:19+08:00", "data_source": "ext_ats", '
    '"salary_estimated": true}, '
    '"requirements": "1、3年以上产品经验；\\n2、对数据敏感。"}'
)
EXT_DESC = (
    "【校招官网投递】https://dcar.jobs.feishu.cn/x\n"
    "【来源】dcar.jobs.feishu.cn / 懂车帝 / post_id=1\n"
    "【工作城市】北京\n【抓取时间】2026-11-11T21:54:19+08:00\n\n"
    "1、负责懂车帝交易业务中的营销产品；\n2、对交易流量转化负责。\n\n"
    "本条记录由飞书招聘公开门户同步（外部扩充库），薪资为平台按方向与城市估算，实际以官网为准。"
)


class CleanJobTextTest(unittest.TestCase):
    def test_provenance_json_not_in_requirement(self):
        cleaned = clean_job_fields(REAL_DESC, REAL_REQ, "投递链接: https://jobs.bytedance.com/campus/position/1/detail")
        self.assertNotIn("provenance", cleaned.requirement)
        self.assertNotIn("post_id", cleaned.requirement)
        self.assertNotIn("{", cleaned.requirement)
        self.assertIn("负责推荐算法研发", cleaned.description)
        self.assertNotIn("【来源】", cleaned.description)
        self.assertNotIn("校招官网投递", cleaned.description)
        self.assertEqual(cleaned.welfare, "")
        self.assertTrue(cleaned.salary_estimated)
        self.assertEqual(cleaned.source_company, "字节跳动")
        self.assertEqual(cleaned.source_site, "jobs.bytedance.com")
        self.assertIn("https://jobs.bytedance.com", cleaned.apply_url)

    def test_ext_ats_extracts_real_requirements(self):
        cleaned = clean_job_fields(EXT_DESC, EXT_REQ, "投递链接: https://dcar.jobs.feishu.cn/x", "ext_ats")
        self.assertIn("3年以上产品经验", cleaned.requirement)
        self.assertIn("对数据敏感", cleaned.requirement)
        self.assertNotIn("provenance", cleaned.requirement)
        self.assertIn("营销产品", cleaned.description)
        self.assertNotIn("飞书招聘公开门户同步", cleaned.description)
        self.assertEqual(cleaned.data_source, "ext_ats")
        self.assertTrue(cleaned.salary_estimated)
        self.assertEqual(cleaned.source_company, "懂车帝")

    def test_json_array_and_double_encoded(self):
        self.assertEqual(
            clean_job_fields(None, '["1. 统招本科及以上学历", "2. 精通Java"]', None).requirement,
            "统招本科及以上学历；精通Java",
        )
        cleaned = clean_job_fields(
            None,
            '{"requirements": [{"text": "会 Python"}, "会 SQL"], "source": "x.com", "salary_estimated": true}',
            None,
        )
        self.assertIn("会 Python", cleaned.requirement)
        self.assertIn("会 SQL", cleaned.requirement)
        self.assertTrue(cleaned.salary_estimated)

    def test_platform_job_keeps_body(self):
        cleaned = clean_job_fields(
            "1. 负责测试开发相关功能的设计与编码；\n2. 基于JMeter完成模块开发",
            "1. 本科\n2. 掌握 Pytest",
            "五险一金、年度体检",
            "platform",
        )
        self.assertIn("负责测试开发相关功能的设计与编码", cleaned.description)
        self.assertIn("本科", cleaned.requirement)
        self.assertEqual(cleaned.welfare, "五险一金、年度体检")
        self.assertFalse(cleaned.salary_estimated)
        self.assertEqual(cleaned.source_label, "企业发布")

    def test_unified_template_no_json(self):
        text = build_job_text(
            {
                "title": "营销产品经理",
                "company_name": "懂车帝",
                "city": "北京",
                "tech_direction": "产品经理",
                "salary_min": 13000,
                "salary_max": 23000,
                "salary_months": 12,
                "education": 2,
                "experience_req": 0,
                "skills": "产品",
                "description": EXT_DESC,
                "requirement": EXT_REQ,
                "welfare": "投递链接: https://dcar.jobs.feishu.cn/x",
                "data_source": "ext_ats",
            }
        )
        self.assertIn("# 营销产品经理", text)
        self.assertIn("公司：懂车帝", text)
        self.assertIn("城市：北京", text)
        self.assertIn("技能：产品", text)
        self.assertIn("要求：", text)
        self.assertIn("职责：", text)
        self.assertIn("3年以上产品经验", text)
        self.assertIn("估算，以官网为准", text)
        self.assertIn("外部扩充库", text)
        self.assertNotIn("provenance", text)
        self.assertNotIn("post_id", text)
        self.assertNotIn("【抓取时间】", text)
        self.assertNotIn("投递链接", text)


class DiversityTest(unittest.TestCase):
    def _hit(self, job, company, score=0.9, doc_type=7):
        return {
            "doc_type": doc_type,
            "doc_key": f"job:{job}",
            "source_id": job,
            "company": company,
            "score": score,
            "title": f"job{job}",
        }

    def test_limits_per_company_and_job(self):
        hits = [
            self._hit(1, "海盐电子商务有限公司"),
            self._hit(1, "海盐电子商务有限公司"),  # same job, second chunk
            self._hit(2, "海盐电子商务有限公司"),
            self._hit(3, "海盐电子商务有限公司"),
            self._hit(4, "阿里巴巴"),
            self._hit(5, "网易"),
            self._hit(6, "字节跳动"),
        ]
        out = diversify_hits(hits, top_k=4, per_job=1, per_company=2)
        companies = [h["company"] for h in out]
        keys = [h["doc_key"] for h in out]
        self.assertEqual(len(out), 4)
        self.assertEqual(keys[:2], ["job:1", "job:2"])
        self.assertEqual(companies.count("海盐电子商务有限公司"), 2)
        self.assertIn("阿里巴巴", companies)
        self.assertIn("网易", companies)
        self.assertEqual(len(set(keys)), 4)

    def test_policy_chunks_not_limited(self):
        hits = [
            {"doc_type": 6, "doc_key": "kb:a", "company": "", "title": "三方"},
            {"doc_type": 6, "doc_key": "kb:b", "company": "", "title": "合同"},
            self._hit(1, "A"),
        ]
        out = diversify_hits(hits, top_k=3, per_job=1, per_company=1)
        self.assertEqual([h["doc_key"] for h in out], ["kb:a", "kb:b", "job:1"])

    def test_fills_from_leftover_if_short(self):
        hits = [self._hit(i, "同一家") for i in range(1, 6)]
        out = diversify_hits(hits, top_k=4, per_job=1, per_company=2)
        # first keep 2 (company cap), then fill 2 more from leftover
        self.assertEqual(len(out), 4)
        self.assertEqual(out[0]["doc_key"], "job:1")
        self.assertEqual(out[1]["doc_key"], "job:2")
        self.assertEqual(out[2]["doc_key"], "job:3")

    def test_disable_with_zero(self):
        hits = [self._hit(1, "A"), self._hit(2, "A"), self._hit(3, "A")]
        out = diversify_hits(hits, top_k=3, per_job=0, per_company=0)
        self.assertEqual(len(out), 3)


if __name__ == "__main__":
    unittest.main()
