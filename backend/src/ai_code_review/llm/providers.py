"""Bounded JSON chat adapters for local Ollama and compatible model servers."""

import json
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from ai_code_review.core.config import Settings
from ai_code_review.core.exceptions import ProviderError
from ai_code_review.core.models import AgentFinding, Model


class FindingBatch(Model):
    findings: list[AgentFinding]


class LLMProvider(Protocol):
    """A provider returns untrusted typed findings; validation belongs to the core."""

    def review(self, system: str, context: str) -> list[AgentFinding]: ...


class JSONChatProvider:
    """HTTP transport shared by provider-specific request/response adapters."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def request(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.settings.api_key.get_secret_value():
            headers["Authorization"] = f"Bearer {self.settings.api_key.get_secret_value()}"
        try:
            with httpx.Client(
                timeout=self.settings.timeout_seconds,
                trust_env=False,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                with client.stream(
                    "POST",
                    self.settings.base_url.rstrip("/") + endpoint,
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > 1_000_000:
                            raise ProviderError("Model response exceeded the size limit")
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ProviderError("Model response must be an object")
            return result
        except (httpx.HTTPError, ValueError) as exc:
            # Do not expose server bodies, API keys, or submitted code in error messages.
            raise ProviderError("Local model request failed or returned invalid JSON") from exc

    def parse_findings(self, content: str) -> list[AgentFinding]:
        try:
            batch = FindingBatch.model_validate_json(content)
            if len(batch.findings) > 100:
                raise ProviderError("Model returned too many findings")
            for finding in batch.findings:
                finding.source = "ai"
                finding.analyzer = f"local:{self.settings.provider}"
            return batch.findings
        except (ValueError, ValidationError) as exc:
            raise ProviderError("Model findings failed schema validation") from exc


class OllamaProvider(JSONChatProvider):
    def review(self, system: str, context: str) -> list[AgentFinding]:
        payload = {
            "model": self.settings.model,
            "stream": False,
            "format": FindingBatch.model_json_schema(),
            "options": {"temperature": 0, "num_predict": 4096},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": context},
            ],
        }
        data = self.request("/api/chat", payload)
        try:
            return self.parse_findings(data["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise ProviderError("Ollama response is missing message content") from exc


class OpenAICompatibleProvider(JSONChatProvider):
    def review(self, system: str, context: str) -> list[AgentFinding]:
        payload = {
            "model": self.settings.model,
            "temperature": 0,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": context},
            ],
        }
        data = self.request("/chat/completions", payload)
        try:
            return self.parse_findings(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Compatible response is missing message content") from exc


def create_provider(settings: Settings) -> LLMProvider | None:
    if settings.provider == "ollama":
        return OllamaProvider(settings)
    if settings.provider == "openai-compatible":
        return OpenAICompatibleProvider(settings)
    return None
