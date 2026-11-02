"""P1-1：求职方向归一、方向冲突降权、推荐理由真实且不重复。

    cd ai-service && ../.venv/bin/python -m unittest tests.test_recommend_direction -v

Spark 用例在本地 SparkSession 上校验列表达式与纯 Python 口径（实时推荐使用）逐行一致。
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.spark.recommend_eval import (  # noqa: E402
    DIR_FACTOR,
    DIRECTIONS,
    build_reason,
    direction_relation,
    normalize_direction,
    skill_detail,
)

SAMPLES = [
    "Java后端", "后端工程师", "Java后端开发", "服务端开发", "大数据开发", "数据产品经理", "推荐算法",
    "前端", "Web前端", "UI设计师", "游戏策划", "iOS开发", "C++开发", "Go开发", "软件开发", "",
    "mail", "Golang", "AI应用开发", "嵌入式软件", "SRE", "测试工程师", "云原生", " 后端开发 ", "游戏体验设计",
] + list(DIRECTIONS)


def _reason(**kw):
    base = dict(
        hit_skills=[], missing_skills=[], hit_count=0, job_tag_count=0, relation="none",
        user_direction="后端开发", job_direction="后端开发", city="", city_match=False,
        major="", major_match=False, cf_score=0.0, popular=False, variant=0,
    )
    base.update(kw)
    return build_reason(**base)


class DirectionTest(unittest.TestCase):
    def test_normalize(self):
        expect = {
            "Java后端": "后端开发", "后端工程师": "后端开发", "服务端开发": "后端开发", "Go开发": "后端开发",
            "大数据开发": "数据开发", "数据产品经理": "产品经理", "推荐算法": "算法工程", "Web前端": "前端开发",
            "UI设计师": "UI设计", "iOS开发": "移动开发", "游戏体验设计": "UI设计", "": "", "mail": "",
        }
        for text, direction in expect.items():
            self.assertEqual(normalize_direction(text), direction, text)
        for direction in DIRECTIONS:
            self.assertEqual(normalize_direction(direction), direction)

    def test_relation(self):
        self.assertEqual(direction_relation("Java后端", "后端开发"), "same")
        self.assertEqual(direction_relation("Java后端", "云原生开发"), "near")
        self.assertEqual(direction_relation("Java后端", "UI设计"), "far")
        self.assertEqual(direction_relation("", "UI设计"), "none")
        self.assertLess(DIR_FACTOR["far"], DIR_FACTOR["near"])
        self.assertEqual(DIR_FACTOR["none"], 1.0)


class ReasonTest(unittest.TestCase):
    def test_no_fake_skill_claim(self):
        text = _reason(hit_count=0, job_tag_count=3, missing_skills=["Kafka", "Redis"], relation="same")
        self.assertNotIn("掌握", text)
        self.assertIn("Kafka", text)
        self.assertIn("还没有", text)

    def test_skill_counts_truthful(self):
        text = _reason(hit_skills=["Java", "MySQL"], hit_count=2, job_tag_count=4, missing_skills=["Redis"], relation="same")
        self.assertIn("Java", text)
        self.assertTrue("2" in text and "4" in text)
        self.assertIn("Redis", text)

    def test_far_direction_is_disclosed(self):
        text = _reason(relation="far", user_direction="Java后端", job_direction="UI设计", cf_score=80)
        self.assertIn("不是你期望的Java后端方向", text)
        self.assertNotIn("符合你期望", text)

    def test_adjacent_cards_differ(self):
        kw = dict(hit_skills=["Java", "Spring Boot"], hit_count=2, job_tag_count=3, relation="same", cf_score=70)
        texts = [_reason(variant=v, **kw) for v in range(6)]
        for a, b in zip(texts, texts[1:]):
            self.assertNotEqual(a, b)
        self.assertGreaterEqual(len(set(texts)), 3)

    def test_skill_detail(self):
        names = {1: "Java", 2: "MySQL", 3: "Redis", 4: "Kafka"}
        detail = skill_detail({1: 4.0, 2: 3.0, 9: 5.0}, {1, 2, 3, 4}, names)
        self.assertEqual(detail["hits"], ["Java", "MySQL"])
        self.assertEqual(detail["missing"], ["Kafka", "Redis"])
        self.assertEqual((detail["hit_count"], detail["job_tag_count"]), (2, 4))
        empty = skill_detail({9: 5.0}, {1, 2}, names)
        self.assertEqual((empty["hit_count"], empty["hits"], empty["percent"]), (0, [], 0))


@unittest.skipIf(os.environ.get("SKIP_SPARK_TESTS") == "1", "SKIP_SPARK_TESTS=1")
class SparkParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pyspark.sql import SparkSession

        cls.spark = (
            SparkSession.builder.master("local[1]").appName("test-recommend-direction")
            .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "1").getOrCreate()
        )

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_normalize_expr_matches_python(self):
        from pyspark.sql import functions as F

        from app.spark.recommend_cf import direction_norm_expr

        frame = self.spark.createDataFrame([(s,) for s in SAMPLES], ["d"])
        got = {r["d"]: r["n"] for r in frame.select("d", direction_norm_expr(F.col("d")).alias("n")).collect()}
        for text in SAMPLES:
            self.assertEqual(got[text], normalize_direction(text), text)

    def test_content_and_fusion_match_online(self):
        from pyspark.sql import functions as F

        from app.spark import recommend_cf as CF
        from app.spark.recommend_online import _content_one, _fuse

        users = [(1, 2, "Java后端", "杭州", "软件工程"), (2, 2, "", "北京", ""), (3, 1, "前端", "上海", "计算机")]
        jobs = [(11, 2, "后端开发", "杭州", "Java后端 软件工程"), (12, 0, "UI设计", "杭州", "游戏体验设计"), (13, 3, "云原生开发", "北京", "K8s")]
        rows = []
        for u in users:
            for j in jobs:
                rows.append((u[0], j[0], u[1], u[2], u[3], u[4], j[1], j[2], j[3], j[4], 60.0, 30.0, 3.0, 1.0))
        frame = self.spark.createDataFrame(
            rows,
            ["user_id", "position_id", "u_edu", "u_dir", "u_city", "u_major", "j_edu", "j_dir", "j_city", "j_text", "cf_mm", "popularity", "activity", "cf_hi"],
        )
        tag_cos = self.spark.createDataFrame([(1, 11, 0.6), (3, 12, 0.2)], ["user_id", "position_id", "tag_cos"])
        scored = CF.with_content(frame, tag_cos).withColumn("hybrid", CF.fused_expr(0.45, "linear", False))
        got = {(r["user_id"], r["position_id"]): (r["content"], r["hybrid"], r["dir_rel"]) for r in scored.collect()}
        names = {1: "t"}
        for u in users:
            for j in jobs:
                percent = {(1, 11): 60, (3, 12): 20}.get((u[0], j[0]), 0)
                # 用一个与 tag_cos 等价的技能向量：单标签熟练度任意，职位标签数 = 1/(cos^2)
                skills, tags = ({1: 1.0}, {1} | set(range(100, 100 + int(round(1 / (percent / 100) ** 2)) - 1))) if percent else ({}, set())
                job = {"techDirection": j[2], "city": j[3], "education": j[1], "title": j[4], "requirement": "", "tags": list(tags)}
                rel = direction_relation(u[2], j[2])
                content = _content_one(skills, u[4], u[2], u[3], u[1], job, names, rel)
                hybrid = _fuse(60.0, content, 30.0, 3.0, False, 0.45, "linear", False, DIR_FACTOR[rel])
                spark_content, spark_hybrid, spark_rel = got[(u[0], j[0])]
                self.assertEqual(spark_rel, rel, (u, j))
                self.assertAlmostEqual(spark_content, content, delta=1.5, msg=(u, j))
                self.assertAlmostEqual(spark_hybrid, hybrid, delta=1.0, msg=(u, j))
        # 方向冲突的职位即使协同分相同也排在同方向职位后面
        self.assertGreater(got[(1, 11)][1], got[(1, 12)][1])


if __name__ == "__main__":
    unittest.main()
