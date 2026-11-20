"""Errors as ProblemDetails (RFC 9457), the same shape ASP.NET Core returns.

Bodies name fields and reasons only: no exception text, no stack traces, no submitted values.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("leadtriage")

TITLES = {
    400: "Validation failed",
    401: "Unauthorized",
    404: "Not found",
    405: "Method not allowed",
    413: "Request body too large",
    429: "Too many requests",
    503: "Service unavailable, retry later",
}


def problem(status: int, detail: str | None = None, headers: dict | None = None, **extra) -> JSONResponse:
    body = {"type": "about:blank", "title": TITLES.get(status, "Error"), "status": status}
    if detail:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(body, status_code=status, headers=headers, media_type="application/problem+json")


def field_names(exc: RequestValidationError) -> list[str]:
    """('body', 'email') → 'email'. A body that is not JSON at all becomes 'body'."""
    names: list[str] = []
    for error in exc.errors():
        loc = [str(part) for part in error.get("loc", ()) if part != "body"]
        # Broken JSON reports a character position as its location; that is the body as a whole.
        name = loc[0] if loc and error.get("type") != "json_invalid" else "body"
        if name not in names:
            names.append(name)
    return names


def install(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def on_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return problem(400, "Check these fields.", errors=field_names(exc))

    @app.exception_handler(StarletteHTTPException)
    async def on_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) and exc.status_code < 500 else None
        if detail == TITLES.get(exc.status_code) or detail in ("Not Found", "Method Not Allowed"):
            detail = None
        return problem(exc.status_code, detail, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def on_unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error: %s", type(exc).__name__)
        return problem(500)
