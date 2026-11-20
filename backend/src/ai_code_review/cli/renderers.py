"""Report formatting is independent of review rules."""

import re

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ai_code_review.core.models import ReviewFinding, ReviewReport, Severity


def visible(report: ReviewReport, severity: Severity | None) -> list[ReviewFinding]:
    return [f for f in report.findings if severity is None or f.severity.rank <= severity.rank]


def safe(text: str) -> str:
    """Strip terminal controls from untrusted source and model text."""
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", text)


def render_terminal(report: ReviewReport, console: Console, severity: Severity | None) -> None:
    console.print(
        Panel(Text(f"Repository: {safe(report.root)}\nMode: {report.mode}"), title="AI CODE REVIEW")
    )
    console.print(f"Review Score: {report.score.value:g} / 100 (full review scope)", markup=False)
    table = Table("Critical", "High", "Medium", "Low", "Info")
    table.add_row(*(str(report.summary.severity_counts[s]) for s in Severity))
    console.print(table)
    current_file = None
    for item in visible(report, severity):
        if current_file != item.file:
            console.print(Text(safe(item.file), style="bold cyan"))
            current_file = item.file
        console.print(
            Text(
                safe(
                    f"{item.severity} {item.title}\n"
                    f"Lines {item.lines.start}-{item.lines.end} | {item.id} | "
                    f"Confidence {item.confidence:.0%} | {item.validation}\n"
                    f"{item.description}\nEvidence: {item.code_snippet}\n"
                    f"Recommendation: {item.recommendation}\n"
                )
            )
        )
        if item.suggested_fix and item.suggested_fix.unified_diff:
            console.print(Text(safe(item.suggested_fix.unified_diff)))
    console.print(
        f"Files: {report.summary.files_reviewed} | AI: {report.ai_status} | "
        f"Duration: {report.summary.duration_seconds:.3f}s",
        markup=False,
    )
    for warning in report.warnings:
        console.print(Text("Warning: " + safe(warning), style="yellow"))


def markdown(report: ReviewReport, severity: Severity | None = None) -> str:
    def escape(value: str) -> str:
        return (
            safe(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("`", "\\`")
        )

    lines = [
        "# AI Code Review",
        "",
        f"Score: **{report.score.value:g}/100** (full review scope)",
        f"Files: {report.summary.files_reviewed} · AI: {report.ai_status} · "
        f"Duration: {report.summary.duration_seconds:.3f}s",
        "",
        " | ".join(f"{s.value}: {report.summary.severity_counts[s]}" for s in Severity),
        "",
    ]
    for item in visible(report, severity):
        lines.extend(
            [
                f"## {item.severity}: {escape(item.title)}",
                "",
                f"{escape(item.file)}:{item.lines.start}-{item.lines.end} · ID: {item.id}",
                f"Confidence: {item.confidence:.0%} · Validation: {item.validation}",
                "",
                escape(item.description),
                "",
                "Evidence:",
                "",
                *["    " + safe(line) for line in item.code_snippet.splitlines()],
                "",
                "Recommendation: " + escape(item.recommendation),
                "",
            ]
        )
        if item.suggested_fix and item.suggested_fix.unified_diff:
            lines.extend(
                [
                    "Suggested patch (review before applying):",
                    "",
                    *["    " + safe(line) for line in item.suggested_fix.unified_diff.splitlines()],
                    "",
                ]
            )
    lines.extend(["## Scoring", "", report.score.formula, ""])
    lines.extend(
        f"- {p.finding_id}: {p.points:g} points — {p.explanation}" for p in report.score.penalties
    )
    lines.extend(["", "## Warnings", ""] if report.warnings else [])
    lines.extend("- " + escape(w) for w in report.warnings)
    return "\n".join(lines) + "\n"
