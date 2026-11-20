"""Strict HTTP contracts, distinct from the transport-independent review report."""

import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from ai_code_review.analysis.language import detect_language
from ai_code_review.core.models import FileChange, Model, ReviewReport, ReviewSummary
from ai_code_review.core.progress import PipelineEvent
from ai_code_review.review.input import EXCLUDED

JobStatus = Literal[
    "QUEUED",
    "SCANNING",
    "PARSING",
    "STATIC_ANALYSIS",
    "AI_ANALYSIS",
    "VALIDATING",
    "SYNTHESIZING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
]
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}
FindingState = Literal["OPEN", "RESOLVED", "IGNORED"]


def safe_filename(value: str) -> str:
    """Accept source-relative paths only, even though uploads are never written to disk."""
    if not value or len(value) > 240 or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid source filename")
    if value.startswith("/") or any(c in value for c in '\\:*?"<>|'):
        raise ValueError("Use a relative source path with forward slashes")
    parts = value.split("/")
    if any(
        p in {"", ".", ".."}
        or p.lower() in EXCLUDED
        or p.endswith((".", " "))
        or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?", p)
        for p in parts
    ):
        raise ValueError("Unsafe or excluded source path")
    if detect_language(value) is None:
        raise ValueError("Supported source: Python, JavaScript/JSX, TypeScript/TSX")
    return value


class UploadedFile(Model):
    path: str
    content: str = Field(max_length=500_000)

    _path = field_validator("path")(safe_filename)

    @field_validator("content")
    @classmethod
    def valid_source(cls, value: str) -> str:
        if "\0" in value or len(value.encode("utf-8")) > 500_000:
            raise ValueError("Source must be text and at most 500 KB per file")
        return value


class CreateReview(Model):
    kind: Literal["demo", "files", "code", "diff", "github", "pr"]
    title: str = Field(default="Untitled review", min_length=1, max_length=120)
    files: list[UploadedFile] = Field(default_factory=list, max_length=100)
    diff: str = Field(default="", max_length=1_000_000)
    url: str = Field(default="", max_length=300)
    ref: str | None = Field(default=None, max_length=200)
    pr_number: int | None = Field(default=None, ge=1, le=10000000)
    use_ai: bool = False

    @model_validator(mode="after")
    def check_kind(self) -> "CreateReview":
        if self.kind in {"files", "code", "diff"} and not self.files:
            raise ValueError("Upload/paste complete source files before starting a review")
        if self.kind == "code" and len(self.files) != 1:
            raise ValueError("Paste code accepts exactly one file")
        if self.kind == "diff" and not self.diff.strip():
            raise ValueError("Paste a unified diff and its complete post-change source")
        if self.kind in {"github", "pr"} and not self.url:
            raise ValueError("A GitHub URL is required")
        if self.kind in {"demo", "github", "pr"} and self.files:
            raise ValueError("This source mode does not accept uploaded files")
        if self.kind != "diff" and self.diff:
            raise ValueError("Diff data is only accepted in diff mode")
        names = [f.path.casefold() for f in self.files]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate source filenames are not allowed")
        return self


class SourceFile(FileChange):
    patch: str | None = None
    before: str | None = None

    def core_file(self) -> FileChange:
        return FileChange(
            path=self.path,
            content=self.content,
            language=self.language,
            changed_lines=self.changed_lines,
        )


class ReviewEvent(PipelineEvent):
    sequence: int
    created_at: str


class ReviewItem(Model):
    id: str
    title: str
    kind: str
    source_url: str | None
    status: JobStatus
    created_at: str
    updated_at: str
    error: str | None = None
    score: float | None = None
    summary: ReviewSummary | None = None
    cancel_requested: bool = False


class ReviewDetail(ReviewItem):
    report: ReviewReport | None = None
    finding_states: dict[str, FindingState] = Field(default_factory=dict)
    sources_available: bool = False


class StateUpdate(Model):
    state: FindingState


class ErrorResponse(Model):
    error: str
    detail: str


class APIError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status, self.code, self.detail = status, code, detail
