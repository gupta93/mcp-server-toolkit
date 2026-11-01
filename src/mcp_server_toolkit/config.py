from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_TOOLKIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = False

    github_token: str | None = Field(default=None, description="Optional GitHub API token")
    github_api_base: str = "https://api.github.com"

    database_url: str = "sqlite:///demo_data/demo.db"
    max_sql_rows: int = Field(default=100, ge=1, le=1000)

    http_host: str = "127.0.0.1"
    http_port: int = Field(default=8000, ge=1, le=65535)
    http_path: str = "/mcp"
    http_timeout: float = Field(default=30.0, gt=0)

    server_name: str = "mcp-server-toolkit"
    server_version: str = "0.1.0"

    @field_validator("http_path")
    @classmethod
    def normalize_http_path(cls, value: str) -> str:
        if not value.startswith("/"):
            return f"/{value}"
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
