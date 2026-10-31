"""LLM 统一提供者与离线降级模块.

提供 ChatOpenAI 统一适配、流式与同步调用、健康检查探活，以及离线模式下的知识库抽取生成器.
"""

import logging
import re
import threading
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Union

import httpx
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


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


class LLMProvider:
    """LLM 统一提供者与连接池适配器."""

    def __init__(self) -> None:
        self._health_cache: Optional[Dict[str, Any]] = None
        self._health_cache_time: float = 0.0
        self._lock = threading.Lock()

    def get_llm(self, streaming: bool = True) -> ChatOpenAI:
        """获取配置好的 LangChain ChatOpenAI 实例.

        支持 OpenAI 协议兼容端点 (本地 Ollama、DeepSeek、DashScope、智谱等).
        """
        return ChatOpenAI(
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT,
            streaming=streaming,
        )

    def health(self, force: bool = False) -> Dict[str, Any]:
        """检查 LLM 服务健康状态 (ping 端点，带 ~30s 缓存，绝不泄露 API KEY)."""
        now = time.time()
        if not force and self._health_cache and (now - self._health_cache_time < 30.0):
            return self._health_cache

        with self._lock:
            # 双重检验锁避免并发重复请求
            if not force and self._health_cache and (time.time() - self._health_cache_time < 30.0):
                return self._health_cache

            provider = settings.LLM_PROVIDER.lower()
            base_url = settings.LLM_BASE_URL
            model = settings.LLM_MODEL

            # 若显式配置为离线模式
            if provider == "offline":
                result = {
                    "provider": "offline",
                    "model": model,
                    "base_url": base_url,
                    "available": False,
                    "mode": "offline",
                    "message": "配置为离线模式，将自动回退为 extractive 知识抽取",
                    "cached_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
                }
                self._health_cache = result
                self._health_cache_time = now
                return result

            # 在线探测 OpenAI 兼容端点 (如 /v1/models)
            start_t = time.perf_counter()
            try:
                models_url = f"{base_url.rstrip('/')}/models"
                headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
                with httpx.Client(timeout=3.0) as client:
                    resp = client.get(models_url, headers=headers)
                latency_ms = round((time.perf_counter() - start_t) * 1000, 2)

                if resp.status_code in (200, 201, 204):
                    result = {
                        "provider": provider,
                        "model": model,
                        "base_url": base_url,
                        "available": True,
                        "mode": "online",
                        "latency_ms": latency_ms,
                        "cached_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
                    }
                else:
                    result = {
                        "provider": provider,
                        "model": model,
                        "base_url": base_url,
                        "available": False,
                        "mode": "offline",
                        "error": f"HTTP {resp.status_code}: {resp.text[:120]}",
                        "latency_ms": latency_ms,
                        "cached_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
                    }
            except Exception as exc:
                latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
                logger.warning(f"LLM health probe failed: {exc}")
                result = {
                    "provider": provider,
                    "model": model,
                    "base_url": base_url,
                    "available": False,
                    "mode": "offline",
                    "error": str(exc),
                    "latency_ms": latency_ms,
                    "cached_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
                }

            self._health_cache = result
            self._health_cache_time = now
            return result

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


# 单例实例与模块级便捷调用函数
llm_provider = LLMProvider()


def get_llm(streaming: bool = True) -> ChatOpenAI:
    """获取 ChatOpenAI 实例."""
    return llm_provider.get_llm(streaming=streaming)


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
