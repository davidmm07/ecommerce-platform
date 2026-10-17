import logging
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ecommerce.application.errors import (
    ApplicationError,
    ConcurrentModification,
    DuplicateSku,
    IdempotencyKeyReused,
    ImageSourceUnavailable,
    ImageTooLarge,
    ImportLimitExceeded,
    InvalidImage,
    InvalidImageSource,
    InvalidImportFile,
    NotFoundError,
    PaymentDeclined,
    PaymentUnavailable,
    RequestInProgress,
    UnsupportedImageType,
    VersionMismatch,
)
from ecommerce.domain.catalog.errors import InsufficientStock, ProductUnavailable
from ecommerce.domain.errors import DomainError, DomainValidationError, InvalidValue
from ecommerce.domain.ordering.errors import InvalidOrderTransition

PROBLEM_JSON = "application/problem+json"

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProblemType:
    status: int
    title: str


PROBLEM_TYPES: dict[type[Exception], ProblemType] = {
    DomainValidationError: ProblemType(422, "Validation failed"),
    InvalidValue: ProblemType(422, "Invalid value"),
    InsufficientStock: ProblemType(409, "Insufficient stock"),
    ProductUnavailable: ProblemType(409, "Product unavailable"),
    InvalidOrderTransition: ProblemType(409, "Invalid order transition"),
    NotFoundError: ProblemType(404, "Resource not found"),
    DuplicateSku: ProblemType(409, "Duplicate SKU"),
    ConcurrentModification: ProblemType(409, "Concurrent modification"),
    RequestInProgress: ProblemType(409, "Request in progress"),
    IdempotencyKeyReused: ProblemType(422, "Idempotency key reused"),
    VersionMismatch: ProblemType(412, "Precondition failed"),
    PaymentDeclined: ProblemType(402, "Payment declined"),
    PaymentUnavailable: ProblemType(502, "Payment provider unavailable"),
    InvalidImportFile: ProblemType(422, "Invalid import file"),
    ImportLimitExceeded: ProblemType(413, "Import too large"),
    InvalidImage: ProblemType(422, "Invalid image"),
    UnsupportedImageType: ProblemType(415, "Unsupported image type"),
    ImageTooLarge: ProblemType(413, "Image too large"),
    InvalidImageSource: ProblemType(422, "Image URL not allowed"),
    ImageSourceUnavailable: ProblemType(502, "Image URL unavailable"),
}
_FALLBACK = ProblemType(400, "Bad request")


def problem_type_for(exc: Exception) -> ProblemType:
    for cls in type(exc).__mro__:
        problem = PROBLEM_TYPES.get(cls)
        if problem is not None:
            return problem
    return _FALLBACK


def request_id_of(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None


def problem_response(
    request: Request,
    *,
    status: int,
    title: str,
    code: str,
    detail: str,
    extensions: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = request_id_of(request)
    body: dict[str, Any] = {
        "type": f"urn:ecommerce:problem:{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "request_id": request_id,
        **(extensions or {}),
    }
    response_headers = dict(headers or {})
    if request_id:
        response_headers["X-Request-ID"] = request_id
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=response_headers)


async def _handle_known_error(
    request: Request, exc: DomainError | ApplicationError
) -> JSONResponse:
    problem = problem_type_for(exc)
    if problem.status >= 500:
        logger.error("dependency failure", extra={"code": exc.code, "detail": exc.message})
    return problem_response(
        request,
        status=problem.status,
        title=problem.title,
        code=exc.code,
        detail=exc.message,
        extensions=exc.details(),
    )


async def _handle_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": _field_path(error.get("loc", ())), "message": str(error.get("msg", "invalid"))}
        for error in exc.errors()
    ]
    return problem_response(
        request,
        status=422,
        title="Validation failed",
        code="validation_failed",
        detail="; ".join(f"{e['field']}: {e['message']}" for e in errors),
        extensions={"errors": errors},
    )


async def _handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    title = _HTTP_TITLES.get(exc.status_code, "Request failed")
    return problem_response(
        request,
        status=exc.status_code,
        title=title,
        code=title.lower().replace(" ", "_"),
        detail=detail,
        headers=dict(exc.headers) if exc.headers else None,
    )


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error", exc_info=exc)
    return problem_response(
        request,
        status=500,
        title="Internal server error",
        code="internal_error",
        detail="An unexpected error occurred, quote the request_id when reporting it",
    )


def install_problem_handlers(app: FastAPI) -> None:
    app.exception_handler(DomainError)(_handle_known_error)
    app.exception_handler(ApplicationError)(_handle_known_error)
    app.exception_handler(RequestValidationError)(_handle_request_validation)
    app.exception_handler(StarletteHTTPException)(_handle_http_error)
    app.exception_handler(Exception)(_handle_unexpected)


_HTTP_TITLES = {
    400: "Bad request",
    404: "Not found",
    405: "Method not allowed",
    413: "Payload too large",
    415: "Unsupported media type",
    428: "Precondition required",
}


def _field_path(location: tuple[int | str, ...] | list[int | str]) -> str:
    parts = [part for part in location if part not in {"body", "query", "path"}]
    path = ""
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}" if path else str(part)
    return path or "request"
