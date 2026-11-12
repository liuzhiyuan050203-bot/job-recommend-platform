"""近域拒答：领域意图与相关性门槛。

运行：cd ai-service && ../.venv/bin/python -m unittest -v tests.test_scope_gate
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.agent import chat
from app.rag.scope import (
    DEFAULT_OUT_COSINE,
    DEFAULT_UNKNOWN_COSINE,
    apply_scope_gate,
    decide_scope,
    domain_intent,
    refusal_answer,
)

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_V2 = ROOT / "experiments" / "rag_eval" / "questions_v2.jsonl"
QUESTIONS_EASY = ROOT / "experiments" / "rag_eval" / "questions.jsonl"
QUESTIONS_SCOPE = ROOT / "experiments" / "rag_eval" / "questions_scope.jsonl"


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _hit(score: float, title: str = "三方协议FAQ", section: str = "想违约怎么办") -> dict:
    return {"score": score, "title": title, "section": section, "content": "示例", "rrf": 0.1}


class DomainIntentTest(unittest.TestCase):
    def test_heldout_near_domain_is_out(self):
        expected = {
            "r01": "考研报名费怎么交，在哪个网站缴费？",
            "r02": "英语四级下一次考试是几月，准考证在哪打印？",
            "r03": "第一次申办因私护照要带哪些材料、在哪个派出所预约？",
            "r04": "国家公务员考试报名入口是哪个网址，应届生岗位怎么筛选？",
            "r05": "北京积分落户申报系统今年几点开放，社保要满多少年？",
        }
        for row in _load_jsonl(QUESTIONS_V2):
            if row.get("id") in expected:
                self.assertEqual(row["question"], expected[row["id"]])
                self.assertEqual("out", domain_intent(row["question"]), row["question"])


    def test_dev_and_heldout_split_file(self):
        rows = _load_jsonl(QUESTIONS_SCOPE)
        dev = [r for r in rows if r.get("split") == "dev"]
        held = [r for r in rows if r.get("split") == "heldout"]
        self.assertGreaterEqual(len(dev), 8)
        self.assertEqual(len(held), 5)
        for row in rows:
            self.assertEqual("out", domain_intent(row["question"]), row["question"])

    def test_in_scope_policy_not_out(self):
        rows = [r for r in _load_jsonl(QUESTIONS_V2) if r.get("set") in {"hard", "multihop"}]
        self.assertGreaterEqual(len(rows), 11)
        for row in rows:
            self.assertNotEqual("out", domain_intent(row["question"]), row["question"])

    def test_easy_policy_not_out(self):
        for row in _load_jsonl(QUESTIONS_EASY):
            if row.get("type") in {"offtopic", "unanswerable"} or not row.get("gold"):
                continue
            self.assertNotEqual("out", domain_intent(row["question"]), row["question"])

    def test_kaogong_default_is_not_out(self):
        # 「因为考公不想去了」是三方违约情境，不能当成国考报名拒答
        question = "已经在网上点了接受，后来因为考公不想去了，一般要先走什么手续、钱怎么谈？"
        self.assertEqual("in", domain_intent(question))

    def test_hukou_employment_is_in_points_is_out(self):
        self.assertEqual(
            "in",
            domain_intent("毕业还没找到单位，档案和户口能不能先转回老家的人才中心，以后签约再调走？"),
        )
        self.assertEqual("in", domain_intent("包落户"))
        self.assertEqual("in", domain_intent("三支一扶"))
        self.assertEqual("out", domain_intent("上海积分落户社保要满多少年才能申报？"))

    def test_short_unknown_keyword_treated_as_in(self):
        self.assertEqual("in", domain_intent("一类账户"))
        self.assertEqual("in", domain_intent("模拟数据"))
        # 长句且不在范围内仍是 unknown
        self.assertEqual("unknown", domain_intent("今天中午食堂有什么菜，窗口几点关门？"))


class ScopeDecisionTest(unittest.TestCase):
    def test_out_with_medium_score_refused(self):
        decision = decide_scope("考研报名费怎么交", [_hit(0.66)])
        self.assertTrue(decision.refuse)
        self.assertEqual("out", decision.intent)
        self.assertEqual("out_of_scope", decision.reason)

    def test_out_with_very_high_score_kept(self):
        decision = decide_scope("考研报名费怎么交", [_hit(DEFAULT_OUT_COSINE + 0.05)])
        self.assertFalse(decision.refuse)
        self.assertEqual("out_but_strong", decision.reason)

    def test_in_scope_kept_even_at_modest_score(self):
        decision = decide_scope("三方协议违约金怎么谈", [_hit(0.51)])
        self.assertFalse(decision.refuse)
        self.assertEqual("in", decision.intent)

    def test_unknown_below_threshold_refused(self):
        decision = decide_scope("今天中午食堂有什么菜，窗口几点关门？", [_hit(DEFAULT_UNKNOWN_COSINE - 0.05)])
        self.assertTrue(decision.refuse)
        self.assertEqual("unknown", decision.intent)
        self.assertEqual("weak_relevance", decision.reason)

    def test_unknown_above_threshold_kept(self):
        decision = decide_scope("今天中午食堂有什么菜，窗口几点关门？", [_hit(DEFAULT_UNKNOWN_COSINE + 0.05)])
        self.assertFalse(decision.refuse)

    def test_empty_hits_refused(self):
        decision = decide_scope("三方协议是什么", [])
        self.assertTrue(decision.refuse)
        self.assertEqual("no_hits", decision.reason)

    def test_gate_drops_hits_for_passport(self):
        hits = [_hit(0.61, title="档案与户口FAQ", section="户口迁移")]
        self.assertEqual([], apply_scope_gate("第一次申办因私护照要带哪些材料", hits))
        self.assertEqual(hits, apply_scope_gate("第一次申办因私护照要带哪些材料", hits, enabled=False))

    def test_gate_keeps_in_scope(self):
        hits = [_hit(0.55)]
        self.assertEqual(hits, apply_scope_gate("三方协议和劳动合同是一回事吗", hits))


class RefusalAnswerTest(unittest.TestCase):
    def test_message_has_scope_and_suggestions(self):
        text = refusal_answer("student")
        self.assertIn("知识库暂无相关资料", text)
        self.assertIn("三方协议", text)
        self.assertIn("学校就业指导中心", text)
        self.assertIn(text, chat._no_hit_text("student"))

    def test_company_has_no_student_phrasing(self):
        text = refusal_answer("company")
        self.assertIn("知识库暂无相关资料", text)
        self.assertNotIn("学校就业指导中心", text)
        self.assertIn("招聘看板", text)
        self.assertEqual(text, chat._no_hit_text("company"))


if __name__ == "__main__":
    unittest.main()
