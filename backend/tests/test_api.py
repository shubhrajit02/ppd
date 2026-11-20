import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from ai_code_review.api.config import WebSettings
from ai_code_review.api.main import create_app
from ai_code_review.api.schemas import APIError, CreateReview
from ai_code_review.api.services.inputs import DEMO_FILES, diff_sources
from ai_code_review.api.services.jobs import ReviewJobs
from ai_code_review.api.services.storage import ReviewStore
from ai_code_review.cli.app import app as cli_app
from ai_code_review.core.config import Settings
from ai_code_review.review.engine import ReviewEngine

HEADERS = {"X-AICR-Client": "web"}


@pytest.fixture
def client(tmp_path):
    app = create_app(WebSettings(data_dir=tmp_path / "data"), Settings(provider="none"))
    with TestClient(app, headers=HEADERS) as test:
        yield test


def completed(client, review_id):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        result = client.get(f"/api/reviews/{review_id}")
        assert result.status_code == 200
        if result.json()["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
            return result.json()
        time.sleep(0.025)
    pytest.fail("Job did not finish in the expected time")


def test_health_openapi_and_provider_secrets(client):
    assert client.get("/api/health").json()["engine"] == "shared"
    schema = client.get("/openapi.json").json()
    assert "/api/reviews/{review_id}/events" in schema["paths"]
    assert "ErrorResponse" in schema["components"]["schemas"]
    config = client.get("/api/config/providers").json()
    assert config["selected"] == "none"
    assert "github_token" not in config and "api_key" not in config
    assert client.get("/docs").status_code == 200


def test_demo_complete_history_events_findings_patch(client):
    response = client.post("/api/reviews", json={"kind": "demo", "title": "Demo review"})
    assert response.status_code == 202, response.text
    review_id = response.json()["id"]
    review = completed(client, review_id)
    assert review["status"] == "COMPLETED", review
    assert review["report"]["summary"]["files_reviewed"] == 3
    assert client.get("/api/reviews").json()[0]["id"] == review_id
    assert client.get(f"/api/reviews/{review_id}/summary").json()["findings_count"] > 0
    events = client.get(f"/api/reviews/{review_id}/events").json()
    assert {e["stage"] for e in events} == {
        "SCANNING",
        "PARSING",
        "STATIC_ANALYSIS",
        "AI_ANALYSIS",
        "VALIDATING",
        "SYNTHESIZING",
    }
    assert any(e["stage"] == "AI_ANALYSIS" and e["state"] == "SKIPPED" for e in events)
    assert all(e["agent"] is None for e in events)
    assert (
        client.get(f"/api/reviews/{review_id}/events?after={events[-1]['sequence']}").json() == []
    )
    files = client.get(f"/api/reviews/{review_id}/files").json()
    assert len(files) == 3
    finding = next(f for f in review["report"]["findings"] if f["suggested_fix"])
    patch = client.post(f"/api/reviews/{review_id}/fixes/{finding['id']}")
    assert patch.status_code == 200
    assert "-    debugger;" in patch.json()["unified_diff"]
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["review_count"] == 1 and dashboard["open_high"] > 0
    assert client.get("/api/repositories").json()[0]["name"] == "Demo review"


def test_cli_and_web_produce_same_findings_for_same_files(client, tmp_path):
    folder = tmp_path / "sample"
    for file in DEMO_FILES:
        path = folder / file.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file.content.encode())
    cli = CliRunner().invoke(cli_app, ["review", str(folder), "--no-ai", "--format", "json"])
    assert cli.exit_code == 0, cli.output
    local = json.loads(cli.stdout)
    job = client.post(
        "/api/reviews/local",
        json={
            "kind": "files",
            "title": "Same sample",
            "files": [f.model_dump() for f in DEMO_FILES],
        },
    ).json()
    web = completed(client, job["id"])["report"]
    assert web["findings"] == local["findings"]
    assert web["rejected_findings"] == local["rejected_findings"]
    assert web["score"] == local["score"]
    assert set(web) == set(local)
    assert web["summary"]["severity_counts"] == local["summary"]["severity_counts"]


@pytest.mark.parametrize(
    "path",
    [
        "../escape.py",
        "/etc/test.py",
        "C:/secret.py",
        "a\\x.py",
        ".git/a.py",
        "nul.py",
        "test.txt",
        "a/../b.py",
    ],
)
def test_unsafe_uploads_rejected_without_echoing_source(client, path):
    result = client.post(
        "/api/reviews",
        json={"kind": "files", "files": [{"path": path, "content": "sensitive_source_content"}]},
    )
    assert result.status_code == 422
    assert "sensitive_source_content" not in result.text


