"""Composition root of the LeadTriage service (like Program.cs in .NET): settings, services, middleware, routes."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import problems, routes
from app.config import Settings
from app.forwarder import N8nForwarder
from app.ratelimit import RateLimiter
from app.security import BodySizeLimit, SecurityHeaders
from app.store import IdempotencyStore

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # One HTTP client for the app's lifetime (connection pooling), like a typed HttpClient from IHttpClientFactory.
        timeout = httpx.Timeout(settings.forward_read_timeout_s, connect=settings.forward_connect_timeout_s)
        async with httpx.AsyncClient(timeout=timeout) as client:
            app.state.forwarder = N8nForwarder(client, settings.n8n_webhook_url, settings.webhook_token)
            app.state.store = IdempotencyStore(settings.data_dir / "intake.sqlite")
            try:
                yield
            finally:
                app.state.store.close()

    app = FastAPI(
        title="LeadTriage",
        version="0.1.0",
        description="Lead intake contract v1 for Verde Kitchen and the demo form. See docs/lead-intake-contract.md.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.limiter = RateLimiter(settings.rate_limit_per_minute)

    # No CORS middleware on purpose: the demo form is served from this origin, and Drupal calls from its server,
    # so browsers on other origins get no permission to call the API.
    app.add_middleware(BodySizeLimit, max_bytes=settings.max_body_bytes)
    app.add_middleware(SecurityHeaders)
    problems.install(app)
    app.include_router(routes.router)

    @app.get("/health", tags=["service"])
    def health() -> dict[str, str]:
        """Liveness probe for Docker and humans."""
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def demo_form() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app


app = create_app()
