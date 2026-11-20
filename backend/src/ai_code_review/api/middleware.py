"""Local browser request boundary and body limits, independent of route parsing."""

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ALLOWED_ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000"}


class LocalBoundary:
    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        write = scope["method"] in {"POST", "PATCH", "DELETE", "PUT"}
        if origin and origin not in ALLOWED_ORIGINS:
            await JSONResponse({"error": "origin_denied", "detail": "Origin is not allowed"}, 403)(
                scope, receive, send
            )
            return
        if write and headers.get("x-aicr-client") != "web":
            await JSONResponse(
                {"error": "client_header_required", "detail": "Send X-AICR-Client: web"}, 403
            )(scope, receive, send)
            return
        if not write:
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                await JSONResponse(
                    {
                        "error": "payload_too_large",
                        "detail": "Request body exceeds the server limit",
                    },
                    413,
                )(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
