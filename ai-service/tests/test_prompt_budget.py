"""提示词上下文预算：本地小模型保持原值，云端默认放大，显式配置优先。

运行：cd ai-service && ../.venv/bin/python -m unittest -v tests.test_prompt_budget
"""

from __future__ import annotations

import unittest

from app.agent import chat
from app.core.config import settings


class _Patch:
    def __init__(self, **values):
        self.values = values
        self._orig: dict = {}

    def __enter__(self):
        for key, value in self.values.items():
            self._orig[key] = getattr(settings, key)
            object.__setattr__(settings, key, value)
        return settings

    def __exit__(self, *exc):
        for key, value in self._orig.items():
            object.__setattr__(settings, key, value)


class PromptBudgetTest(unittest.TestCase):
    def test_local_ollama_keeps_original(self):
        with _Patch(
            LLM_PROVIDER="ollama",
            LLM_BASE_URL="http://127.0.0.1:11434/v1",
            RAG_PROMPT_CHUNK_CHARS=0,
            RAG_PROMPT_CHAR_BUDGET=0,
            RAG_PROMPT_TOOL_CHARS=0,
        ):
            self.assertFalse(settings.is_cloud_llm)
            self.assertEqual(settings.prompt_chunk_chars, 300)
            self.assertEqual(settings.prompt_char_budget, 1500)
            self.assertEqual(settings.prompt_tool_chars, 700)

    def test_openai_compatible_local_is_not_cloud(self):
        with _Patch(
            LLM_PROVIDER="openai_compatible",
            LLM_BASE_URL="http://127.0.0.1:11434/v1",
            RAG_PROMPT_CHUNK_CHARS=0,
            RAG_PROMPT_CHAR_BUDGET=0,
            RAG_PROMPT_TOOL_CHARS=0,
        ):
            self.assertFalse(settings.is_cloud_llm)
            self.assertEqual(settings.prompt_char_budget, 1500)

    def test_gemini_and_openai_use_larger_defaults(self):
        for provider, base in [("gemini", ""), ("openai", "https://api.openai.com/v1")]:
            with self.subTest(provider=provider):
                with _Patch(
                    LLM_PROVIDER=provider,
                    LLM_BASE_URL=base,
                    RAG_PROMPT_CHUNK_CHARS=0,
                    RAG_PROMPT_CHAR_BUDGET=0,
                    RAG_PROMPT_TOOL_CHARS=0,
                ):
                    self.assertTrue(settings.is_cloud_llm)
                    self.assertEqual(settings.prompt_chunk_chars, 800)
                    self.assertEqual(settings.prompt_char_budget, 6000)
                    self.assertEqual(settings.prompt_tool_chars, 2000)

    def test_explicit_override_wins(self):
        with _Patch(
            LLM_PROVIDER="gemini",
            LLM_BASE_URL="",
            RAG_PROMPT_CHUNK_CHARS=400,
            RAG_PROMPT_CHAR_BUDGET=2500,
            RAG_PROMPT_TOOL_CHARS=900,
        ):
            self.assertTrue(settings.is_cloud_llm)
            self.assertEqual(settings.prompt_chunk_chars, 400)
            self.assertEqual(settings.prompt_char_budget, 2500)
            self.assertEqual(settings.prompt_tool_chars, 900)

    def test_fit_prompt_respects_budget(self):
        chunks = [
            {"title": f"资料{i}", "section": "节", "content": "薪资范围与岗位说明。" * 80}
            for i in range(6)
        ]
        with _Patch(
            LLM_PROVIDER="ollama",
            LLM_BASE_URL="http://127.0.0.1:11434/v1",
            RAG_PROMPT_CHUNK_CHARS=0,
            RAG_PROMPT_CHAR_BUDGET=0,
            RAG_PROMPT_TOOL_CHARS=0,
        ):
            text = chat._fit_prompt("杭州 Java 月薪多少", [], chunks, "预测 18000", "引用在招职位")
            self.assertLessEqual(len(text), 1500)
            self.assertIn("【资料】", text)
        with _Patch(
            LLM_PROVIDER="gemini",
            LLM_BASE_URL="",
            RAG_PROMPT_CHUNK_CHARS=0,
            RAG_PROMPT_CHAR_BUDGET=0,
            RAG_PROMPT_TOOL_CHARS=0,
        ):
            text = chat._fit_prompt("杭州 Java 月薪多少", [], chunks, "预测 18000", "引用在招职位")
            self.assertGreater(len(text), 1500)
            self.assertLessEqual(len(text), 6000)
            self.assertIn("资料1", text)
            self.assertIn("薪资范围", text)


if __name__ == "__main__":
    unittest.main()