def test_unknown_fields_and_client_filesystem_access_rejected(client):
    result = client.post("/api/reviews/local", json={"kind": "files", "path": "C:/Users/private"})
    assert result.status_code == 422
    duplicate = [{"path": "a.py", "content": "x=1"}, {"path": "A.py", "content": "x=2"}]
    assert (
        client.post("/api/reviews", json={"kind": "files", "files": duplicate}).status_code == 422
    )


def test_local_request_boundary(client):
    assert (
        client.post(
            "/api/reviews", json={"kind": "demo"}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/reviews", json={"kind": "demo"}, headers={"X-AICR-Client": ""}
        ).status_code
        == 403
    )
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    assert (
        client.options(
            "/api/reviews",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-AICR-Client",
            },
        ).status_code
        == 200
    )
    assert client.post("/api/reviews", content=b"x" * 4_000_001).status_code == 413


def test_decisions_persist_without_changing_engine_score(client):
    job = client.post("/api/reviews", json={"kind": "demo"}).json()
    review = completed(client, job["id"])
    high = next(f for f in review["report"]["findings"] if f["severity"] == "HIGH")
    before = client.get("/api/dashboard").json()["open_high"]
    result = client.patch(
        f"/api/reviews/{job['id']}/findings/{high['id']}", json={"state": "RESOLVED"}
    )
    assert result.status_code == 200
    refreshed = client.get(f"/api/reviews/{job['id']}").json()
    assert refreshed["finding_states"][high["id"]] == "RESOLVED"
    assert refreshed["report"]["score"] == review["report"]["score"]
    assert client.get("/api/dashboard").json()["open_high"] == before - 1
    assert client.delete(f"/api/reviews/{job['id']}").status_code == 204
    assert client.get(f"/api/reviews/{job['id']}").status_code == 404
    assert client.get("/api/dashboard").json()["review_count"] == 0


def test_diff_requires_exact_full_source_and_tracks_changed_lines(client):
    files = [{"path": "main.py", "content": "x = 1\neval(value)\n"}]
    patch = "--- a/main.py\n+++ b/main.py\n@@ -2 +2 @@\n-x = 2\n+eval(value)\n"
    job = client.post(
        "/api/reviews/diff", json={"kind": "diff", "files": files, "diff": patch}
    ).json()
    review = completed(client, job["id"])
    assert review["status"] == "COMPLETED"
    assert review["report"]["findings"][0]["lines"]["start"] == 2
    bad = client.post(
        "/api/reviews/diff",
        json={"kind": "diff", "files": files, "diff": patch.replace("+eval(value)", "+different")},
    ).json()
    assert completed(client, bad["id"])["status"] == "FAILED"


def test_sources_expire_but_evidence_remains(client):
    job = client.post("/api/reviews", json={"kind": "demo"}).json()
    completed(client, job["id"])
    with client.app.state.store.connect() as db:
        db.execute("UPDATE reviews SET source_expires='2000-01-01' WHERE id=?", (job["id"],))
    assert client.get(f"/api/reviews/{job['id']}/files").status_code == 410
    assert client.get(f"/api/reviews/{job['id']}").json()["report"]["findings"]


def test_restart_recovers_pending_and_keeps_history(tmp_path):
    store = ReviewStore(tmp_path)
    store.create("pending", "Pending", "files", None)
    store.recover()
    assert store.get("pending").status == "FAILED"
    assert "restarted" in store.get("pending").error
    again = ReviewStore(tmp_path)
    assert again.get("pending").title == "Pending"


def test_queue_limit_and_cancellation(tmp_path, monkeypatch):
    entered, release = Event(), Event()
    original = ReviewEngine.review_context

    def delayed(self, *args, **kwargs):
        entered.set()
        release.wait(3)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ReviewEngine, "review_context", delayed)
    web = WebSettings(data_dir=tmp_path, workers=1, max_pending=1)
    database = ReviewStore(tmp_path)
    jobs = ReviewJobs(database, web, Settings(provider="none"))
    try:
        job = jobs.submit(CreateReview(kind="demo"))
        assert entered.wait(3)
        with pytest.raises(APIError) as error:
            jobs.submit(CreateReview(kind="demo"))
        assert error.value.status == 429
        jobs.cancel(job.id)
        release.set()
    finally:
        release.set()
        jobs.close()
    assert database.get(job.id).status == "CANCELLED"


def test_sqlite_concurrent_history_writes(tmp_path):
    store = ReviewStore(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(lambda n: store.create(str(n), f"Review {n}", "code", None), range(12)))
    assert len(store.list_reviews()) == 12


def test_invalid_diff_hunks():
    from ai_code_review.api.schemas import UploadedFile

    with pytest.raises(APIError):
        diff_sources(
            "--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n+x\n",
            [UploadedFile(path="x.py", content="x\n")],
        )
