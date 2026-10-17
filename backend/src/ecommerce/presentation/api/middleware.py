import logging
import re
import time
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ecommerce.infrastructure.logging import request_id_var
from ecommerce.presentation.api.problems import PROBLEM_JSON

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
}

access_logger = logging.getLogger("ecommerce.access")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        request_id = _incoming_request_id(scope) or uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500

        async def send_with_headers(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                for name, value in _SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        try:
            await self._app(scope, receive, send_with_headers)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            if not scope["path"].startswith("/health/"):
                _log_access(scope, status, duration_ms)
            request_id_var.reset(token)


def _log_access(scope: Scope, status: int, duration_ms: float) -> None:
    access_logger.info(
        "%s %s %s %sms",
        scope["method"],
        scope["path"],
        status,
        duration_ms,
        extra={
            "method": scope["method"],
            "path": scope["path"],
            "status": status,
            "duration_ms": duration_ms,
        },
    )


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        declared = _content_length(scope)
        if declared is not None and declared > self._max_bytes:
            await self._too_large_response(scope)(scope, receive, send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    raise HTTPException(status_code=413, detail=self._detail)
            return message

        await self._app(scope, limited_receive, send)

    @property
    def _detail(self) -> str:
        return f"The request body must not exceed {self._max_bytes} bytes"

    def _too_large_response(self, scope: Scope) -> JSONResponse:
        return JSONResponse(
            {
                "type": "urn:ecommerce:problem:payload_too_large",
                "title": "Payload too large",
                "status": 413,
                "detail": self._detail,
                "instance": scope["path"],
                "code": "payload_too_large",
                "request_id": scope.get("state", {}).get("request_id"),
            },
            status_code=413,
            media_type=PROBLEM_JSON,
        )


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope["headers"]:
        if name == b"x-request-id":
            candidate = value.decode("latin-1")
            return candidate if _REQUEST_ID.fullmatch(candidate) else None
    return None


def _content_length(scope: Scope) -> int | None:
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None
