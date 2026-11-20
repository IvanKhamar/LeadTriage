# Build:  docker build -t leadtriage-app .
# Run:    docker compose up -d --build   (the app service)
# Two stages: uv builds the virtual environment, only the environment and the code go into the smaller runtime image.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build
# Compile .py to bytecode at build time (faster start); copy files instead of linking from uv's cache;
# use the image's Python instead of downloading one.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.13-slim-bookworm
RUN useradd --system --create-home leadtriage \
    && mkdir -p /app/data && chown leadtriage /app/data
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY app ./app
COPY web ./web
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER leadtriage
EXPOSE 8000
# The slim image has no curl, so the health check asks /health with Python itself.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
# --proxy-headers off: the app is reached directly; the client IP for the rate limit is the socket address.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
