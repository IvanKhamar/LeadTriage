"""Token checks, body size limit and security headers."""

import hmac

from fastapi import HTTPException
from pydantic import SecretStr
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.problems import problem


def token_matches(given: str | None, expected: SecretStr) -> bool:
    """Constant-time comparison (hmac.compare_digest), so response time does not leak how much of a token matched.
    An empty expected token matches nothing: a missing setting closes the endpoint instead of opening it."""
    secret = expected.get_secret_value()
    if not secret or not given:
        return False
    return hmac.compare_digest(given.encode(), secret.encode())


class BodyTooLarge(HTTPException):
    """An HTTPException on purpose: FastAPI turns other errors raised while reading the body into a 400."""

    def __init__(self) -> None:
        super().__init__(status_code=413)


class BodySizeLimit:
    """ASGI middleware: rejects bodies over `max_bytes`, checked on Content-Length and again while reading
    (a chunked request has no Content-Length)."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        length = dict(scope["headers"]).get(b"content-length")
        if length is not None and length.isdigit() and int(length) > self.max_bytes:
            await problem(413)(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise BodyTooLarge()
            return message

        await self.app(scope, limited_receive, send)


# The demo page loads its script and stylesheet from the same origin only; no inline code, no outside addresses.
SECURITY_HEADERS = {
    b"content-security-policy": (
        b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
        b"form-action 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
    ),
    b"x-content-type-options": b"nosniff",
    b"referrer-policy": b"no-referrer",
    b"x-frame-options": b"DENY",
    b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
}


class SecurityHeaders:
    """ASGI middleware that adds SECURITY_HEADERS to every response that does not set them itself."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {name.lower() for name, _ in message.get("headers", [])}
                extra = [(name, value) for name, value in SECURITY_HEADERS.items() if name not in present]
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        await self.app(scope, receive, send_with_headers)
