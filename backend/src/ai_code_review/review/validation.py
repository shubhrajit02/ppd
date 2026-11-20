"""Ground locations and evidence; location validity does not prove an AI claim."""

from ai_code_review.core.models import ASTContext, FileChange, ReviewFinding, ValidationState
from ai_code_review.review.patching import generate_patch


def validate(
    item: ReviewFinding, files: dict[str, FileChange], contexts: dict[str, ASTContext]
) -> ReviewFinding:
    result = ReviewFinding.model_validate(item.model_dump())
    result.validation = ValidationState.UNVERIFIED
    result.validation_notes = []
    file = files.get(item.file)
    reason = ""
    if file is None:
        reason = "Referenced file is not in the reviewed snapshot."
    elif item.lines.end > len(file.content.splitlines()):
        reason = "Referenced line range is outside the file."
    elif file.changed_lines is not None and not any(
        item.lines.start <= r.end and item.lines.end >= r.start for r in file.changed_lines
    ):
        reason = "Referenced lines do not intersect the reviewed diff."
    if reason:
        result.validation = ValidationState.REJECTED
        result.validation_notes = [reason]
        result.suggested_fix = None
        return result
    assert file is not None
    snippet = "\n".join(file.content.splitlines()[item.lines.start - 1 : item.lines.end])
    context = contexts[item.file]
    if item.symbol and not any(
        s.name == item.symbol
        and s.lines.start <= item.lines.start
        and s.lines.end >= item.lines.end
        for s in context.symbols
    ):
        reason = "Referenced symbol does not enclose this location in the syntax tree."
    elif item.source == "ai" and (
        not item.code_snippet.strip() or item.code_snippet.strip() not in snippet
    ):
        reason = "AI evidence does not match the cited source lines."
    elif item.source == "ai" and not any(
        item.lines.start <= line <= item.lines.end for line in context.code_lines
    ):
        reason = "No executable syntax token at the cited location."
    elif item.source == "ai" and context.error_lines:
        reason = "File has parse errors; AI evidence cannot be reliably grounded."
    if reason:
        result.validation_notes.append(reason)
    else:
        result.validation = (
            ValidationState.VERIFIED if item.source == "static" else ValidationState.GROUNDED
        )
        result.validation_notes.append("Source location and syntax evidence match the snapshot.")
    if item.source == "ai":
        result.confidence = min(result.confidence, 0.85)
        result.validation_notes.append("Grounding does not establish semantic correctness.")
    result.code_snippet = snippet
    result.evidence = [f"{item.file}:{item.lines.start}-{item.lines.end}", snippet]
    if result.suggested_fix:
        patch = generate_patch(file.path, file.content, result.suggested_fix)
        fix_in_scope = (
            item.lines.start <= result.suggested_fix.lines.start
            and result.suggested_fix.lines.end <= item.lines.end
        )
        if (
            result.validation in {ValidationState.UNVERIFIED, ValidationState.REJECTED}
            or not patch
            or not fix_in_scope
        ):
            result.suggested_fix = None
            result.validation_notes.append(
                "Fix omitted: ungrounded finding, mismatched preimage or out-of-scope edit."
            )
        else:
            result.suggested_fix.unified_diff = patch
    return result
