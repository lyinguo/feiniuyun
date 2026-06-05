"""Application settings.

The backend uses an OpenAI-compatible chat-completions endpoint. This keeps the
project provider-neutral: DashScope, OpenAI, Azure OpenAI, and many private
gateways expose the same basic protocol.
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "NovelScriptAI"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "*"

    llm_api_key: str = Field(default="", description="API key for the model provider")
    llm_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="OpenAI-compatible API base URL",
    )
    llm_model: str = "qwen-max"
    llm_temperature: float = 0.25
    llm_max_tokens: int = 4096
    llm_timeout_seconds: float = 90.0
    llm_max_retries: int = 2

    max_input_chars: int = 600_000
    max_chapters_per_request: int = 120
    default_short_term_window: int = 2
    memory_dir: Path = Path("data/memory")

    enable_mcp_tools: bool = False
    mcp_config_path: str = ""

    @field_validator("debug", "enable_mcp_tools", mode="before")
    @classmethod
    def parse_bool_like(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "y", "on", "debug", "dev", "development"}:
                return True
            if lowered in {
                "0",
                "false",
                "no",
                "n",
                "off",
                "release",
                "prod",
                "production",
                "",
            }:
                return False
        return value

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key.strip())

    @property
    def cors_origin_list(self) -> List[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.memory_dir.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
