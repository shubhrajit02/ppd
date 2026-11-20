import base64

import httpx
import pytest

from ai_code_review.api.config import WebSettings
from ai_code_review.api.schemas import APIError, CreateReview
from ai_code_review.integrations.github import GitHubImporter, parse_github_url

SHA = "a" * 40
BASE = "b" * 40


def blob(source):
    return {
        "size": len(source),
        "encoding": "base64",
        "content": base64.b64encode(source.encode()).decode(),
    }


def test_repository_import_only_reads_supported_regular_files():
    calls = []

    def handle(request):
        calls.append(request)
        assert request.method == "GET" and request.url.host == "api.github.com"
        assert request.headers["Authorization"] == "Bearer private-test-token"
        if request.url.path.endswith("/repo"):
            data = {"default_branch": "main"}
        elif "/trees/" in request.url.path:
            data = {
                "tree": [
                    {"path": "src/a.py", "type": "blob", "mode": "100644", "sha": SHA},
                    {"path": "secret.py", "type": "blob", "mode": "120000", "sha": SHA},
                    {"path": "../escape.py", "type": "blob", "mode": "100644", "sha": SHA},
                    {"path": ".env", "type": "blob", "mode": "100644", "sha": SHA},
                ]
            }
        else:
            data = blob("print('safe snapshot')\n")
        return httpx.Response(200, json=data)

    importer = GitHubImporter(
        WebSettings(github_token="private-test-token"), httpx.MockTransport(handle)
    )
    result = importer.prepare(
        CreateReview(kind="github", title="test", url="https://github.com/owner/repo"), lambda: None
    )
    assert [f.path for f in result.sources] == ["src/a.py"]
    assert "private-test-token" not in result.context.model_dump_json()
    assert len(calls) == 3


def test_pr_import_builds_diff_from_merge_base_and_head_blobs():
    def handle(request):
        route = request.url.path
        if route.endswith("/repo"):
            data = {"default_branch": "main"}
        elif route.endswith("/pulls/7"):
            data = {
                "head": {"repo": {"html_url": "https://github.com/fork/repo"}, "sha": SHA},
                "base": {"sha": BASE},
                "changed_files": 1,
            }
        elif "/compare/" in route:
            data = {"merge_base_commit": {"sha": BASE}}
        elif "/trees/" in route:
            data = {"tree": [{"path": "a.ts", "type": "blob", "mode": "100644", "sha": BASE}]}
        elif route.endswith("/files"):
            data = [{"filename": "a.ts", "status": "modified", "sha": SHA}]
        elif route.endswith(BASE):
            data = blob("const a = 1;\n")
        else:
            data = blob("const a = 1;\ndebugger;\n")
        return httpx.Response(200, json=data)

    result = GitHubImporter(WebSettings(), httpx.MockTransport(handle)).prepare(
        CreateReview(kind="pr", title="PR", url="https://github.com/owner/repo/pull/7"),
        lambda: None,
    )
    assert result.context.mode == "diff"
    assert result.sources[0].before == "const a = 1;\n"
    assert "+debugger;" in result.sources[0].patch
    assert result.sources[0].changed_lines[0].start == 2


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",
        "https://evil.test/a/b",
        "https://github.com@evil.test/a/b",
        "https://github.com/a/b?token=x",
        "https://github.com/a/b/pull/0",
    ],
)
def test_github_url_rejects_other_hosts_and_credentials(url):
    with pytest.raises(APIError):
        parse_github_url(url)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 302])
def test_github_errors_do_not_echo_response_or_token(status):
    importer = GitHubImporter(
        WebSettings(github_token="private-test-token"),
        httpx.MockTransport(lambda _: httpx.Response(status, text="secret upstream body")),
    )
    with pytest.raises(APIError) as error:
        importer.prepare(
            CreateReview(kind="github", title="test", url="https://github.com/owner/repo"),
            lambda: None,
        )
    assert "secret" not in error.value.detail
    assert "private-test-token" not in error.value.detail
