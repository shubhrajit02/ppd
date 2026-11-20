"""Bounded GitHub REST imports. Tokens stay server-side; source is never executed."""

import base64
import difflib
import json
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from ai_code_review.api.config import WebSettings
from ai_code_review.api.schemas import (
    APIError,
    CreateReview,
    SourceFile,
    UploadedFile,
    safe_filename,
)
from ai_code_review.api.services.inputs import PreparedInput, validate_budget
from ai_code_review.core.models import RepositoryContext
from ai_code_review.review.input import parse_diff_ranges


def parse_github_url(url: str, pr_number: int | None = None) -> tuple[str, int | None]:
    parsed = urlsplit(url)
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or len(parts) not in {2, 4}
    ):
        raise APIError(
            422, "invalid_github_url", "Use https://github.com/owner/repository[/pull/123]"
        )
    owner, repo = parts[:2]
    repo = repo.removesuffix(".git")
    if (
        not re.fullmatch(r"[A-Za-z0-9-]{1,39}", owner)
        or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo)
        or repo in {".", ".."}
    ):
        raise APIError(422, "invalid_github_url", "Invalid GitHub owner or repository")
    if len(parts) == 4:
        if parts[2] != "pull" or not parts[3].isdigit() or int(parts[3]) < 1:
            raise APIError(422, "invalid_pull_request", "Use a valid pull request URL")
        pr_number = int(parts[3])
    return f"{owner}/{repo}", pr_number


