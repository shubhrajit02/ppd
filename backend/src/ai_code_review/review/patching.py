"""Generate suggestions only; never write reviewed source files."""

import difflib
from pathlib import PurePosixPath

from ai_code_review.core.models import SuggestedFix


def generate_patch(path: str, content: str, fix: SuggestedFix) -> str | None:
    """Require an exact whole-line preimage and a safe relative path."""
    if (
        PurePosixPath(path).is_absolute()
        or ".." in PurePosixPath(path).parts
        or any(c in path for c in '\r\n\t\\:"')
    ):
        return None
    lines = content.splitlines(keepends=True)
    if fix.lines.end > len(lines):
        return None
    original = "".join(lines[fix.lines.start - 1 : fix.lines.end])
    if not original or original != fix.original:
        return None
    if fix.replacement and not fix.replacement.endswith("\n") and fix.lines.end < len(lines):
        return None
    new = "".join(lines[: fix.lines.start - 1]) + fix.replacement + "".join(lines[fix.lines.end :])
    chunks = difflib.unified_diff(
        content.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return (
        "".join(
            chunk if chunk.endswith("\n") else chunk + "\n\\ No newline at end of file\n"
            for chunk in chunks
        )
        or None
    )
