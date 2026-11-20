"""FastAPI composition root. Start with aicr-api; loopback binding is intentional."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ai_code_review.api.config import WebSettings
from ai_code_review.api.middleware import ALLOWED_ORIGINS, LocalBoundary
from ai_code_review.api.routes import router
from ai_code_review.api.schemas import APIError, ErrorResponse
from ai_code_review.api.services.jobs import ReviewJobs
from ai_code_review.api.services.storage import ReviewStore
from ai_code_review.core.config import Settings
from ai_code_review.integrations.github import GitHubImporter


def create_app(
    web_settings: WebSettings | None = None,
    core_settings: Settings | None = None,
    importer: GitHubImporter | None = None,
) -> FastAPI:
    web = web_settings or WebSettings()
    core = core_settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = ReviewStore(web.data_dir, web.source_retention_hours)
        runner = ReviewJobs(database, web, core, importer)
        app.state.store, app.state.jobs = database, runner
        app.state.web_settings, app.state.core_settings = web, core
        yield
        runner.close()

    app = FastAPI(
        title="AICR Review API",
        version="0.2.0",
        lifespan=lifespan,
        description="Local-only review jobs over the shared CLI engine. "
        "Mutations require X-AICR-Client: web. No patch is applied automatically.",
        responses={
            code: {"model": ErrorResponse} for code in [403, 404, 409, 410, 413, 422, 429, 502]
        },
    )
    app.add_middleware(LocalBoundary, max_bytes=web.max_payload_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(ALLOWED_ORIGINS),
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-AICR-Client"],
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )

    @app.exception_handler(APIError)
    async def api_error(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse({"error": exc.code, "detail": exc.detail}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic error dictionaries contain input values; never echo source or secrets.
        locations = [".".join(str(part) for part in error["loc"]) for error in exc.errors()]
        return JSONResponse(
            {
                "error": "validation_error",
                "detail": "Invalid request fields: " + ", ".join(locations[:8]),
            },
            status_code=422,
        )

    app.include_router(router)
    return app


def run() -> None:
    import uvicorn

    settings = WebSettings()
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port, access_log=False)


if __name__ == "__main__":
    run()
