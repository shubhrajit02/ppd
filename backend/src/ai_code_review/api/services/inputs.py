"""Normalize browser source and validate complete post-change diff snapshots."""

import re
from dataclasses import dataclass

from ai_code_review.analysis.language import detect_language
from ai_code_review.api.config import WebSettings
from ai_code_review.api.schemas import (
    APIError,
    CreateReview,
    SourceFile,
    UploadedFile,
    safe_filename,
)
from ai_code_review.core.models import LineRange, RepositoryContext

DEMO_FILES = [
    UploadedFile(
        path="src/runner.py",
        content='''"""Example command runner for an explicit demonstration review."""
import subprocess


def run_command(command, history=[]):
    history.append(command)
    subprocess.run(command, shell=True)
    return history
''',
    ),
    UploadedFile(
        path="src/evaluate.ts",
        content="""export function evaluate(source: string): unknown {
    debugger;
    return eval(source);
}
""",
    ),
    UploadedFile(
        path="src/metrics.py",
        content="""def compare_records(records):
    for left in records:
        for right in records:
            print(left, right)
""",
    ),
]
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class PreparedInput:
    context: RepositoryContext
    sources: list[SourceFile]


def validate_budget(files: list[UploadedFile], settings: WebSettings) -> None:
    if len(files) > settings.max_files:
        raise APIError(413, "too_many_files", f"Select at most {settings.max_files} source files")
    if sum(len(f.content.encode("utf-8")) for f in files) > settings.max_source_bytes:
        raise APIError(413, "source_too_large", "Combined source exceeds the server's byte budget")


def diff_sources(patch: str, files: list[UploadedFile]) -> list[SourceFile]:
    """Check hunk counts and new-side text against supplied full source, without applying it."""
    uploaded = {f.path: f for f in files}
    ranges: dict[str, list[LineRange]] = {}
    chunks: dict[str, list[str]] = {}
    path: str | None = None
    old_left = new_left = new_line = 0
    in_hunk = False
    for line in patch.splitlines():
        if line.startswith("\\ No newline"):
            continue
        if in_hunk and (old_left or new_left):
            if line.startswith((" ", "+")):
                if new_left <= 0 or path not in uploaded:
                    raise APIError(422, "invalid_diff", "Hunk exceeds supplied new source")
                source_lines = uploaded[path].content.splitlines()
                if (
                    new_line < 1
                    or new_line > len(source_lines)
                    or source_lines[new_line - 1] != line[1:]
                ):
                    raise APIError(
                        422, "diff_mismatch", "Diff does not match the post-change source"
                    )
                if line.startswith("+"):
                    ranges[path].append(LineRange(start=new_line, end=new_line))
                new_line += 1
                new_left -= 1
            if line.startswith((" ", "-")):
                old_left -= 1
            if not line.startswith((" ", "+", "-")) or old_left < 0:
                raise APIError(422, "invalid_diff", "Invalid or truncated unified diff hunk")
            if path is not None:
                chunks[path].append(line)
            continue
        if line.startswith("+++ "):
            name = line[4:].split("\t", 1)[0]
            if name == "/dev/null":
                path = None
                continue
            name = name[2:] if name.startswith("b/") else name
            try:
                path = safe_filename(name)
            except ValueError as exc:
                raise APIError(422, "invalid_diff", "Unsafe or unsupported diff filename") from exc
            if path not in uploaded:
                raise APIError(
                    422, "missing_source", f"Provide complete post-change source for {path}"
                )
            ranges.setdefault(path, [])
            chunks[path] = [f"--- a/{path}", f"+++ b/{path}"]
            in_hunk = False
        elif match := HUNK.match(line):
            if path is None:
                # Deleted-only files have no post-change source to analyze.
                continue
            old_left, new_left = int(match[2] or 1), int(match[4] or 1)
            new_line = int(match[3])
            in_hunk = True
            chunks[path].append(line)
    if in_hunk and (old_left or new_left):
        raise APIError(422, "truncated_diff", "The final diff hunk is incomplete")
    if not ranges:
        raise APIError(422, "empty_diff", "No supported post-change files were found in the diff")
    return [
        SourceFile(
            path=name,
            content=uploaded[name].content,
            language=detect_language(name) or "",
            changed_lines=lines,
            patch="\n".join(chunks[name]) + "\n",
        )
        for name, lines in ranges.items()
    ]


def prepare_local(request: CreateReview, settings: WebSettings) -> PreparedInput:
    files = DEMO_FILES if request.kind == "demo" else request.files
    validate_budget(files, settings)
    sources = (
        diff_sources(request.diff, files)
        if request.kind == "diff"
        else [
            SourceFile(path=f.path, content=f.content, language=detect_language(f.path) or "")
            for f in sorted(files, key=lambda f: f.path)
        ]
    )
    warnings = []
    if request.kind == "demo":
        warnings.append(
            "Explicit demo: intentionally unsafe example source, analyzed by the real engine."
        )
    if request.kind == "diff":
        warnings.append("Diff scope: changed new-side lines only; deleted code is not analyzed.")
    context = RepositoryContext(
        root=request.title,
        mode="diff" if request.kind == "diff" else "repository",
        files=[f.core_file() for f in sources],
        warnings=warnings,
    )
    return PreparedInput(context, sources)
