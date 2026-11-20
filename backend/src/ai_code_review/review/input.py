"""Normalize bounded source snapshots without executing reviewed source."""

import difflib
import os
import re
import shutil
import stat
from pathlib import Path
from typing import Literal

from ai_code_review.analysis.language import detect_language
from ai_code_review.core.config import Settings
from ai_code_review.core.exceptions import InputError
from ai_code_review.core.models import FileChange, LineRange, RepositoryContext, ReviewRequest
from ai_code_review.review.git import base_entries, git, index_entries, read_blob

EXCLUDED = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".aicr",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".next",
}
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def parse_diff_ranges(diff: str) -> list[LineRange]:
    """New-side hunk ranges; pure deletions have no reviewable new lines."""
    ranges = []
    for match in HUNK.finditer(diff):
        start, count = int(match[1]), int(match[2] or 1)
        if count:
            ranges.append(LineRange(start=start, end=start + count - 1))
    return ranges


def _is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    # Junctions on Python 3.11 Windows; do not reject ordinary OneDrive placeholders.
    try:
        info = path.lstat()
        return getattr(info, "st_reparse_tag", 0) == stat.IO_REPARSE_TAG_MOUNT_POINT
    except (OSError, AttributeError):
        return False


def _safe_path(root: Path, name: str) -> Path | None:
    path = root / name
    if any(part in EXCLUDED for part in Path(name).parts):
        return None
    if not path.resolve().is_relative_to(root):
        return None
    current = path
    while current != root:
        if _is_link(current):
            return None
        current = current.parent
    return path


def _directory_names(root: Path, is_git: bool) -> list[str]:
    if is_git:
        names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--")
        return [n.decode("utf-8") for n in names.split(b"\0") if n]
    candidates: list[str] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not _is_link(Path(current) / d))
        candidates.extend((Path(current) / f).relative_to(root).as_posix() for f in files)
    return candidates


def normalize(request: ReviewRequest, settings: Settings) -> RepositoryContext:
    """Normalize file, directory, staged index, or base-to-worktree changes."""
    raw = request.path.expanduser().absolute()
    if _is_link(raw):
        raise InputError("Symlink/junction inputs are not reviewed")
    target = raw.resolve()
    if not target.exists():
        raise InputError(f"Input does not exist: {target}")
    directory = target if target.is_dir() else target.parent
    is_git = True
    try:
        root = Path(git(directory, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    except InputError:
        if shutil.which("git") and any(
            (p / ".git").exists() for p in [directory, *directory.parents]
        ):
            raise
        root, is_git = directory, False
    mode: Literal["staged", "diff", "file", "repository"] = (
        "staged"
        if request.staged
        else "diff"
        if request.diff
        else "file"
        if target.is_file()
        else "repository"
    )
    context = RepositoryContext(root=str(root), mode=mode)
    baseline: dict[str, str] = {}
    index: dict[str, str] = {}
    if request.staged or request.diff:
        if not is_git:
            raise InputError("Diff review requires a Git repository")
        baseline, index = base_entries(root, request.diff), index_entries(root)
        candidates = sorted(set(baseline) | set(index))
        context.warnings.append(
            "Diff scope: changed new-side lines only; deleted code is not analyzed."
        )
    elif target.is_file():
        candidates = [target.relative_to(root).as_posix()]
    else:
        candidates = _directory_names(root, is_git)
        if not is_git:
            context.warnings.append(
                "No Git repository: built-in excludes apply; .gitignore is not read."
            )
    total = 0
    for name in sorted(set(candidates)):
        path = _safe_path(root, name)
        if path is None or not (path == target or path.is_relative_to(target)):
            continue
        language = detect_language(name)
        if language is None:
            if target.is_file():
                raise InputError("Unsupported file; supported: Python, JavaScript, TypeScript, TSX")
            continue
        if request.staged and (name not in index or index.get(name) == baseline.get(name)):
            continue
        if len(context.files) >= settings.max_files:
            context.warnings.append("File count limit reached; review is incomplete.")
            break
        try:
            if request.staged:
                data = read_blob(root, index[name], settings.max_file_bytes)
            else:
                if not path.is_file():
                    continue
                with path.open("rb") as stream:
                    data = stream.read(settings.max_file_bytes + 1)
            if data is None or len(data) > settings.max_file_bytes:
                context.warnings.append(f"Skipped oversized file: {name}")
                continue
            if b"\0" in data:
                context.warnings.append(f"Skipped binary file: {name}")
                continue
            source = data.decode("utf-8-sig")
            previous = b""
            if name in baseline:
                old = read_blob(root, baseline[name], settings.max_file_bytes)
                if old is None or b"\0" in old:
                    context.warnings.append(f"Skipped oversized/binary diff baseline: {name}")
                    continue
                previous = old
            before = previous.decode("utf-8-sig")
        except (OSError, UnicodeError) as exc:
            context.warnings.append(
                f"Skipped unreadable/non-UTF8 file: {name} ({type(exc).__name__})"
            )
            continue
        total += len(data) + len(previous)
        if total > settings.max_total_bytes:
            context.warnings.append("Total byte limit reached; review is incomplete.")
            break
        ranges = None
        if request.staged or request.diff:
            # In-memory diff of literal source avoids executable Git clean/textconv filters.
            # Normalize line endings for matching only; retain exact snapshot bytes for patches.
            patch = "\n".join(difflib.unified_diff(before.splitlines(), source.splitlines(), n=0))
            ranges = parse_diff_ranges(patch)
            if not ranges:
                continue
        context.files.append(
            FileChange(path=name, content=source, language=language, changed_lines=ranges)
        )
    if not context.files:
        context.warnings.append(
            "No supported source files in review scope; score is not assurance."
        )
    return context
