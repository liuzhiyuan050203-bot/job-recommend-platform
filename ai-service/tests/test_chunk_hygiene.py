"""入库切片卫生：去掉示例免责声明，合并过短小节。

运行：cd ai-service && ../.venv/bin/python -m unittest -v tests.test_chunk_hygiene
"""

from __future__ import annotations

import unittest

from app.rag.chunking import is_disclaimer, merge_short_sections, strip_disclaimer
from app.rag.ingest import KNOWLEDGE_DIR, _chunks_of


class DisclaimerTest(unittest.TestCase):
    LINE = "> 示例资料：本文为毕业设计演示用的通用示例内容，具体以学校和当地最新政策为准"

    def test_is_disclaimer(self):
        self.assertTrue(is_disclaimer(self.LINE))
        self.assertFalse(is_disclaimer("三方协议由毕业生、用人单位和学校签订，不等于劳动合同。"))
        self.assertFalse(is_disclaimer(""))

    def test_strip_keeps_body(self):
        text = self.LINE + "\n\n# 三方协议\n\n## 是什么\n\n三方协议不等于劳动合同。"
        cleaned = strip_disclaimer(text)
        self.assertNotIn("示例资料", cleaned)
        self.assertNotIn("演示用", cleaned)
        self.assertIn("三方协议不等于劳动合同", cleaned)
        self.assertIn("# 三方协议", cleaned)

    def test_knowledge_files_have_no_disclaimer_chunks(self):
        self.assertTrue(KNOWLEDGE_DIR.is_dir())
        total = 0
        for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
            chunks = _chunks_of(path.read_text(encoding="utf-8"))
            self.assertGreater(len(chunks), 0, path.name)
            total += len(chunks)
            for chunk in chunks:
                self.assertFalse(is_disclaimer(chunk.content), f"{path.name} {chunk.section}")
                self.assertNotIn("毕业设计演示用的通用示例内容", chunk.content)
                self.assertNotIn("演示用示例", chunk.content)
        self.assertGreaterEqual(total, 70)

    def test_merge_short_sections(self):
        parts = [
            ("签约流程", "用人单位在系统发起邀约，学生核对单位名称、岗位和薪酬后接受。" * 2),
            ("短节", "注意时效。"),
            ("改派", "改派需要在规定期限内向学校就业中心提交书面材料，过期后档案会回到生源地，学生要提前确认截止时间。"),
        ]
        merged = merge_short_sections(parts, min_len=40)
        self.assertEqual(len(merged), 2)
        self.assertIn("注意时效", merged[0][1])
        self.assertEqual(merged[1][0], "改派")

    def test_short_standalone_document_kept(self):
        text = "# 面试复习重点\n\n涵盖Java、大数据与算法核心考点。"
        chunks = _chunks_of(text)
        self.assertEqual(len(chunks), 1)
        self.assertIn("Java", chunks[0].content)

    def test_disclaimer_only_yields_nothing(self):
        self.assertEqual(_chunks_of(self.LINE), [])


if __name__ == "__main__":
    unittest.main()
