"""Transport-neutral pipeline events used by CLI, API and future integrations."""

from enum import StrEnum
from typing import Literal

from ai_code_review.core.models import Model


class Stage(StrEnum):
    SCANNING = "SCANNING"
    PARSING = "PARSING"
    STATIC_ANALYSIS = "STATIC_ANALYSIS"
    AI_ANALYSIS = "AI_ANALYSIS"
    VALIDATING = "VALIDATING"
    SYNTHESIZING = "SYNTHESIZING"


class PipelineEvent(Model):
    stage: Stage
    label: str
    state: Literal["RUNNING", "COMPLETED", "SKIPPED", "FAILED"] = "RUNNING"
    completed: int = 0
    total: int = 0
    findings: int = 0
    duration_seconds: float = 0
    agent: str | None = None


class ReviewCancelled(Exception):
    """Caller requested cooperative cancellation at a pipeline boundary."""