class GitHubImporter:
    """One import has a fixed host, request budget and source budget."""

    def __init__(self, settings: WebSettings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def prepare(self, request: CreateReview, check_cancel: Callable[[], None]) -> PreparedInput:
        repository, number = parse_github_url(request.url, request.pr_number)
        if request.kind == "pr" and number is None:
            raise APIError(422, "missing_pr_number", "Provide a pull request URL or number")
        calls = 0
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AICR-local-review",
        }
        token = self.settings.github_token.get_secret_value()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        with httpx.Client(
            base_url="https://api.github.com",
            headers=headers,
            timeout=self.settings.github_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=self.transport,
        ) as client:

            def get(path: str, params: dict[str, str | int] | None = None) -> Any:
                nonlocal calls
                check_cancel()
                calls += 1
                if calls > self.settings.github_max_requests:
                    raise APIError(
                        422,
                        "github_budget",
                        "GitHub request budget exceeded; review a smaller scope",
                    )
                try:
                    with client.stream("GET", path, params=params) as response:
                        if response.status_code in {401, 403, 429}:
                            raise APIError(
                                502,
                                "github_access",
                                "GitHub denied access or rate-limited the request. "
                                "Check the server token/permissions or try "
                                "after the rate limit resets.",
                            )
                        if response.status_code == 404:
                            raise APIError(
                                422,
                                "github_not_found",
                                "GitHub repository/ref/file was not found "
                                "or is private to the configured credentials",
                            )
                        response.raise_for_status()
                        data = bytearray()
                        for chunk in response.iter_bytes():
                            check_cancel()
                            data.extend(chunk)
                            if len(data) > 8_000_000:
                                raise APIError(
                                    413,
                                    "github_response_large",
                                    "GitHub response exceeds the limit",
                                )
                    return json.loads(data)
                except (httpx.HTTPError, ValueError) as exc:
                    raise APIError(
                        502,
                        "github_unavailable",
                        "GitHub request failed; no repository code was executed",
                    ) from exc

            def blob(repo: str, sha: str) -> str:
                if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
                    raise APIError(
                        502, "github_invalid_data", "GitHub returned an invalid object ID"
                    )
                obj = get(f"/repos/{repo}/git/blobs/{sha}")
                if obj.get("size", 0) > 500_000 or obj.get("encoding") != "base64":
                    raise APIError(
                        413, "github_file_large", "A selected GitHub source file exceeds 500 KB"
                    )
                try:
                    data = base64.b64decode(obj["content"].replace("\n", ""), validate=True)
                    text = data.decode("utf-8-sig")
                    UploadedFile(path="check.py", content=text)
                    return text
                except (ValueError, UnicodeError, KeyError) as exc:
                    raise APIError(
                        422, "github_non_text", "GitHub source must be UTF-8 text"
                    ) from exc

            warnings: list[str] = []
            sources: list[SourceFile] = []
            metadata = get(f"/repos/{repository}")
            if request.kind == "pr":
                pr = get(f"/repos/{repository}/pulls/{number}")
                head_repo, _ = parse_github_url(pr["head"]["repo"]["html_url"])
                head_sha, base_sha = pr["head"]["sha"], pr["base"]["sha"]
                compare = get(
                    f"/repos/{repository}/compare/{quote(base_sha, safe='')}..."
                    f"{quote(head_sha, safe='')}"
                )
                merge_base = compare["merge_base_commit"]["sha"]
                tree = get(f"/repos/{repository}/git/trees/{merge_base}", {"recursive": "1"})
                if tree.get("truncated"):
                    raise APIError(
                        422,
                        "github_tree_truncated",
                        "GitHub truncated the baseline tree; narrow the review",
                    )
                baseline = {
                    entry["path"]: entry["sha"]
                    for entry in tree["tree"]
                    if entry["type"] == "blob" and entry["mode"] in {"100644", "100755"}
                }
                changed = []
                for page in range(1, 31):
                    batch = get(
                        f"/repos/{repository}/pulls/{number}/files", {"per_page": 100, "page": page}
                    )
                    changed.extend(batch)
                    if len(batch) < 100:
                        break
                if len(changed) != pr["changed_files"]:
                    raise APIError(
                        422, "github_files_truncated", "GitHub did not return every PR file"
                    )
                candidates = [entry for entry in changed if entry["status"] != "removed"]
                warnings.append(
                    "PR review: changed new-side lines against the merge base; "
                    "deleted code is not analyzed."
                )
                for entry in candidates:
                    check_cancel()
                    try:
                        path = safe_filename(entry["filename"])
                    except ValueError:
                        continue
                    if len(sources) >= self.settings.github_max_files:
                        warnings.append("GitHub file limit reached; this is a partial review.")
                        break
                    before_sha = baseline.get(entry.get("previous_filename", path))
                    before = blob(repository, before_sha) if before_sha else ""
                    content = blob(head_repo, entry["sha"])
                    patch = (
                        "\n".join(
                            difflib.unified_diff(
                                before.splitlines(),
                                content.splitlines(),
                                fromfile=f"a/{path}",
                                tofile=f"b/{path}",
                                n=0,
                            )
                        )
                        + "\n"
                    )
                    from ai_code_review.analysis.language import detect_language

                    sources.append(
                        SourceFile(
                            path=path,
                            content=content,
                            language=detect_language(path) or "",
                            before=before,
                            patch=patch,
                            changed_lines=parse_diff_ranges(patch),
                        )
                    )
                    validate_budget(
                        [UploadedFile(path=f.path, content=f.content) for f in sources],
                        self.settings,
                    )
            else:
                ref = request.ref or metadata["default_branch"]
                tree = get(
                    f"/repos/{repository}/git/trees/{quote(ref, safe='')}", {"recursive": "1"}
                )
                if tree.get("truncated"):
                    warnings.append(
                        "GitHub truncated the repository tree; this is a partial review."
                    )
                for entry in sorted(tree["tree"], key=lambda entry: entry["path"]):
                    check_cancel()
                    if entry["type"] != "blob" or entry["mode"] not in {"100644", "100755"}:
                        continue
                    try:
                        path = safe_filename(entry["path"])
                    except ValueError:
                        continue
                    if len(sources) >= self.settings.github_max_files:
                        warnings.append("GitHub file limit reached; this is a partial review.")
                        break
                    if entry.get("size", 0) > 500_000:
                        warnings.append(f"Skipped oversized source: {path}")
                        continue
                    from ai_code_review.analysis.language import detect_language

                    sources.append(
                        SourceFile(
                            path=path,
                            content=blob(repository, entry["sha"]),
                            language=detect_language(path) or "",
                        )
                    )
                    validate_budget(
                        [UploadedFile(path=f.path, content=f.content) for f in sources],
                        self.settings,
                    )
        if not sources:
            warnings.append("No supported source files found; the score is not assurance.")
        return PreparedInput(
            RepositoryContext(
                root=request.title,
                mode="diff" if request.kind == "pr" else "repository",
                files=[f.core_file() for f in sources],
                warnings=warnings,
            ),
            sources,
        )
