"""Explicit local configuration; model use is disabled unless selected."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Hosted OpenAI-compatible endpoints that may be used besides localhost.
REMOTE_HOSTS = {"integrate.api.nvidia.com"}  # NVIDIA build.nvidia.com free endpoint


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AICR_", extra="ignore")
    provider: Literal["none", "ollama", "openai-compatible"] = "none"
    base_url: str = "http://localhost:11434"
    model: str = ""
    api_key: SecretStr = SecretStr("")
    timeout_seconds: float = Field(default=60, ge=1, le=600)
    max_file_bytes: int = Field(default=500_000, ge=1, le=5_000_000)
    max_files: int = Field(default=1000, ge=1, le=10000)
    max_total_bytes: int = Field(default=20_000_000, ge=1, le=100_000_000)
    max_ai_chars: int = Field(default=24000, ge=1000, le=100000)
    max_ai_calls: int = Field(default=8, ge=1, le=100)

    @model_validator(mode="after")
    def local_only(self) -> "Settings":
        if self.provider != "none":
            url = urlsplit(self.base_url)
            remote_ok = (
                self.provider == "openai-compatible"
                and url.scheme == "https"
                and url.hostname in REMOTE_HOSTS
            )
            if (
                url.scheme not in {"http", "https"}
                or not (remote_ok or url.hostname in {"localhost", "127.0.0.1", "::1"})
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError("Only local endpoints or https://integrate.api.nvidia.com/v1 (openai-compatible) are allowed")
            if not self.model.strip():
                raise ValueError("AICR_MODEL is required when enabling AI")
            if self.model.lower().endswith(":cloud"):
                raise ValueError("Cloud models are disabled; select an installed local model")
        return self


def load_settings(env_file: Path | None = None, *, no_ai: bool = False) -> Settings:
    """Read process environment and only an explicitly requested dotenv file."""
    if no_ai:
        return Settings(_env_file=env_file, provider="none")  # type: ignore[call-arg]
    return Settings(_env_file=env_file)  # type: ignore[call-arg]
