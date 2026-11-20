"""Versioned, serializable contracts shared by CLI and future API adapters."""

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    @property
    def rank(self) -> int:
        return list(Severity).index(self)


class Category(StrEnum):
    SECURITY = "SECURITY"
    BUG = "BUG"
    PERFORMANCE = "PERFORMANCE"
    MAINTAINABILITY = "MAINTAINABILITY"
    STYLE = "STYLE"
    DOCUMENTATION = "DOCUMENTATION"
    TESTING = "TESTING"
    COMPLEXITY = "COMPLEXITY"


class ValidationState(StrEnum):
    VERIFIED = "VERIFIED"
    GROUNDED = "GROUNDED"
    UNVERIFIED = "UNVERIFIED"
    REJECTED = "REJECTED"


class LineRange(Model):
    start: int = Field(ge=1)
    end: int = Field(ge=1)

    @model_validator(mode="after")
    def ordered(self) -> "LineRange":
        if self.end < self.start:
            raise ValueError("end must be >= start")
        return self


class ReviewRequest(Model):
    path: Path = Path(".")
    staged: bool = False
    diff: str | None = None
    no_ai: bool = False

    @model_validator(mode="after")
    def exclusive(self) -> "ReviewRequest":
        if self.staged and self.diff:
            raise ValueError("staged and diff are mutually exclusive")
        return self


class FileChange(Model):
    path: str
    language: str
    content: str
    changed_lines: list[LineRange] | None = None


class RepositoryContext(Model):
    root: str
    mode: Literal["repository", "file", "staged", "diff"]
    files: list[FileChange] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Symbol(Model):
    name: str
    lines: LineRange


class ASTContext(Model):
    file: str
    language: str
    symbols: list[Symbol] = Field(default_factory=list)
    code_lines: list[int] = Field(default_factory=list)
    error_lines: list[int] = Field(default_factory=list)


class SuggestedFix(Model):
    lines: LineRange
    original: str
    replacement: str
    explanation: str
    unified_diff: str | None = None


class ReviewFinding(Model):
    id: str = ""
    rule_id: str = Field(min_length=1, max_length=120)
    category: Category
    severity: Severity
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=6000)
    file: str
    lines: LineRange
    symbol: str | None = None
    code_snippet: str = ""
    evidence: list[str] = Field(default_factory=list)
    recommendation: str
    suggested_fix: SuggestedFix | None = None
    source: Literal["static", "ai"] = "static"
    analyzer: str
    validation: ValidationState = ValidationState.UNVERIFIED
    validation_notes: list[str] = Field(default_factory=list)


class StaticFinding(ReviewFinding):
    source: Literal["static"] = "static"


class AgentFinding(ReviewFinding):
    source: Literal["ai"] = "ai"


class ScorePenalty(Model):
    finding_id: str
    points: float
    explanation: str


class ReviewScore(Model):
    value: float = Field(ge=0, le=100)
    penalties: list[ScorePenalty]
    formula: str = "max(0, 100 - sum(severity_weight * confidence * validation_weight))"


class ReviewSummary(Model):
    files_reviewed: int
    severity_counts: dict[Severity, int]
    findings_count: int
    rejected_count: int
    duration_seconds: float


class ReviewReport(Model):
    schema_version: str = "1.0"
    root: str
    mode: str
    findings: list[ReviewFinding]
    rejected_findings: list[ReviewFinding]
    score: ReviewScore
    summary: ReviewSummary
    warnings: list[str]
    ai_status: Literal["disabled", "completed", "partial", "failed"]
