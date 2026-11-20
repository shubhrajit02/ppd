"""Request-scoped access to application-owned services."""

from typing import cast

from fastapi import Request

from ai_code_review.api.services.jobs import ReviewJobs
from ai_code_review.api.services.storage import ReviewStore


def jobs(request: Request) -> ReviewJobs:
    return cast(ReviewJobs, request.app.state.jobs)


def store(request: Request) -> ReviewStore:
    return cast(ReviewStore, request.app.state.store)
