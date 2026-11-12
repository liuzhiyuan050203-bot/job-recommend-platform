"""查询改写、多跳拆分与多路 RRF 融合。

运行：cd ai-service && ../.venv/bin/python -m unittest -v tests.test_rewrite
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.rag.rewrite import (
    apply_synonyms,
    decompose,
    expand_queries,
    is_job_only,
    llm_rewrites,
    merge_multi_query,
    rrf_fuse_weighted,
    rule_rewrites,
)

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_V2 = ROOT / "experiments" / "rag_eval" / "questions_v2.jsonl"


def _load_v2() -> dict[str, dict]:
    rows = {}
    for line in QUESTIONS_V2.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["id"]] = row
    return rows


class SynonymAndDecomposeTest(unittest.TestCase):
    def test_paraphrase_synonyms(self):
        text = apply_synonyms("学校、用人单位和我本人签的那份就业意向书，和入职后要签的劳动合约是一回事吗？")
        self.assertIn("三方协议", text)
        self.assertIn("劳动合同", text)
        self.assertNotIn("就业意向书", text)
        self.assertNotIn("劳动合约", text)

    def test_probation_synonym(self):
        text = apply_synonyms("还在考察期内自己不想干了，需要提前多久告诉公司？过了考察期呢？")
        self.assertIn("试用期内", text)
        self.assertIn("试用期", text)
        self.assertNotIn("考察期", text)

    def test_service_period_not_duplicated(self):
        text = apply_synonyms("正式劳动合约里因为专项培训约定的服务期")
        self.assertIn("劳动合同", text)
        self.assertIn("专项培训", text)
        self.assertEqual(text.count("服务期"), 1)

    def test_multihop_m01_splits_two_sides(self):
        q = _load_v2()["m01"]["question"]
        queries = expand_queries(q, allow_llm=False)
        self.assertGreaterEqual(len(queries), 3)
        self.assertEqual(queries[0], q)
        blob = " ".join(queries)
        self.assertIn("三方协议", blob)
        self.assertIn("试用期", blob)
        # 两侧都应作为独立查询出现
        self.assertTrue(any("反悔" in item and "离职" not in item for item in queries[1:]))
        self.assertTrue(any("离职" in item and "反悔" not in item for item in queries[1:]))

    def test_multihop_m02_splits_penalty_and_service(self):
        q = _load_v2()["m02"]["question"]
        queries = expand_queries(q, allow_llm=False)
        blob = " ".join(queries)
        self.assertIn("三方协议", blob)
        self.assertIn("劳动合同", blob)
        self.assertIn("服务期", blob)
        self.assertTrue(any("违约" in item and "服务期" not in item for item in queries[1:]))

    def test_multihop_m03_splits_company_and_student(self):
        q = _load_v2()["m03"]["question"]
        parts = decompose(q)
        self.assertGreaterEqual(len(parts), 2)
        self.assertTrue(any("违规" in p or "职位" in p for p in parts))
        blob = " ".join(expand_queries(q, allow_llm=False))
        self.assertIn("限制性别", blob)

    def test_simple_job_query_not_rewritten(self):
        q = "懂车帝在招哪些产品经理？"
        self.assertEqual(expand_queries(q, allow_llm=False), [q])
        self.assertEqual(decompose(q), [])

    def test_paraphrase_not_decomposed(self):
        q = _load_v2()["h01"]["question"]
        self.assertEqual(decompose(q), [])
        queries = expand_queries(q, allow_llm=False)
        self.assertEqual(len(queries), 2)
        self.assertIn("三方协议", queries[1])

    def test_rewrite_can_be_disabled(self):
        q = "还在考察期内自己不想干了？"
        with patch("app.rag.rewrite.settings") as mocked:
            mocked.RAG_QUERY_REWRITE = False
            mocked.RAG_QUERY_REWRITE_LLM = "false"
            mocked.is_cloud_llm = False
            self.assertEqual(expand_queries(q, allow_llm=False), [q])

    def test_is_job_only(self):
        self.assertTrue(is_job_only([7]))
        self.assertTrue(is_job_only([7, 7]))
        self.assertFalse(is_job_only([1, 6]))
        self.assertFalse(is_job_only(None))
        self.assertFalse(is_job_only([]))


class MergeRrfTest(unittest.TestCase):
    def test_fuse_prefers_docs_in_both_lists(self):
        a = [
            {"chroma_id": "x", "score": 0.6, "section": "A"},
            {"chroma_id": "y", "score": 0.7, "section": "B"},
        ]
        b = [
            {"chroma_id": "y", "score": 0.8, "section": "B"},
            {"chroma_id": "z", "score": 0.9, "section": "C"},
        ]
        merged = merge_multi_query([a, b], limit=3)
        ids = [h["chroma_id"] for h in merged]
        # y 在两路都出现，RRF 应最高；余弦取较大值 0.8
        self.assertEqual(ids[0], "y")
        self.assertAlmostEqual(merged[0]["score"], 0.8)
        self.assertEqual(set(ids), {"x", "y", "z"})
        self.assertGreater(merged[0]["rrf"], merged[1]["rrf"])


    def test_original_top1_not_displaced(self):
        # 原问第一是 gold，改写子问把另一篇推到第一：加权后 gold 仍应第一
        original = [
            {"chroma_id": "gold", "score": 0.70},
            {"chroma_id": "other", "score": 0.65},
            {"chroma_id": "noise", "score": 0.60},
        ]
        rewrite = [
            {"chroma_id": "other", "score": 0.90},
            {"chroma_id": "gold", "score": 0.80},
        ]
        merged = merge_multi_query([original, rewrite], limit=3)
        self.assertEqual(merged[0]["chroma_id"], "gold")

    def test_weighted_rrf_equals_unweighted_when_all_ones(self):
        ranks = [["a", "b"], ["b", "c"]]
        from app.rag.bm25 import rrf_fuse
        self.assertEqual(rrf_fuse_weighted(ranks, [1, 1]), rrf_fuse(list(ranks)))

    def test_single_list_keeps_order(self):
        hits = [{"chroma_id": "a", "score": 0.5}, {"chroma_id": "b", "score": 0.4}]
        self.assertEqual([h["chroma_id"] for h in merge_multi_query([hits], 2)], ["a", "b"])

    def test_empty(self):
        self.assertEqual(merge_multi_query([[], []], 4), [])


class LlmRewriteGuardTest(unittest.TestCase):
    def test_auto_skips_on_local_provider(self):
        with patch("app.rag.rewrite.settings") as mocked:
            mocked.RAG_QUERY_REWRITE_LLM = "auto"
            mocked.is_cloud_llm = False
            self.assertEqual(llm_rewrites("三方协议违约金怎么算"), [])

    def test_explicit_true_calls_llm_and_parses_lines(self):
        class FakeMsg:
            content = "三方协议解约步骤\n试用期内离职提前通知\n1. 带编号也应去掉"

        class FakeLlm:
            def invoke(self, _prompt):
                return FakeMsg()

        with patch("app.rag.rewrite.settings") as mocked, patch(
            "app.core.llm.is_available", return_value=True
        ), patch("app.core.llm.get_llm", return_value=FakeLlm()):
            mocked.RAG_QUERY_REWRITE_LLM = "true"
            mocked.is_cloud_llm = False
            lines = llm_rewrites("已经签了就业协议后又反悔，和试用期离职有何不同")
        self.assertIn("三方协议解约步骤", lines)
        self.assertIn("试用期内离职提前通知", lines)
        self.assertIn("带编号也应去掉", lines)
        self.assertLessEqual(len(lines), 3)


if __name__ == "__main__":
    unittest.main()
