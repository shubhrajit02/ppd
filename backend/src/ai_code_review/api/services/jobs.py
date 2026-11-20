"""Bounded local job runner with cooperative cancellation and truthful events."""

import logging
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Event, Lock, Thread
from uuid import uuid4

from ai_code_review.api.config import WebSettings
from ai_code_review.api.schemas import APIError, CreateReview, ReviewItem
from ai_code_review.api.services.inputs import prepare_local, validate_budget
from ai_code_review.api.services.storage import ReviewStore
from ai_code_review.core.config import Settings
from ai_code_review.core.progress import PipelineEvent, ReviewCancelled, Stage
from ai_code_review.integrations.github import GitHubImporter, parse_github_url
from ai_code_review.review.engine import ReviewEngine

logger = logging.getLogger(__name__)


class ReviewJobs:
    def __init__(
        self,
        store: ReviewStore,
        settings: WebSettings,
        core_settings: Settings,
        importer: GitHubImporter | None = None,
    ):
        self.store, self.settings, self.core_settings = store, settings, core_settings
        self.importer = importer or GitHubImporter(settings)
        self.executor = ThreadPoolExecutor(max_workers=settings.workers, thread_name_prefix="aicr")
        self.capacity = BoundedSemaphore(settings.max_pending)
        self.lock = Lock()
        self.cancellations: dict[str, Event] = {}
        self.stopping = Event()
        self.store.recover()
        self.janitor = Thread(target=self._expire, daemon=True, name="aicr-retention")
        self.janitor.start()

    def _expire(self) -> None:
        while not self.stopping.wait(60):
            self.store.expire_sources()

    def submit(self, request: CreateReview) -> ReviewItem:
        if self.stopping.is_set():
            raise APIError(503, "server_stopping", "The server is shutting down")
        validate_budget(request.files, self.settings)
        source_url = None
        if request.kind in {"github", "pr"}:
            repository, number = parse_github_url(request.url, request.pr_number)
            if request.kind == "pr" and not number:
                raise APIError(422, "missing_pr_number", "Provide the pull request URL or number")
            if request.kind == "github" and number:
                raise APIError(422, "wrong_source_mode", "Choose pull request mode for a PR URL")
            source_url = f"https://github.com/{repository}" + (f"/pull/{number}" if number else "")
        if request.use_ai and self.core_settings.provider == "none":
            raise APIError(
                422, "provider_unavailable", "Configure a local model on the server or disable AI"
            )
        if not self.capacity.acquire(blocking=False):
            raise APIError(
                429, "queue_full", "The local review queue is full; wait for a job to finish"
            )
        review_id = uuid4().hex
        cancel = Event()
        try:
            item = self.store.create(review_id, request.title, request.kind, source_url)
            with self.lock:
                self.cancellations[review_id] = cancel
            self.executor.submit(self._run, review_id, request, cancel)
        except Exception:
            self.capacity.release()
            raise
        return item

    def _run(self, review_id: str, request: CreateReview, cancel: Event) -> None:
        def check_cancel() -> None:
            if cancel.is_set() or self.stopping.is_set():
                raise ReviewCancelled()

        def progress(item: PipelineEvent) -> None:
            check_cancel()
            self.store.event(review_id, item)

        try:
            progress(PipelineEvent(stage=Stage.SCANNING, label="Preparing source snapshot"))
            prepared = (
                self.importer.prepare(request, check_cancel)
                if request.kind in {"github", "pr"}
                else prepare_local(request, self.settings)
            )
            check_cancel()
            self.store.save_sources(review_id, prepared.sources)
            report = ReviewEngine(self.core_settings).review_context(
                prepared.context, no_ai=not request.use_ai, on_event=progress
            )
            check_cancel()
            self.store.finish(review_id, "COMPLETED", report=report)
        except ReviewCancelled:
            self.store.finish(review_id, "CANCELLED")
        except APIError as exc:
            self.store.finish(review_id, "FAILED", error=exc.detail)
        except Exception as exc:
            # Never log source, provider response bodies, credentials or user payloads.
            logger.error("Review job failed: %s", type(exc).__name__)
            self.store.finish(
                review_id,
                "FAILED",
                error="Review failed unexpectedly. Check server configuration and retry.",
            )
        finally:
            with self.lock:
                self.cancellations.pop(review_id, None)
            self.capacity.release()

    def cancel(self, review_id: str) -> None:
        self.store.request_cancel(review_id)
        with self.lock:
            signal = self.cancellations.get(review_id)
            if signal:
                signal.set()

    def close(self) -> None:
        self.stopping.set()
        with self.lock:
            for signal in self.cancellations.values():
                signal.set()
        self.executor.shutdown(wait=True)
        self.janitor.join(timeout=2)
