"""Server-only configuration; secrets never enter response models."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class WebSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AICR_WEB_", extra="ignore")
    data_dir: Path = Path(".aicr/web")
    github_token: SecretStr = SecretStr("")
    max_payload_bytes: int = Field(default=4_000_000, ge=1000, le=20_000_000)
    max_source_bytes: int = Field(default=2_000_000, ge=1000, le=10_000_000)
    max_files: int = Field(default=100, ge=1, le=500)
    workers: int = Field(default=2, ge=1, le=4)
    max_pending: int = Field(default=12, ge=1, le=100)
    source_retention_hours: int = Field(default=24, ge=1, le=168)
    github_max_files: int = Field(default=30, ge=1, le=100)
    github_max_requests: int = Field(default=50, ge=1, le=200)
    github_timeout_seconds: float = Field(default=20, ge=1, le=60)
    port: int = Field(default=8000, ge=1024, le=65535)
