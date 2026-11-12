"""职位知识库增量同步：在招外部岗位纳入索引文本，过期岗位会被剔除。

运行：cd ai-service && ../.venv/bin/python -m unittest -v tests.test_job_sync
需本机 MySQL。默认不写入生产 Chroma，除非设置 RAG_TEST_WRITE_SYNC=1。
"""

from __future__ import annotations

import os
import unittest

from app.rag.ingest import load_job_texts, load_jobs, sync_jobs, _source_label, _job_text
from app.spark.db import connect


def _one(sql: str, params=None) -> dict | None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()
    finally:
        conn.close()


class JobSourceTextTest(unittest.TestCase):
    def test_source_labels(self):
        self.assertIn("外部来源", _source_label("self_crawl"))
        self.assertIn("外部扩充库", _source_label("ext_ats"))
        self.assertEqual(_source_label("platform"), "企业发布")

    def test_estimated_salary_in_external_job_text(self):
        row = {
            "title": "产品经理",
            "company_name": "懂车帝",
            "city": "北京",
            "tech_direction": "产品经理",
            "salary_min": 13000,
            "salary_max": 23000,
            "salary_months": 12,
            "education": 2,
            "experience_req": 0,
            "skills": "产品",
            "description": "负责产品",
            "requirement": "本科",
            "welfare": "",
            "data_source": "ext_ats",
        }
        text = _job_text(row)
        self.assertIn("飞书招聘公开门户（外部扩充库）", text)
        self.assertIn("估算，以官网为准", text)
        self.assertIn("懂车帝", text)
        self.assertIn("13000-23000", text)

    def test_platform_job_not_estimated(self):
        row = {
            "title": "Java",
            "company_name": "测试公司",
            "city": "杭州",
            "tech_direction": "后端开发",
            "salary_min": 10000,
            "salary_max": 15000,
            "salary_months": 13,
            "education": 2,
            "experience_req": 1,
            "skills": "Java",
            "description": "开发",
            "requirement": "本科",
            "welfare": "五险一金",
            "data_source": "platform",
        }
        text = _job_text(row)
        self.assertIn("13薪", text)
        self.assertIn("企业发布", text)
        self.assertNotIn("估算", text)


class LoadLiveJobsTest(unittest.TestCase):
    def test_ext_ats_job_loaded_with_metadata(self):
        row = _one(
            """
            SELECT p.id FROM job_position p
            INNER JOIN ent_company c ON c.id = p.company_id AND c.deleted = 0 AND c.audit_status = 1
            WHERE p.deleted = 0 AND p.shelf_status = 1 AND p.audit_status = 1
              AND p.data_source = 'ext_ats'
            ORDER BY p.id LIMIT 1
            """
        )
        if not row:
            self.skipTest("库中没有在招的外部扩充职位")
        job_id = int(row["id"])
        items = load_job_texts(ids=[job_id])
        self.assertEqual(len(items), 1, items)
        item = items[0]
        self.assertEqual(item["data_source"], "ext_ats")
        self.assertTrue(item["salary_estimated"])
        self.assertIn("外部扩充库", item["text"])
        self.assertIn("估算", item["text"])
        docs = load_jobs(ids=[job_id])
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].meta.get("data_source"), "ext_ats")
        self.assertTrue(docs[0].meta.get("salary_estimated"))
        self.assertEqual(docs[0].source_id, job_id)

    def test_deleted_job_not_live(self):
        row = _one(
            """
            SELECT id FROM job_position
            WHERE (deleted = 1 OR shelf_status = 0 OR audit_status <> 1)
            ORDER BY id LIMIT 1
            """
        )
        if not row:
            self.skipTest("没有下架或已删除的职位可测")
        items = load_job_texts(ids=[int(row["id"])])
        self.assertEqual(items, [])

    def test_normalize_ids(self):
        from app.rag.ingest import _normalize_ids
        self.assertEqual(_normalize_ids([]), [])
        self.assertEqual(_normalize_ids(None), [])
        self.assertEqual(_normalize_ids([1, 1, 0, -2, "3"]), [1, 3])


@unittest.skipUnless(os.environ.get("RAG_TEST_WRITE_SYNC") == "1", "默认不写入生产向量库")
class SyncWriteTest(unittest.TestCase):
    def test_prune_stale_and_upsert_ext(self):
        stale = _one(
            """
            SELECT id FROM job_position
            WHERE deleted = 1 OR shelf_status = 0 OR audit_status <> 1
            ORDER BY id LIMIT 1
            """
        )
        live = _one(
            """
            SELECT id FROM job_position
            WHERE deleted = 0 AND shelf_status = 1 AND audit_status = 1 AND data_source = 'ext_ats'
            ORDER BY id LIMIT 1
            """
        )
        ids = []
        if stale:
            ids.append(int(stale["id"]))
        if live:
            ids.append(int(live["id"]))
        if not ids:
            self.skipTest("没有可同步的职位")
        result = sync_jobs(ids)
        self.assertIn("pruned", result)
        if stale:
            self.assertGreaterEqual(result["pruned"], 0)
        if live:
            self.assertGreaterEqual(result["documents"] + result.get("skipped", 0), 1)


if __name__ == "__main__":
    unittest.main()
