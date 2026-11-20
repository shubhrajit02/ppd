"""Single shared engine for filesystem callers and normalized snapshot adapters."""

import logging
from collections.abc import Callable
from time import perf_counter
from typing import Literal

from ai_code_review.agents.coordinator import coordinate
from ai_code_review.analysis.ast import parse
from ai_code_review.analysis.static import analyze
from ai_code_review.core.config import Settings
from ai_code_review.core.logging import event
from ai_code_review.core.models import (
    RepositoryContext,
    ReviewFinding,
    ReviewReport,
    ReviewRequest,
    ReviewSummary,
    Severity,
    ValidationState,
)
from ai_code_review.core.progress import PipelineEvent, Stage
from ai_code_review.llm.providers import LLMProvider, create_provider
from ai_code_review.review.deduplication import deduplicate
from ai_code_review.review.input import normalize
from ai_code_review.review.scoring import score
from ai_code_review.review.validation import validate

logger = logging.getLogger(__name__)
EventSink = Callable[[PipelineEvent], None]


class ReviewEngine:
    """One pipeline, no source mutation. Event callbacks may request cancellation."""

    def __init__(self, settings: Settings | None = None, provider: LLMProvider | None = None):
        self.settings = settings or Settings()
        self.provider = provider

    def review(
        self,
        request: ReviewRequest,
        progress: Callable[[str], None] | None = None,
        *,
        on_event: EventSink | None = None,
    ) -> ReviewReport:
        """Existing CLI/library entry point; normalize local filesystem input."""
        started = perf_counter()
        if progress:
            progress("Scanning source snapshots")
        if on_event:
            on_event(PipelineEvent(stage=Stage.SCANNING, label="Reading source snapshots"))
        repository = normalize(request, self.settings)
        return self.review_context(
            repository, no_ai=request.no_ai, progress=progress, on_event=on_event, started=started
        )

    def review_context(
        self,
        repository: RepositoryContext,
        *,
        no_ai: bool = False,
        progress: Callable[[str], None] | None = None,
        on_event: EventSink | None = None,
        started: float | None = None,
    ) -> ReviewReport:
        """Analyze an already normalized snapshot through the same CLI pipeline.

        Input adapters own transport validation and size limits. Source is untrusted
        data. No files, Git operations or web requests are introduced by this method.
        """
        started = started if started is not None else perf_counter()
        total = len(repository.files)

        def emit(
            stage: Stage,
            label: str,
            state: Literal["RUNNING", "COMPLETED", "SKIPPED", "FAILED"] = "RUNNING",
            completed: int = 0,
            findings: int = 0,
            duration: float = 0,
            agent: str | None = None,
        ) -> None:
            if progress:
                progress(label)
            if on_event:
                on_event(
                    PipelineEvent(
                        stage=stage,
                        label=label,
                        state=state,
                        completed=completed,
                        total=total,
                        findings=findings,
                        duration_seconds=round(duration, 3),
                        agent=agent,
                    )
                )

        emit(Stage.SCANNING, f"{total} source files indexed", "COMPLETED", total)
        parsing_start = perf_counter()
        emit(Stage.PARSING, "Parsing source syntax")
        parsed = {}
        for index, file in enumerate(repository.files, 1):
            parsed[file.path] = parse(file)
            emit(Stage.PARSING, f"Parsed {index} of {total} files", completed=index)
        contexts = {path: pair[0] for path, pair in parsed.items()}
        emit(
            Stage.PARSING,
            "Syntax parsing complete",
            "COMPLETED",
            total,
            duration=perf_counter() - parsing_start,
        )
        analysis_start = perf_counter()
        emit(Stage.STATIC_ANALYSIS, "Running deterministic rules")
        candidates: list[ReviewFinding] = []
        for index, file in enumerate(repository.files, 1):
            context, tree = parsed[file.path]
            candidates.extend(analyze(file, context, tree))
            emit(
                Stage.STATIC_ANALYSIS,
                f"Analyzed {index} of {total} files",
                completed=index,
                findings=len(candidates),
            )
        emit(
            Stage.STATIC_ANALYSIS,
            "Deterministic analysis complete",
            "COMPLETED",
            total,
            len(candidates),
            perf_counter() - analysis_start,
        )
        del parsed
        ai_status: Literal["disabled", "completed", "partial", "failed"] = "disabled"
        provider = None if no_ai else self.provider or create_provider(self.settings)

        def agent_event(name: str, state: str, count: int, duration: float) -> None:
            emit(
                Stage.AI_ANALYSIS,
                f"{name.title()} specialist",
                state=state,  # type: ignore[arg-type]
                findings=count,
                duration=duration,
                agent=name,
            )

        if provider is not None:
            ai_start = perf_counter()
            emit(Stage.AI_ANALYSIS, "Running local AI specialists")
            found, warnings, calls, failures = coordinate(
                repository.files, contexts, provider, self.settings, agent_event
            )
            candidates.extend(found)
            repository.warnings.extend(warnings)
            ai_status = (
                "failed"
                if failures == calls and failures
                else ("partial" if warnings or not calls else "completed")
            )
            emit(
                Stage.AI_ANALYSIS,
                f"Local AI {ai_status}",
                "FAILED" if ai_status == "failed" else "COMPLETED",
                findings=len(found),
                duration=perf_counter() - ai_start,
            )
        else:
            emit(Stage.AI_ANALYSIS, "AI disabled; deterministic review is available", "SKIPPED")
        validation_start = perf_counter()
        emit(Stage.VALIDATING, "Checking source evidence and locations")
        files = {file.path: file for file in repository.files}
        validated = [validate(item, files, contexts) for item in candidates]
        emit(
            Stage.VALIDATING,
            "Evidence validation complete",
            "COMPLETED",
            findings=sum(f.validation != ValidationState.REJECTED for f in validated),
            duration=perf_counter() - validation_start,
        )
        emit(Stage.SYNTHESIZING, "Deduplicating and calculating score")
        merged = deduplicate(validated)
        accepted = [f for f in merged if f.validation != ValidationState.REJECTED]
        rejected = [f for f in merged if f.validation == ValidationState.REJECTED]
        duration = round(perf_counter() - started, 3)
        report = ReviewReport(
            root=repository.root,
            mode=repository.mode,
            findings=accepted,
            rejected_findings=rejected,
            score=score(accepted),
            warnings=repository.warnings,
            ai_status=ai_status,
            summary=ReviewSummary(
                files_reviewed=total,
                findings_count=len(accepted),
                rejected_count=len(rejected),
                duration_seconds=duration,
                severity_counts={s: sum(f.severity == s for f in accepted) for s in Severity},
            ),
        )
        emit(Stage.SYNTHESIZING, "Review report ready", "COMPLETED", total, len(accepted), duration)
        event(logger, "review_completed", files=total, findings=len(accepted), seconds=duration)
        return report
