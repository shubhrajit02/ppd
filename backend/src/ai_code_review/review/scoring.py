"""Explainable heuristic prioritization; not a security certification."""

from ai_code_review.core.models import ReviewFinding, ReviewScore, ScorePenalty, Severity
from ai_code_review.core.models import ValidationState as State

SEVERITY_WEIGHTS = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 12,
    Severity.MEDIUM: 5,
    Severity.LOW: 2,
    Severity.INFO: 0,
}
VALIDATION_WEIGHTS = {
    State.VERIFIED: 1.0,
    State.GROUNDED: 0.5,
    State.UNVERIFIED: 0.0,
    State.REJECTED: 0.0,
}


def score(findings: list[ReviewFinding]) -> ReviewScore:
    penalties = []
    for item in findings:
        severity, validation = SEVERITY_WEIGHTS[item.severity], VALIDATION_WEIGHTS[item.validation]
        points = round(severity * item.confidence * validation, 3)
        penalties.append(
            ScorePenalty(
                finding_id=item.id,
                points=points,
                explanation=f"{item.severity}({severity}) * confidence({item.confidence}) "
                f"* {item.validation}({validation})",
            )
        )
    return ReviewScore(
        value=round(max(0, 100 - sum(p.points for p in penalties)), 2), penalties=penalties
    )
