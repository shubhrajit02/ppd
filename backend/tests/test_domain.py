import math

import pytest
from pydantic import ValidationError

from ai_code_review.core.models import (
    AgentFinding,
    Category,
    LineRange,
    ReviewRequest,
    Severity,
    StaticFinding,
    ValidationState,
)
from ai_code_review.review.deduplication import deduplicate
from ai_code_review.review.scoring import score


def make_finding(**overrides):
    values = dict(
        rule_id="test",
        category=Category.BUG,
        severity=Severity.HIGH,
        confidence=1.0,
        title="Test",
        description="Evidence",
        file="main.py",
        lines=LineRange(start=1, end=1),
        recommendation="Fix it",
        analyzer="test",
    )
    values.update(overrides)
    return StaticFinding(**values)


@pytest.mark.parametrize("confidence", [-0.1, 1.1, math.nan, math.inf])
def test_confidence_bounds(confidence):
    with pytest.raises(ValidationError):
        make_finding(confidence=confidence)


def test_ranges_and_request():
    with pytest.raises(ValidationError):
        LineRange(start=2, end=1)
    with pytest.raises(ValidationError):
        LineRange(start=0, end=1)
    with pytest.raises(ValidationError):
        ReviewRequest(staged=True, diff="HEAD")
    assert Severity.CRITICAL.rank < Severity.HIGH.rank < Severity.INFO.rank
    with pytest.raises(ValidationError):
        make_finding(severity="urgent")


def test_scoring_explains_confidence_and_trust():
    trusted = make_finding(validation=ValidationState.VERIFIED, confidence=0.5)
    assert score([trusted]).value == 94
    trusted.validation = ValidationState.GROUNDED
    assert score([trusted]).value == 97
    trusted.validation = ValidationState.UNVERIFIED
    assert score([trusted]).value == 100
    trusted.validation = ValidationState.REJECTED
    assert score([trusted]).value == 100
    assert score([]).value == 100
    trusted.validation = ValidationState.VERIFIED
    assert score([trusted] * 100).value == 0
    assert "confidence(0.5)" in score([trusted]).penalties[0].explanation


def test_dedup_stable_id_and_prefer_static_evidence():
    trusted = make_finding(validation=ValidationState.VERIFIED)
    ai = AgentFinding(
        **{**trusted.model_dump(), "source": "ai", "validation": ValidationState.GROUNDED}
    )
    merged = deduplicate([ai, trusted])
    assert len(merged) == 1
    assert merged[0].source == "static"
    assert merged[0].id == deduplicate([trusted, ai])[0].id
    assert not trusted.id  # caller's objects unchanged
    other = make_finding(file="other.py")
    assert len(deduplicate([trusted, other])) == 2
