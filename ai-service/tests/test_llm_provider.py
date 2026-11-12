"""大模型工厂：按 LLM_PROVIDER 选择实现、配置传递，以及缺密钥/无效密钥时的降级。

不发起真实云端请求。运行：
  cd ai-service && ../.venv/bin/python -m unittest -v tests.test_llm_provider
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from langchain_openai import ChatOpenAI

from app.core import llm as llm_mod
from app.core.config import settings
from app.core.llm import (
    LLMConfigError,
    get_chat_model,
    health,
    normalize_provider,
    resolved_base_url,
)


def _clear_health_cache() -> None:
    llm_mod.llm_provider.reset_health_cache()


class _SettingsPatch:
    """临时改写 settings 字段，退出时恢复并清空探活缓存。"""

    def __init__(self, **values):
        self.values = values
        self._orig: dict = {}

    def __enter__(self):
        for key, value in self.values.items():
            self._orig[key] = getattr(settings, key)
            setattr(settings, key, value)
        _clear_health_cache()
        return self

    def __exit__(self, *exc):
        for key, value in self._orig.items():
            setattr(settings, key, value)
        _clear_health_cache()
        return False


class NormalizeProviderTest(unittest.TestCase):
    def test_default_and_aliases(self):
        with _SettingsPatch(LLM_PROVIDER="ollama", LLM_BASE_URL="http://127.0.0.1:11434/v1"):
            self.assertEqual(normalize_provider(), "ollama")
        with _SettingsPatch(LLM_PROVIDER="openai_compatible", LLM_BASE_URL="http://127.0.0.1:11434/v1"):
            self.assertEqual(normalize_provider(), "ollama")
        with _SettingsPatch(LLM_PROVIDER="openai_compatible", LLM_BASE_URL="https://api.deepseek.com/v1"):
            self.assertEqual(normalize_provider(), "openai")
        with _SettingsPatch(LLM_PROVIDER="google", LLM_BASE_URL="http://127.0.0.1:11434/v1"):
            self.assertEqual(normalize_provider(), "gemini")
        with _SettingsPatch(LLM_PROVIDER="openai", LLM_BASE_URL="http://127.0.0.1:11434/v1"):
            # 显式 openai 即使留下本地默认基址，也按云端处理
            self.assertEqual(normalize_provider(), "openai")
            self.assertEqual(resolved_base_url(), "https://api.openai.com/v1")

    def test_unknown_provider(self):
        with _SettingsPatch(LLM_PROVIDER="claude"):
            with self.assertRaises(LLMConfigError) as ctx:
                normalize_provider()
            self.assertIn("不支持", str(ctx.exception))
            self.assertNotIn("sk-", str(ctx.exception))


class FactorySelectionTest(unittest.TestCase):
    def test_ollama_returns_chat_openai(self):
        with _SettingsPatch(
            LLM_PROVIDER="ollama",
            LLM_MODEL="qwen2.5:3b",
            LLM_API_KEY="ollama",
            LLM_BASE_URL="http://127.0.0.1:11434/v1",
            LLM_TEMPERATURE=0.3,
            LLM_TIMEOUT=120,
            LLM_MAX_TOKENS=800,
        ):
            model = get_chat_model(streaming=False, max_tokens=200)
            self.assertIsInstance(model, ChatOpenAI)
            self.assertEqual(model.model_name, "qwen2.5:3b")
            self.assertEqual(str(model.openai_api_base).rstrip("/"), "http://127.0.0.1:11434/v1")
            self.assertEqual(model.temperature, 0.3)
            self.assertEqual(model.max_tokens, 200)
            self.assertEqual(model.request_timeout, 120)

    def test_gemini_uses_chat_google_and_passes_config(self):
        fake = MagicMock(name="ChatGoogleGenerativeAI")
        with _SettingsPatch(
            LLM_PROVIDER="gemini",
            LLM_MODEL="gemini-2.0-flash",
            LLM_API_KEY="test-gemini-key-abc",
            LLM_BASE_URL="http://127.0.0.1:11434/v1",
            LLM_TEMPERATURE=0.2,
            LLM_TIMEOUT=45,
            LLM_MAX_TOKENS=256,
        ), patch("langchain_google_genai.ChatGoogleGenerativeAI", fake):
            returned = object()
            fake.return_value = returned
            model = get_chat_model(streaming=True, max_tokens=128)
            self.assertIs(model, returned)
            fake.assert_called_once()
            kwargs = fake.call_args.kwargs
            self.assertEqual(kwargs["model"], "gemini-2.0-flash")
            self.assertEqual(kwargs["google_api_key"], "test-gemini-key-abc")
            self.assertEqual(kwargs["temperature"], 0.2)
            self.assertEqual(kwargs["max_tokens"], 128)
            self.assertEqual(kwargs["timeout"], 45)
            self.assertTrue(kwargs["streaming"])
            self.assertNotIn("base_url", kwargs)  # 本地默认基址应被忽略

    def test_openai_compatible_endpoint(self):
        with _SettingsPatch(
            LLM_PROVIDER="openai",
            LLM_MODEL="deepseek-chat",
            LLM_API_KEY="sk-test-deepseek-key",
            LLM_BASE_URL="https://api.deepseek.com/v1",
            LLM_TEMPERATURE=0.1,
            LLM_TIMEOUT=60,
            LLM_MAX_TOKENS=300,
        ):
            model = get_chat_model(streaming=False)
            self.assertIsInstance(model, ChatOpenAI)
            self.assertEqual(model.model_name, "deepseek-chat")
            self.assertIn("api.deepseek.com", str(model.openai_api_base))
            self.assertEqual(model.temperature, 0.1)
            self.assertEqual(model.max_tokens, 300)
            self.assertEqual(model.request_timeout, 60)

    def test_missing_gemini_key_raises_clear_error(self):
        with _SettingsPatch(
            LLM_PROVIDER="gemini",
            LLM_MODEL="gemini-2.0-flash",
            LLM_API_KEY="",
        ):
            with self.assertRaises(LLMConfigError) as ctx:
                get_chat_model()
            msg = str(ctx.exception)
            self.assertIn("LLM_API_KEY", msg)
            self.assertIn("gemini", msg)

    def test_placeholder_openai_key_raises_clear_error(self):
        with _SettingsPatch(
            LLM_PROVIDER="openai",
            LLM_MODEL="gpt-4o-mini",
            LLM_API_KEY="your-llm-api-key",
            LLM_BASE_URL="https://api.openai.com/v1",
        ):
            with self.assertRaises(LLMConfigError) as ctx:
                get_chat_model()
            self.assertIn("LLM_API_KEY", str(ctx.exception))


class HealthAndDegradeTest(unittest.TestCase):
    def test_missing_key_health_is_offline_and_hides_secrets(self):
        secret = "sk-this-should-never-appear-in-health"
        with _SettingsPatch(
            LLM_PROVIDER="gemini",
            LLM_MODEL="gemini-2.0-flash",
            LLM_API_KEY="",  # missing
        ):
            result = health(force=True)
            self.assertFalse(result["available"])
            self.assertEqual(result["mode"], "offline")
            self.assertEqual(result["provider"], "gemini")
            self.assertEqual(result["model"], "gemini-2.0-flash")
            self.assertIn("LLM_API_KEY", result.get("error", ""))
            blob = str(result)
            self.assertNotIn("api_key", blob.lower().replace("llm_api_key", ""))
            self.assertNotIn(secret, blob)

        with _SettingsPatch(
            LLM_PROVIDER="openai",
            LLM_MODEL="gpt-4o-mini",
            LLM_API_KEY=secret,
            LLM_BASE_URL="https://api.openai.com/v1",
        ):
            mock_resp = SimpleNamespace(status_code=401, text=f"Incorrect API key provided: {secret}")
            mock_client = MagicMock()
            mock_client.__enter__.return_value.get.return_value = mock_resp
            with patch("app.core.llm.httpx.Client", return_value=mock_client):
                result = health(force=True)
            self.assertFalse(result["available"])
            self.assertEqual(result["mode"], "offline")
            self.assertEqual(result["provider"], "openai")
            self.assertEqual(result["model"], "gpt-4o-mini")
            self.assertIn("401", result.get("error", ""))
            blob = str(result)
            self.assertNotIn(secret, blob)

    def test_bad_gemini_key_health_degrades(self):
        secret = "AIzaSy-fake-secret-key-value"
        with _SettingsPatch(
            LLM_PROVIDER="gemini",
            LLM_MODEL="gemini-2.0-flash",
            LLM_API_KEY=secret,
            LLM_BASE_URL="",
        ):
            mock_resp = SimpleNamespace(status_code=403, text=f"API key not valid: {secret}")
            mock_client = MagicMock()
            mock_client.__enter__.return_value.get.return_value = mock_resp
            with patch("app.core.llm.httpx.Client", return_value=mock_client):
                result = health(force=True)
            self.assertFalse(result["available"])
            self.assertEqual(result["provider"], "gemini")
            self.assertIn("403", result.get("error", ""))
            self.assertNotIn(secret, str(result))
            self.assertFalse(llm_mod.is_available())

    def test_offline_provider_health(self):
        with _SettingsPatch(LLM_PROVIDER="offline", LLM_MODEL="offline"):
            result = health(force=True)
            self.assertFalse(result["available"])
            self.assertEqual(result["provider"], "offline")
            self.assertEqual(result["mode"], "offline")
            with self.assertRaises(LLMConfigError):
                get_chat_model()


class UseModelToolsTest(unittest.TestCase):
    def test_auto_skips_tools_for_ollama_uses_tools_for_cloud(self):
        from app.agent.chat import use_model_tools

        with _SettingsPatch(
            LLM_PROVIDER="ollama",
            LLM_TOOL_CALLING="auto",
            LLM_BASE_URL="http://127.0.0.1:11434/v1",
            LLM_MODEL="qwen2.5:3b",
        ):
            self.assertFalse(use_model_tools())
        with _SettingsPatch(
            LLM_PROVIDER="gemini",
            LLM_TOOL_CALLING="auto",
            LLM_BASE_URL="http://127.0.0.1:11434/v1",
            LLM_MODEL="gemini-2.0-flash",
            LLM_API_KEY="test-gemini-key-abc",
        ):
            self.assertTrue(use_model_tools())
        with _SettingsPatch(
            LLM_PROVIDER="openai",
            LLM_TOOL_CALLING="auto",
            LLM_BASE_URL="https://api.deepseek.com/v1",
            LLM_MODEL="deepseek-chat",
            LLM_API_KEY="sk-test",
        ):
            self.assertTrue(use_model_tools())


if __name__ == "__main__":
    unittest.main()
