"""Professional offline-first CLI over the shared engine."""

import json
import shutil
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from ai_code_review import __version__
from ai_code_review.analysis.ast import grammar
from ai_code_review.cli.renderers import markdown, render_terminal
from ai_code_review.core.config import load_settings
from ai_code_review.core.exceptions import ReviewError
from ai_code_review.core.models import ReviewReport, ReviewRequest, Severity
from ai_code_review.review.engine import ReviewEngine

app = typer.Typer(no_args_is_help=True, help="Offline-first, AST-grounded code review.")
config_app = typer.Typer(help="Inspect configuration without exposing secrets.")
app.add_typer(config_app, name="config")


class OutputFormat(StrEnum):
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"


def severity_value(value: str | None) -> Severity | None:
    try:
        return Severity(value.upper()) if value else None
    except ValueError as exc:
        raise typer.BadParameter("Severity must be critical, high, medium, low or info") from exc


@app.command()
def review(
    path: Annotated[Path, typer.Argument(help="Source file or directory")] = Path("."),
    staged: Annotated[bool, typer.Option(help="Review index content against HEAD")] = False,
    diff: Annotated[
        str | None, typer.Option(help="Review tracked worktree changes against a commit")
    ] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.TEXT,
    severity: Annotated[str | None, typer.Option(help="Minimum severity to display")] = None,
    no_ai: Annotated[
        bool, typer.Option("--no-ai", help="Force offline deterministic analysis")
    ] = False,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write report; never overwrite")
    ] = None,
    save_report: Annotated[
        Path | None, typer.Option(help="Save full JSON for explain; never overwrite")
    ] = None,
    env_file: Annotated[
        Path | None, typer.Option(help="Explicit dotenv configuration file")
    ] = None,
    fail_on: Annotated[
        str | None, typer.Option(help="Exit 1 for grounded findings at this severity")
    ] = None,
) -> None:
    """Review source without modifying it. Exit codes: 0 success, 1 quality gate, 2 error."""
    minimum, gate = severity_value(severity), severity_value(fail_on)
    try:
        if output_format == OutputFormat.JSON and minimum is not None:
            raise typer.BadParameter(
                "--severity filters text/Markdown only; JSON is always complete"
            )
        for destination in (output, save_report):
            if destination and destination.exists():
                raise typer.BadParameter(f"Output already exists: {destination}")
        if output and save_report and output.resolve() == save_report.resolve():
            raise typer.BadParameter("--output and --save-report must be different paths")
        settings = load_settings(env_file, no_ai=no_ai)
        request = ReviewRequest(path=path, staged=staged, diff=diff, no_ai=no_ai)
        engine = ReviewEngine(settings)
        stderr = Console(stderr=True)
        if output_format == OutputFormat.TEXT and stderr.is_terminal:
            with stderr.status("Starting review") as status:
                report = engine.review(request, status.update)
        else:
            report = engine.review(request)
        if save_report:
            with save_report.open("x", encoding="utf-8") as stream:
                stream.write(report.model_dump_json(indent=2) + "\n")
        if output_format == OutputFormat.JSON:
            rendered = report.model_dump_json(indent=2) + "\n"
        elif output_format == OutputFormat.MARKDOWN:
            rendered = markdown(report, minimum)
        else:
            if output:
                with output.open("x", encoding="utf-8") as stream:
                    render_terminal(
                        report, Console(file=stream, width=100, color_system=None), minimum
                    )
            else:
                render_terminal(report, Console(), minimum)
            rendered = None
        if rendered is not None:
            if output:
                with output.open("x", encoding="utf-8") as stream:
                    stream.write(rendered)
            else:
                typer.echo(rendered, nl=False)
        if gate and any(
            f.severity.rank <= gate.rank and f.validation.value in {"VERIFIED", "GROUNDED"}
            for f in report.findings
        ):
            raise typer.Exit(1)
    except ValidationError:
        typer.echo("Error: invalid request or configuration; check options and settings", err=True)
        raise typer.Exit(2) from None
    except (ReviewError, OSError, UnicodeError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc


@app.command()
def explain(finding_id: str, report: Annotated[Path, typer.Option("--report")]) -> None:
    """Explain a finding from JSON explicitly saved by a previous review."""
    try:
        saved = ReviewReport.model_validate_json(report.read_text(encoding="utf-8"))
        for item in [*saved.findings, *saved.rejected_findings]:
            if item.id == finding_id:
                penalty = next(
                    (p.model_dump() for p in saved.score.penalties if p.finding_id == item.id), None
                )
                typer.echo(
                    json.dumps(
                        {"finding": item.model_dump(mode="json"), "scoring": penalty}, indent=2
                    )
                )
                return
        raise ReviewError("Finding ID not present in this report")
    except (OSError, ValueError, ReviewError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc


@config_app.command("show")
def config_show(env_file: Annotated[Path | None, typer.Option()] = None) -> None:
    try:
        settings = load_settings(env_file)
        typer.echo(settings.model_dump_json(indent=2))
    except ValueError:
        typer.echo("Invalid configuration; check provider, local URL and model settings", err=True)
        raise typer.Exit(2) from None


@app.command()
def doctor() -> None:
    """Check local prerequisites without network requests or model downloads."""
    typer.echo(f"aicr {__version__}")
    typer.echo(f"Git: {shutil.which('git') or 'missing (file/directory review still works)'}")
    for language in ("python", "javascript", "typescript", "tsx"):
        grammar(language)
        typer.echo(f"Tree-Sitter {language}: ready")
    typer.echo("Offline rules: ready. Local AI is optional; doctor makes no network calls.")


@app.command()
def version() -> None:
    """Show the installed version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
