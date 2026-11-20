"""Stable IDs and deterministic merging for repeated rule/location findings."""

import hashlib

from ai_code_review.core.models import ReviewFinding, ValidationState


def deduplicate(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    groups: dict[tuple[str, str, int, int], ReviewFinding] = {}
    weights = {
        ValidationState.VERIFIED: 3,
        ValidationState.GROUNDED: 2,
        ValidationState.UNVERIFIED: 1,
        ValidationState.REJECTED: 0,
    }
    for item in findings:
        key = (item.file, item.rule_id, item.lines.start, item.lines.end)
        item = item.model_copy(deep=True)
        item.id = hashlib.sha256(repr(key).encode()).hexdigest()[:16]
        existing = groups.get(key)
        if existing is None or (weights[item.validation], item.confidence, -item.severity.rank) > (
            weights[existing.validation],
            existing.confidence,
            -existing.severity.rank,
        ):
            groups[key] = item
    return sorted(groups.values(), key=lambda f: (f.severity.rank, f.file, f.lines.start, f.id))
