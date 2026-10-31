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

    # MariaDB / MySQL 数据库连接配置 (兼容 MySQL 协议)
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_DB: str = "job_platform"
    MYSQL_USER: str = "job"
    MYSQL_PASSWORD: str = "job123"

    # Chroma 向量数据库目录 (解析为 ai-service 下绝对路径)
    CHROMA_DIR: str = "./data/chroma"

    # 大模型与基础设施配置
    LLM_PROVIDER: str = "openai_compatible"  # "openai_compatible" | "offline"
    LLM_BASE_URL: str = "http://127.0.0.1:11434/v1"
    LLM_API_KEY: str = "ollama"
    LLM_MODEL: str = "qwen2.5:3b"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 800
    LLM_TIMEOUT: int = 120
    LLM_TOOL_CALLING: str = "auto"  # "auto" | "true" | "false"

    # 嵌入模型配置 (FastEmbed)
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_CACHE_DIR: str = "./data/models"

    # 内部通信安全令牌 (与 Spring Boot 后端交互共享密钥)
    AI_INTERNAL_TOKEN: str = "change-me-internal-token"

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
