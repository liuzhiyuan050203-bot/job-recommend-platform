"""LLM 统一提供者与离线降级模块.

根据 LLM_PROVIDER（ollama | gemini | openai | offline）创建 LangChain 对话模型，
并提供流式 / 同步调用、健康检查与离线知识库抽取。健康检查与日志不会输出 API Key。
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Union

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_PROVIDER_ALIASES = {
    "openai_compatible": "openai",
    "google": "gemini",
    "google_genai": "gemini",
    "google_gemini": "gemini",
    "gemini_api": "gemini",
}

_KNOWN_PROVIDERS = frozenset({"ollama", "gemini", "openai", "offline"})

_PLACEHOLDER_KEYS = frozenset(
    {
        "",
        "ollama",
        "offline",
        "your-llm-api-key",
        "sk-your-deepseek-api-key",
        "sk-your-dashscope-api-key",
        "your-zhipu-api-key",
        "changeme",
        "change-me",
        "change_me",
        "sk-...",
        "none",
        "null",
        "todo",
        "placeholder",
    }
)


class LLMConfigError(RuntimeError):
    """大模型配置不完整或无效（缺密钥、不支持的提供方等）。"""


class OfflineGenerator:
    """离线问答提取生成器.

    在大模型处于离线模式或无法连通时，基于用户问题与检索到的知识库切片，
    通过字符 2-gram (Bigram) 重合度挑选最具相关性的语句，组装为带引用标记 [n] 的 Markdown 格式摘录.
    """

    @staticmethod
    def _extract_char_bigrams(text: str) -> set[str]:
        """提取文本字符 2-gram 集合（忽略空白字符并转为小写）."""
        clean = "".join(ch for ch in text if not ch.isspace()).lower()
        if len(clean) < 2:
            return {clean} if clean else set()
        return {clean[i : i + 2] for i in range(len(clean) - 1)}

    @classmethod
    def generate(
        cls,
        question: str,
        chunks: List[Dict[str, Any]],
        max_sentences: int = 3,
    ) -> str:
        """基于字符 bigram 重合度抽取最相关句子并构建离线答复.

        Args:
            question: 用户提问文本
            chunks: 检索到的知识库切片列表，元素通常包含 {title, content, source}
            max_sentences: 最多抽取的句子条数

        Returns:
            带 [n] 引用标记与统一前缀的 Markdown 列表文本
        """
        prefix = "【离线模式】未连接大模型，以下为知识库原文摘录："
        if not chunks:
            return f"{prefix}\n- （未检索到相关知识库内容）"

        q_bigrams = cls._extract_char_bigrams(question)

        # 针对每个 chunk (1-based index 为 n)，在句级别评估其与问题的匹配度
        candidates: List[Dict[str, Any]] = []

        for idx, chunk in enumerate(chunks, 1):
            if isinstance(chunk, dict):
                content = chunk.get("content", "")
                title = chunk.get("title") or chunk.get("source") or f"文档{idx}"
                source = chunk.get("source") or chunk.get("category") or ""
            else:
                content = str(chunk)
                title = f"文档{idx}"
                source = ""

            # 按照常见中文与英文断句标点切分句子
            sentences = [
                s.strip()
                for s in re.split(r"[。！？!?；;\n]+", content)
                if len(s.strip()) >= 4
            ]
            if not sentences and content.strip():
                sentences = [content.strip()]

            best_sentence = sentences[0] if sentences else ""
            best_score = -1.0

            for sent in sentences:
                s_bigrams = cls._extract_char_bigrams(sent)
                overlap = len(q_bigrams & s_bigrams) if q_bigrams else 0
                score = overlap / (len(q_bigrams) + 1e-6) if q_bigrams else 0.0
                if score > best_score:
                    best_score = score
                    best_sentence = sent

            if best_sentence:
                candidates.append(
                    {
                        "idx": idx,
                        "title": title,
                        "source": source,
                        "sentence": best_sentence,
                        "score": best_score,
                    }
                )

        # 优先按匹配重合度降序排列，取前 max_sentences 条
        candidates.sort(key=lambda x: x["score"], reverse=True)
        selected = candidates[:max_sentences]

        lines = [prefix]
        for item in selected:
            title_label = item["title"]
            lines.append(f"- {item['sentence']} [{item['idx']}]（来源: {title_label}）")

        return "\n".join(lines)

    @classmethod
    async def astream(
        cls,
        question: str,
        chunks: List[Dict[str, Any]],
        max_sentences: int = 3,
    ) -> AsyncIterator[str]:
        """离线模式流式生成器."""
        full_text = cls.generate(question, chunks, max_sentences=max_sentences)
        lines = full_text.split("\n")
        for i, line in enumerate(lines):
            yield line + ("\n" if i < len(lines) - 1 else "")


def _norm_token(value: str) -> str:
    return (value or "").strip().lower().replace("-", "_")


def normalize_provider(raw: Optional[str] = None) -> str:
    """把环境变量规范为 ollama / gemini / openai / offline.

    ``openai_compatible`` 视为 openai；若基址仍是本机 Ollama 默认地址，则按 ollama 处理，
    以兼容旧的默认配置。显式 ``LLM_PROVIDER=openai`` 即使留下本地默认基址，也走官方/兼容云端接口。
    """
    original = raw if raw is not None else settings.LLM_PROVIDER
    token = _norm_token(original or "ollama")
    if not token:
        token = "ollama"
    mapped = _PROVIDER_ALIASES.get(token, token)
    if mapped not in _KNOWN_PROVIDERS:
        raise LLMConfigError(
            f"不支持的 LLM_PROVIDER={original!r}，可选：ollama、gemini、openai、offline"
        )
    if token in {"openai_compatible"} and _is_default_ollama_url(settings.LLM_BASE_URL):
        return "ollama"
    return mapped


def _is_default_ollama_url(url: Optional[str]) -> bool:
    text = (url or "").strip().rstrip("/").lower()
    if text.endswith("/v1"):
        text = text[:-3].rstrip("/")
    return text in {
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://0.0.0.0:11434",
        "http://[::1]:11434",
    }


def _is_local_llm_url(url: Optional[str]) -> bool:
    text = (url or "").lower()
    return any(host in text for host in ("127.0.0.1", "localhost", "0.0.0.0", "[::1]"))


def resolved_base_url(provider: Optional[str] = None) -> Optional[str]:
    """当前提供方实际使用的 API 基址；Gemini 默认不需要基址。"""
    name = provider or normalize_provider()
    raw = (settings.LLM_BASE_URL or "").strip()
    if name == "ollama":
        return raw or DEFAULT_OLLAMA_BASE_URL
    if name == "gemini":
        if raw and not _is_default_ollama_url(raw):
            return raw
        return None
    if name == "openai":
        if raw and not _is_default_ollama_url(raw):
            return raw
        return DEFAULT_OPENAI_BASE_URL
    return raw or None


def _is_placeholder_key(key: Optional[str]) -> bool:
    text = (key or "").strip()
    if text.lower() in _PLACEHOLDER_KEYS:
        return True
    low = text.lower()
    if "your-" in low or low.startswith("your_") or "placeholder" in low:
        return True
    return False


def _require_cloud_api_key(provider: str) -> str:
    key = (settings.LLM_API_KEY or "").strip()
    if _is_placeholder_key(key):
        raise LLMConfigError(
            f"LLM_PROVIDER={provider} 需要有效的 LLM_API_KEY，"
            "请在 .env 中填写后重启 ai-service（或本机的 bishe-ai 服务）。"
            "不要把真实密钥提交到仓库。"
        )
    return key


def _safe_error(exc: Union[BaseException, str]) -> str:
    """去掉密钥后再截断，避免健康检查或日志泄露凭证。"""
    text = str(exc)
    key = (settings.LLM_API_KEY or "").strip()
    if key and len(key) >= 4:
        text = text.replace(key, "***")
    text = re.sub(r"(key=)([^&\s]+)", r"\1***", text, flags=re.I)
    text = re.sub(r"(Bearer\s+)\S+", r"\1***", text, flags=re.I)
    text = re.sub(
        r"(api[_-]?key[\"']?\s*[:=]\s*[\"']?)([^\"'\s,&]+)",
        r"\1***",
        text,
        flags=re.I,
    )
    return text[:240]


def _build_chat_model(
    streaming: bool = True, max_tokens: Optional[int] = None
) -> BaseChatModel:
    """按当前环境变量构造 LangChain 对话模型，不探活。"""
    provider = normalize_provider()
    if provider == "offline":
        raise LLMConfigError(
            "LLM_PROVIDER=offline，不会创建在线模型。问答将走离线摘录；"
            "若要启用大模型，请将 LLM_PROVIDER 改为 ollama、gemini 或 openai。"
        )

    model_name = settings.LLM_MODEL
    temperature = settings.LLM_TEMPERATURE
    timeout = settings.LLM_TIMEOUT
    token_limit = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS
    base_url = resolved_base_url(provider)

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = _require_cloud_api_key(provider)
        kwargs: Dict[str, Any] = {
            "model": model_name,
            "google_api_key": api_key,
            "temperature": temperature,
            "max_tokens": token_limit,
            "timeout": timeout,
            "streaming": streaming,
        }
        if base_url:
            kwargs["base_url"] = base_url
        return ChatGoogleGenerativeAI(**kwargs)

    # ollama 与 openai（含任意 OpenAI 兼容端点，如 DeepSeek / 通义 / OpenRouter）
    api_key = (settings.LLM_API_KEY or "").strip()
    if provider == "openai":
        api_key = _require_cloud_api_key(provider)
    elif not api_key:
        api_key = "ollama"

    return ChatOpenAI(
        model=model_name,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=token_limit,
        timeout=timeout,
        streaming=streaming,
    )


class LLMProvider:
    """LLM 统一提供者与连接池适配器."""

    def __init__(self) -> None:
        self._health_cache: Optional[Dict[str, Any]] = None
        self._health_cache_time: float = 0.0
        self._lock = threading.Lock()

    def reset_health_cache(self) -> None:
        """清空探活缓存（配置变更或单测使用）。"""
        with self._lock:
            self._health_cache = None
            self._health_cache_time = 0.0

    def get_llm(self, streaming: bool = True, max_tokens: Optional[int] = None) -> BaseChatModel:
        """获取配置好的 LangChain 对话模型.

        LLM_PROVIDER=ollama 走本机 Ollama 的 OpenAI 兼容接口；
        gemini 走 ChatGoogleGenerativeAI；
        openai 走 ChatOpenAI，可指向官方或任意兼容端点（DeepSeek、DashScope、OpenRouter 等）。
        max_tokens 缺省时使用配置项，智能体回答会单独收紧到约 500.
        """
        return _build_chat_model(streaming=streaming, max_tokens=max_tokens)

    def get_chat_model(
        self, streaming: bool = True, max_tokens: Optional[int] = None
    ) -> BaseChatModel:
        """get_llm 的别名，便于按工厂语义调用。"""
        return self.get_llm(streaming=streaming, max_tokens=max_tokens)

    def health(self, force: bool = False) -> Dict[str, Any]:
        """检查 LLM 服务健康状态 (ping 端点，带 ~30s 缓存，绝不泄露 API KEY)."""
        now = time.time()
        if not force and self._health_cache and (now - self._health_cache_time < 30.0):
            return self._health_cache

        with self._lock:
            # 双重检验锁避免并发重复请求
            if not force and self._health_cache and (time.time() - self._health_cache_time < 30.0):
                return self._health_cache

            result = self._probe_health()
            self._health_cache = result
            self._health_cache_time = time.time()
            return result

    def _probe_health(self) -> Dict[str, Any]:
        now = time.time()
        cached_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        try:
            provider = normalize_provider()
        except LLMConfigError as exc:
            return {
                "provider": (settings.LLM_PROVIDER or "").strip() or "unknown",
                "model": settings.LLM_MODEL,
                "base_url": settings.LLM_BASE_URL,
                "available": False,
                "mode": "offline",
                "error": _safe_error(exc),
                "cached_at": cached_at,
            }

        base_url = resolved_base_url(provider)
        model = settings.LLM_MODEL
        base: Dict[str, Any] = {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "cached_at": cached_at,
        }

        if provider == "offline":
            base.update(
                {
                    "available": False,
                    "mode": "offline",
                    "message": "配置为离线模式，将自动回退为 extractive 知识抽取",
                }
            )
            return base

        if provider in {"gemini", "openai"}:
            try:
                _require_cloud_api_key(provider)
            except LLMConfigError as exc:
                base.update(
                    {
                        "available": False,
                        "mode": "offline",
                        "error": _safe_error(exc),
                    }
                )
                return base

        start_t = time.perf_counter()
        try:
            if provider == "gemini":
                status_code, body = _probe_gemini(settings.LLM_API_KEY)
            else:
                status_code, body = _probe_openai_compatible(
                    base_url or DEFAULT_OLLAMA_BASE_URL, settings.LLM_API_KEY
                )
            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
            if status_code in (200, 201, 204):
                base.update(
                    {
                        "available": True,
                        "mode": "online",
                        "latency_ms": latency_ms,
                    }
                )
                return base
            if status_code in (401, 403):
                error = f"API Key 无效或权限不足（HTTP {status_code}）"
            else:
                error = f"HTTP {status_code}: {_safe_error(body)}"
            base.update(
                {
                    "available": False,
                    "mode": "offline",
                    "error": error,
                    "latency_ms": latency_ms,
                }
            )
            return base
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
            logger.warning("LLM health probe failed: %s", _safe_error(exc))
            base.update(
                {
                    "available": False,
                    "mode": "offline",
                    "error": _safe_error(exc),
                    "latency_ms": latency_ms,
                }
            )
            return base

    def is_available(self) -> bool:
        """检查大模型服务当前是否连通可用."""
        return bool(self.health().get("available", False))

    async def astream_chat(
        self,
        messages: Union[str, List[Union[dict, BaseMessage]]],
    ) -> AsyncIterator[str]:
        """异步流式对话，逐个 yield 文本增量 (token deltas)."""
        if not self.is_available():
            raise RuntimeError(
                f"LLM 当前处于不可用状态 ({self.health().get('mode', 'offline')})，"
                "请检查 LLM 服务或使用 OfflineGenerator 降级生成."
            )

        llm = self.get_llm(streaming=True)
        async for chunk in llm.astream(messages):
            delta = chunk.content
            if isinstance(delta, str) and delta:
                yield delta
            elif isinstance(delta, list):
                for part in delta:
                    if isinstance(part, dict) and "text" in part:
                        yield part["text"]
                    elif isinstance(part, str):
                        yield part

    def chat(self, messages: Union[str, List[Union[dict, BaseMessage]]]) -> str:
        """同步阻塞对话，返回完整回答文本."""
        if not self.is_available():
            raise RuntimeError(
                f"LLM 当前处于不可用状态 ({self.health().get('mode', 'offline')})，"
                "请检查 LLM 服务或使用 OfflineGenerator 降级生成."
            )

        llm = self.get_llm(streaming=False)
        response = llm.invoke(messages)
        return response.content if isinstance(response.content, str) else str(response.content)


def _probe_openai_compatible(base_url: str, api_key: Optional[str]) -> tuple[int, str]:
    models_url = f"{base_url.rstrip('/')}/models"
    headers = {}
    key = (api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    with httpx.Client(timeout=3.0) as client:
        resp = client.get(models_url, headers=headers)
    return resp.status_code, resp.text[:200]


def _probe_gemini(api_key: Optional[str]) -> tuple[int, str]:
    params = {"key": (api_key or "").strip(), "pageSize": 1}
    with httpx.Client(timeout=3.0) as client:
        resp = client.get(GEMINI_MODELS_URL, params=params)
    return resp.status_code, resp.text[:200]


# 单例实例与模块级便捷调用函数
llm_provider = LLMProvider()


def get_llm(streaming: bool = True, max_tokens: Optional[int] = None) -> BaseChatModel:
    """获取当前配置对应的 LangChain 对话模型."""
    return llm_provider.get_llm(streaming=streaming, max_tokens=max_tokens)


def get_chat_model(streaming: bool = True, max_tokens: Optional[int] = None) -> BaseChatModel:
    """工厂入口：按 LLM_PROVIDER 返回对话模型。"""
    return llm_provider.get_chat_model(streaming=streaming, max_tokens=max_tokens)


async def astream_chat(
    messages: Union[str, List[Union[dict, BaseMessage]]],
) -> AsyncIterator[str]:
    """异步流式对话."""
    async for token in llm_provider.astream_chat(messages):
        yield token


def chat(messages: Union[str, List[Union[dict, BaseMessage]]]) -> str:
    """同步对话."""
    return llm_provider.chat(messages)


def health(force: bool = False) -> Dict[str, Any]:
    """LLM 健康检查."""
    return llm_provider.health(force=force)


def is_available() -> bool:
    """LLM 是否可用."""
    return llm_provider.is_available()
