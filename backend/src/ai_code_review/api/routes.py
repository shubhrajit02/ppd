"""Thin HTTP routes: submit source, query persisted results, never implement review rules."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response

from ai_code_review.api.dependencies import jobs, store
from ai_code_review.api.schemas import (
    APIError,
    CreateReview,
    ReviewDetail,
    ReviewEvent,
    ReviewItem,
    SourceFile,
    StateUpdate,
    UploadedFile,
)
from ai_code_review.api.services.inputs import DEMO_FILES
from ai_code_review.api.services.jobs import ReviewJobs
from ai_code_review.api.services.storage import ReviewStore
from ai_code_review.core.models import ReviewFinding, ReviewReport, ReviewSummary, SuggestedFix

router = APIRouter(prefix="/api")
Store = Annotated[ReviewStore, Depends(store)]
Jobs = Annotated[ReviewJobs, Depends(jobs)]


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "engine": "shared", "mode": "local", "version": "0.2.0"}


@router.get("/config/providers", tags=["config"])
def providers(request: Request) -> dict[str, Any]:
    settings = request.app.state.core_settings
    web = request.app.state.web_settings
    return {
        "selected": settings.provider,
        "model": settings.model,
        "ai_available": settings.provider != "none",
        "providers": ["none", "ollama", "openai-compatible"],
        "github_authenticated": bool(web.github_token.get_secret_value()),
        "max_files": web.max_files,
        "max_source_bytes": web.max_source_bytes,
        "source_retention_hours": web.source_retention_hours,
    }


@router.get("/demo", response_model=list[UploadedFile], tags=["sources"])
def demo() -> list[UploadedFile]:
    return DEMO_FILES


@router.post("/reviews", response_model=ReviewItem, status_code=202, tags=["reviews"])
def create_review(payload: CreateReview, service: Jobs) -> ReviewItem:
    return service.submit(payload)


@router.post("/reviews/local", response_model=ReviewItem, status_code=202, tags=["reviews"])
def local_review(payload: CreateReview, service: Jobs) -> ReviewItem:
    if payload.kind not in {"files", "code", "demo"}:
        raise APIError(422, "invalid_kind", "Use files, code or demo for local review")
    return service.submit(payload)


@router.post("/reviews/diff", response_model=ReviewItem, status_code=202, tags=["reviews"])
def diff_review(payload: CreateReview, service: Jobs) -> ReviewItem:
    if payload.kind != "diff":
        raise APIError(422, "invalid_kind", "This route requires diff mode")
    return service.submit(payload)


@router.post("/github/repository", response_model=ReviewItem, status_code=202, tags=["github"])
def github_repository(payload: CreateReview, service: Jobs) -> ReviewItem:
    if payload.kind != "github":
        raise APIError(422, "invalid_kind", "This route requires github mode")
    return service.submit(payload)


@router.post("/github/pull-request", response_model=ReviewItem, status_code=202, tags=["github"])
def github_pr(payload: CreateReview, service: Jobs) -> ReviewItem:
    if payload.kind != "pr":
        raise APIError(422, "invalid_kind", "This route requires pr mode")
    return service.submit(payload)


@router.get("/reviews", response_model=list[ReviewItem], tags=["reviews"])
def list_reviews(
    database: Store, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)
) -> list[ReviewItem]:
    return database.list_reviews(limit, offset)


@router.get("/dashboard", tags=["dashboard"])
def dashboard(database: Store) -> dict[str, Any]:
    return database.dashboard()


@router.get("/repositories", tags=["sources"])
def repositories(database: Store) -> list[dict[str, Any]]:
    return list(database.dashboard()["repositories"])


@router.get("/reviews/{review_id}", response_model=ReviewDetail, tags=["reviews"])
def get_review(review_id: str, database: Store) -> ReviewDetail:
    return database.get(review_id)


@router.get("/reviews/{review_id}/events", response_model=list[ReviewEvent], tags=["reviews"])
def events(review_id: str, database: Store, after: int = Query(0, ge=0)) -> list[ReviewEvent]:
    return database.events(review_id, after)


@router.get("/reviews/{review_id}/files", response_model=list[SourceFile], tags=["sources"])
def files(review_id: str, database: Store) -> list[SourceFile]:
    return database.sources(review_id)


def completed_report(review_id: str, database: ReviewStore) -> ReviewReport:
    report = database.get(review_id).report
    if report is None:
        raise APIError(409, "report_not_ready", "This review does not have a completed report")
    return report


@router.get("/reviews/{review_id}/report", response_model=ReviewReport, tags=["reviews"])
def report(review_id: str, database: Store) -> ReviewReport:
    return completed_report(review_id, database)


@router.get("/reviews/{review_id}/findings", response_model=list[ReviewFinding], tags=["findings"])
def findings(review_id: str, database: Store) -> list[ReviewFinding]:
    return completed_report(review_id, database).findings


@router.get("/reviews/{review_id}/summary", response_model=ReviewSummary, tags=["reviews"])
def summary(review_id: str, database: Store) -> ReviewSummary:
    return completed_report(review_id, database).summary


@router.patch("/reviews/{review_id}/findings/{finding_id}", tags=["findings"])
def finding_state(
    review_id: str, finding_id: str, payload: StateUpdate, database: Store
) -> StateUpdate:
    database.set_finding_state(review_id, finding_id, payload.state)
    return payload


@router.post(
    "/reviews/{review_id}/fixes/{finding_id}", response_model=SuggestedFix, tags=["findings"]
)
def suggested_fix(review_id: str, finding_id: str, database: Store) -> SuggestedFix:
    """Retrieve a validated suggestion; this endpoint never applies code changes."""
    item = next(
        (f for f in completed_report(review_id, database).findings if f.id == finding_id), None
    )
    if item is None or item.suggested_fix is None:
        raise APIError(404, "patch_unavailable", "No grounded patch is available for this finding")
    return item.suggested_fix


@router.post("/reviews/{review_id}/cancel", status_code=202, tags=["reviews"])
def cancel(review_id: str, service: Jobs) -> dict[str, bool]:
    service.cancel(review_id)
    return {"cancel_requested": True}


@router.delete("/reviews/{review_id}", status_code=204, tags=["reviews"])
def delete_review(review_id: str, database: Store) -> Response:
    database.delete(review_id)
    return Response(status_code=204)
