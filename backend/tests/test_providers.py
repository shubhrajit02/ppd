import json

import httpx
import pytest
from pydantic import ValidationError
from test_domain import make_finding

from ai_code_review.core.config import Settings, load_settings
from ai_code_review.core.exceptions import ProviderError
from ai_code_review.core.models import ReviewRequest
from ai_code_review.llm.providers import OllamaProvider, OpenAICompatibleProvider
from ai_code_review.review.engine import ReviewEngine


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com",
        "file:///tmp/model",
        "http://localhost@evil.example",
        "http://localhost?token=secret",
    ],
)
def test_remote_endpoints_rejected(url):
    with pytest.raises(ValidationError):
        Settings(provider="ollama", model="local", base_url=url)


def test_config_secrets_and_explicit_dotenv(tmp_path):
    file = tmp_path / ".env"
    file.write_text("AICR_MAX_FILES=7\nAICR_API_KEY=sensitive-test-value\n")
    settings = load_settings(file)
    assert settings.max_files == 7
    assert "sensitive-test-value" not in settings.model_dump_json()
    with pytest.raises(ValidationError):
        Settings(provider="ollama", model="model:cloud")


@pytest.mark.parametrize(
    "provider_type,provider_name,envelope,endpoint",
    [
        (OllamaProvider, "ollama", {"message": {"content": '{"findings": []}'}}, "/api/chat"),
        (
            OpenAICompatibleProvider,
            "openai-compatible",
            {"choices": [{"message": {"content": '{"findings": []}'}}]},
            "/chat/completions",
        ),
    ],
)
def test_provider_wire_contract(provider_type, provider_name, envelope, endpoint):
    def handler(request):
        assert request.url.path == endpoint
        payload = json.loads(request.content)
        assert payload["model"] == "local"
        assert payload["messages"][0]["role"] == "system"
        return httpx.Response(200, json=envelope)

    settings = Settings(provider=provider_name, model="local")
    provider = provider_type(settings, httpx.MockTransport(handler))
    assert provider.review("Review code", "code data") == []


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="private-server-details"),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"missing": True}),
        httpx.Response(200, json={"message": {"content": '{"findings": [{"bad": true}]}'}}),
        httpx.Response(302, headers={"location": "https://example.com"}),
    ],
)
def test_provider_errors_are_sanitized(response):
    provider = OllamaProvider(
        Settings(provider="ollama", model="local"), httpx.MockTransport(lambda request: response)
    )
    with pytest.raises(ProviderError) as error:
        provider.review("s", "c")
    assert "private-server-details" not in str(error.value)


def test_ai_failure_preserves_static_and_no_ai_skips_provider(tmp_path):
    path = tmp_path / "main.py"
    path.write_text("eval(value)\n")

    class Failed:
        def review(self, system, context):
            raise ProviderError("Unavailable")

    engine = ReviewEngine(provider=Failed())
    report = engine.review(ReviewRequest(path=path))
    assert report.ai_status == "failed"
    assert report.findings[0].rule_id == "dynamic-eval"
    assert report.warnings
    report = engine.review(ReviewRequest(path=path, no_ai=True))
    assert report.ai_status == "disabled"


def test_ai_call_budget_and_no_silent_truncation(tmp_path):
    path = tmp_path / "main.py"
    path.write_bytes(b"eval(value)\n")

    class Empty:
        calls = 0

        def review(self, system, context):
            self.calls += 1
            assert json.loads(context)["file"]["content"] == "eval(value)\n"
            return []

    provider = Empty()
    report = ReviewEngine(Settings(max_ai_calls=1), provider).review(ReviewRequest(path=path))
    assert provider.calls == 1
    assert report.ai_status == "partial"
    path.write_text("# long\n" * 5000)
    report = ReviewEngine(Settings(max_ai_chars=1000), provider).review(ReviewRequest(path=path))
    assert provider.calls == 1
    assert report.ai_status == "partial"


def test_ai_findings_flow_through_real_engine_and_validation(tmp_path):
    path = tmp_path / "main.py"
    path.write_bytes(b"eval(value)\n")
    item = make_finding(rule_id="ai-risk", code_snippet="eval(value)").model_dump(mode="json")
    item.update(source="ai", validation="VERIFIED")
    missing = {**item, "file": "invented.py"}
    envelope = {"message": {"content": json.dumps({"findings": [item, missing]})}}
    settings = Settings(provider="ollama", model="local", max_ai_calls=4)
    provider = OllamaProvider(
        settings, httpx.MockTransport(lambda request: httpx.Response(200, json=envelope))
    )
    report = ReviewEngine(settings, provider).review(ReviewRequest(path=path))
    assert report.ai_status == "completed"
    assert len(report.findings) == 2
    ai = next(f for f in report.findings if f.source == "ai")
    assert ai.validation.value == "GROUNDED"
    assert ai.confidence == 0.85
    assert len(report.rejected_findings) == 1
    assert report.rejected_findings[0].file == "invented.py"
