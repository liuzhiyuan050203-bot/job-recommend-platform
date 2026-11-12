"""应用配置模块.

基于 pydantic-settings 实现环境变量与 .env 文件自动解析.
"""

import json
from pathlib import Path
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ai-service 根目录绝对路径 (保持所有相对路径以此为基准解析)
AI_SERVICE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """全局应用配置类."""

    # 基础应用配置
    APP_NAME: str = "ai-service"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # MySQL 8.4 数据库连接配置
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_DB: str = "job_platform"
    MYSQL_USER: str = "job"
    MYSQL_PASSWORD: str = "job123"

    # Spark：local[*] 为单机多线程；spark://127.0.0.1:7077 为 Standalone 伪分布式集群
    # （scripts/start-spark-cluster.sh 拉起）。集群模式下按下面三项申请 Executor。
    SPARK_MASTER: str = "local[*]"
    SPARK_EXECUTOR_MEMORY: str = "1g"
    SPARK_EXECUTOR_CORES: int = 2
    SPARK_CORES_MAX: int = 4
    # 批任务与在线问答共用一台机器时的资源隔离（见 docs：experiments/stability/README.md）。
    # SPARK_LOCAL_CORES：SPARK_MASTER 为 local[*] 时改写成 local[N]，给大模型和 API 留核；0 表示不改写。
    SPARK_LOCAL_CORES: int = 4
    # SPARK_BATCH_ISOLATED：批任务在独立子进程里跑（自带 Driver JVM），不占 ai-service 进程；false 退回进程内线程。
    SPARK_BATCH_ISOLATED: bool = True
    # SPARK_BATCH_NICE：子进程 nice 值（0~19），Driver JVM 与 Python worker 都继承，CPU 紧张时让位给问答。
    SPARK_BATCH_NICE: int = 10
    # SPARK_BATCH_QUEUE_MAX：运行中之外最多排队几个批次，超过返回 409；相同任务组合已在排队时直接复用。
    SPARK_BATCH_QUEUE_MAX: int = 2
    # SPARK_BATCH_TIMEOUT：单个批次子进程最长运行秒数，超时终止并把未结束任务记为失败。
    SPARK_BATCH_TIMEOUT: int = 1800

    # Chroma 向量数据库目录 (解析为 ai-service 下绝对路径)
    CHROMA_DIR: str = "./data/chroma"

    # 大模型与基础设施配置。LLM_PROVIDER: ollama | gemini | openai | offline
    # openai 可指向任意 OpenAI 兼容端点（DeepSeek / 通义 / OpenRouter 等）；
    # 旧值 openai_compatible 仍可用。默认本机 Ollama + qwen2.5:3b。
    LLM_PROVIDER: str = "ollama"
    LLM_BASE_URL: str = "http://127.0.0.1:11434/v1"
    LLM_API_KEY: str = "ollama"
    LLM_MODEL: str = "qwen2.5:3b"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 800
    LLM_TIMEOUT: int = 120
    LLM_TOOL_CALLING: str = "auto"  # "auto" | "true" | "false"
    # 助手流式回答的服务端时限（秒）：首个片段超过 LLM_FIRST_TOKEN_TIMEOUT 未到，或生成总时长超过
    # LLM_ANSWER_DEADLINE，就停止等待大模型，改用知识库摘录/工具结果作答（带引用），不让前端一直等到超时。
    LLM_FIRST_TOKEN_TIMEOUT: float = 45.0
    LLM_ANSWER_DEADLINE: float = 90.0

    # 嵌入模型配置 (FastEmbed)
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_CACHE_DIR: str = "./data/models"

    # 内部通信安全令牌，必须与 Spring Boot 的 AI_INTERNAL_TOKEN / fastapi.internal-token 相同
    AI_INTERNAL_TOKEN: str = "change-me-internal-token"

    # RAG 检索与切片
    RAG_COLLECTION: str = "job_knowledge"
    RAG_SCORE_THRESHOLD: float = 0.50
    RAG_TOP_K: int = 4
    RAG_CHUNK_SIZE: int = 400
    RAG_CHUNK_OVERLAP: int = 60
    RAG_PROMPT_CHUNK_CHARS: int = 300
    # dense | bm25 | hybrid | hybrid_rerank。
    # 2026-11 评测：标题切分 + hybrid 的 Hit@1=0.92、MRR@10=0.947，约 15ms/问。
    # hybrid_rerank 的 Hit@1 同为 0.92，平均延迟约 1.86s，超过 1.5s，故默认 hybrid。
    RAG_RETRIEVAL_MODE: str = "hybrid"
    # 职位检索多样性：同一职位、同一公司在最终 top-k 中的切片上限；0 表示不限制。
    RAG_DIVERSITY_PER_JOB: int = 1
    RAG_DIVERSITY_PER_COMPANY: int = 2
    # 服务启动后在后台做一次职位增量同步（跳过未变切片、剔除过期），失败不影响启动。
    RAG_SYNC_JOBS_ON_START: bool = True

    # 跨域允许源 (支持 Spring Boot 8080 与 Vue 5173)
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
    ]

    @field_validator("CHROMA_DIR", "EMBEDDING_CACHE_DIR", mode="after")
    @classmethod
    def resolve_service_path(cls, v: str) -> str:
        """确保相对路径始终相对 ai-service 目录解析，避免因执行目录不同导致路径漂移."""
        path = Path(v)
        if not path.is_absolute():
            path = (AI_SERVICE_DIR / path).resolve()
        return str(path)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """支持从逗号分隔字符串或 JSON 格式解析跨域源列表."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def database_url(self) -> str:
        """SQLAlchemy 数据库连接 URL."""
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        )

    model_config = SettingsConfigDict(
        env_file=[str(AI_SERVICE_DIR / ".env"), ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
