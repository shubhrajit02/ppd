"""Optional read-only live GitHub smoke test. No token or source text is printed."""
import json

import httpx

from ai_code_review.api.config import WebSettings
from ai_code_review.api.schemas import CreateReview
from ai_code_review.core.config import Settings
from ai_code_review.integrations.github import GitHubImporter
from ai_code_review.review.engine import ReviewEngine

settings = WebSettings(github_max_files=3)
requests = [CreateReview(kind="github", title="Public repository smoke", url="https://github.com/kailash0001/ai-code-review-system")]
with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
    response = client.get("https://api.github.com/repos/pallets/flask/pulls", params={"state": "closed", "per_page": 10})
    response.raise_for_status()
    for pr in response.json():
        files = client.get(f"https://api.github.com/repos/pallets/flask/pulls/{pr['number']}/files", params={"per_page": 100})
        files.raise_for_status()
        if any(f["filename"].endswith(".py") and f["status"] != "removed" for f in files.json()):
            requests.append(CreateReview(kind="pr", title="Public PR smoke", url=pr["html_url"]))
            break
    if len(requests) != 2:
        raise RuntimeError("No recent PR with Python source; choose a source PR explicitly")
for request in requests:
    prepared = GitHubImporter(settings).prepare(request, lambda: None)
    report = ReviewEngine(Settings(provider="none")).review_context(prepared.context, no_ai=True)
    print(json.dumps({"kind": request.kind, "url": request.url, "files": len(prepared.sources), "findings": len(report.findings), "score": report.score.value, "warnings": report.warnings}))
