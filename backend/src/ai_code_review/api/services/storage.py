"""SQLite history with expiring source snapshots and persisted execution events."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ai_code_review.api.schemas import (
    TERMINAL,
    APIError,
    FindingState,
    JobStatus,
    ReviewDetail,
    ReviewEvent,
    ReviewItem,
    SourceFile,
)
from ai_code_review.core.models import ReviewReport
from ai_code_review.core.progress import PipelineEvent


def now() -> str:
    return datetime.now(UTC).isoformat()


class ReviewStore:
    def __init__(self, directory: Path, retention_hours: int = 24):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "reviews.sqlite3"
        self.retention_hours = retention_hours
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL, source_url TEXT,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    error TEXT, report TEXT, sources TEXT, source_expires TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_id TEXT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS event_review ON events(review_id, sequence);
                CREATE TABLE IF NOT EXISTS finding_states (
                    review_id TEXT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
                    finding_id TEXT NOT NULL, state TEXT NOT NULL,
                    PRIMARY KEY(review_id, finding_id)
                );
            """)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def recover(self) -> None:
        """Interrupted in-process jobs fail explicitly rather than hanging after restart."""
        with self.connect() as db:
            db.execute(
                "UPDATE reviews SET status='FAILED', error=?, updated_at=? "
                "WHERE status NOT IN ('COMPLETED','FAILED','CANCELLED')",
                ("Server restarted before the review finished. Start a new review.", now()),
            )
        self.expire_sources()

    def expire_sources(self) -> None:
        with self.connect() as db:
            db.execute("UPDATE reviews SET sources=NULL WHERE source_expires < ?", (now(),))

    def create(self, review_id: str, title: str, kind: str, source_url: str | None) -> ReviewItem:
        timestamp = now()
        with self.connect() as db:
            db.execute(
                "INSERT INTO reviews(id,title,kind,source_url,status,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (review_id, title, kind, source_url, "QUEUED", timestamp, timestamp),
            )
        return self.get(review_id)

    def _item(self, row: sqlite3.Row) -> ReviewDetail:
        report = ReviewReport.model_validate_json(row["report"]) if row["report"] else None
        with self.connect() as db:
            states = {
                r["finding_id"]: r["state"]
                for r in db.execute(
                    "SELECT finding_id,state FROM finding_states WHERE review_id=?", (row["id"],)
                )
            }
        return ReviewDetail(
            id=row["id"],
            title=row["title"],
            kind=row["kind"],
            source_url=row["source_url"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error=row["error"],
            report=report,
            score=report.score.value if report else None,
            summary=report.summary if report else None,
            cancel_requested=bool(row["cancel_requested"]),
            finding_states=states,
            sources_available=bool(row["sources"]) and row["source_expires"] > now(),
        )

    def get(self, review_id: str) -> ReviewDetail:
        with self.connect() as db:
            row = db.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
        if row is None:
            raise APIError(404, "review_not_found", "This review does not exist")
        return self._item(row)

    def list_reviews(self, limit: int = 50, offset: int = 0) -> list[ReviewItem]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM reviews ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        fields = set(ReviewItem.model_fields)
        return [ReviewItem.model_validate(self._item(r).model_dump(include=fields)) for r in rows]

    def event(self, review_id: str, item: PipelineEvent) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO events(review_id,created_at,payload) VALUES(?,?,?)",
                (review_id, now(), item.model_dump_json()),
            )
            db.execute(
                "UPDATE reviews SET status=?, updated_at=? WHERE id=? "
                "AND status NOT IN ('COMPLETED','FAILED','CANCELLED')",
                (item.stage.value, now(), review_id),
            )

    def events(self, review_id: str, after: int = 0) -> list[ReviewEvent]:
        self.get(review_id)
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM events WHERE review_id=? AND sequence>? "
                "ORDER BY sequence LIMIT 1000",
                (review_id, after),
            ).fetchall()
        return [
            ReviewEvent(
                **json.loads(r["payload"]), sequence=r["sequence"], created_at=r["created_at"]
            )
            for r in rows
        ]

    def save_sources(self, review_id: str, sources: list[SourceFile]) -> None:
        expires = (datetime.now(UTC) + timedelta(hours=self.retention_hours)).isoformat()
        with self.connect() as db:
            db.execute(
                "UPDATE reviews SET sources=?,source_expires=? WHERE id=?",
                (json.dumps([f.model_dump() for f in sources]), expires, review_id),
            )

    def sources(self, review_id: str) -> list[SourceFile]:
        self.expire_sources()
        item = self.get(review_id)
        if not item.sources_available:
            raise APIError(
                410 if item.status in TERMINAL else 409,
                "sources_unavailable",
                "Source is not ready or its retention period has expired",
            )
        with self.connect() as db:
            row = db.execute("SELECT sources FROM reviews WHERE id=?", (review_id,)).fetchone()
        return [SourceFile.model_validate(f) for f in json.loads(row[0])]

    def finish(
        self,
        review_id: str,
        status: JobStatus,
        *,
        report: ReviewReport | None = None,
        error: str | None = None,
    ) -> None:
        with self.connect() as db:
            # Cancellation wins if requested before this completion transaction.
            row = db.execute(
                "SELECT cancel_requested FROM reviews WHERE id=?", (review_id,)
            ).fetchone()
            if row and row[0]:
                status, report, error = "CANCELLED", None, None
            db.execute(
                "UPDATE reviews SET status=?,report=?,error=?,updated_at=? WHERE id=?",
                (status, report.model_dump_json() if report else None, error, now(), review_id),
            )

    def request_cancel(self, review_id: str) -> None:
        if self.get(review_id).status in TERMINAL:
            raise APIError(409, "already_finished", "This review has already finished")
        with self.connect() as db:
            db.execute(
                "UPDATE reviews SET cancel_requested=1,updated_at=? WHERE id=? "
                "AND status NOT IN ('COMPLETED','FAILED','CANCELLED')",
                (now(), review_id),
            )

    def set_finding_state(self, review_id: str, finding_id: str, state: FindingState) -> None:
        report = self.get(review_id).report
        if report is None or not any(f.id == finding_id for f in report.findings):
            raise APIError(404, "finding_not_found", "This finding does not exist in the review")
        with self.connect() as db:
            db.execute(
                "INSERT INTO finding_states VALUES(?,?,?) ON CONFLICT(review_id,finding_id) "
                "DO UPDATE SET state=excluded.state",
                (review_id, finding_id, state),
            )

    def delete(self, review_id: str) -> None:
        if self.get(review_id).status not in TERMINAL:
            raise APIError(409, "review_running", "Cancel the review before deleting it")
        with self.connect() as db:
            db.execute("DELETE FROM reviews WHERE id=?", (review_id,))

    def dashboard(self) -> dict[str, Any]:
        self.expire_sources()
        with self.connect() as db:
            rows = db.execute("SELECT * FROM reviews ORDER BY created_at DESC").fetchall()
        reviews = [self._item(row) for row in rows]
        completed = [r for r in reviews if r.report is not None]
        severity = {s: 0 for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]}
        categories: dict[str, int] = {}
        repositories: dict[str, dict[str, Any]] = {}
        for review in completed:
            assert review.report is not None
            for finding in review.report.findings:
                if review.finding_states.get(finding.id, "OPEN") == "OPEN":
                    severity[finding.severity.value] += 1
                    categories[finding.category.value] = (
                        categories.get(finding.category.value, 0) + 1
                    )
        for review in reviews:
            key = review.source_url or review.title
            if key not in repositories:
                repositories[key] = {
                    "name": review.title,
                    "source_url": review.source_url,
                    "kind": review.kind,
                    "latest_review_id": review.id,
                    "score": review.score,
                    "status": review.status,
                    "updated_at": review.updated_at,
                    "review_count": 0,
                }
            repositories[key]["review_count"] += 1
        return {
            "review_count": len(reviews),
            "completed_count": len(completed),
            "average_score": round(sum(r.score or 0 for r in completed) / len(completed), 1)
            if completed
            else None,
            "files_reviewed": sum(r.summary.files_reviewed for r in completed if r.summary),
            "open_critical": severity["CRITICAL"],
            "open_high": severity["HIGH"],
            "severity_distribution": severity,
            "categories": categories,
            "repositories": list(repositories.values()),
            "recent": [r.model_dump(include=set(ReviewItem.model_fields)) for r in reviews[:6]],
        }
