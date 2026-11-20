"""Composition root of the LeadTriage service (like Program.cs in .NET)."""

from fastapi import FastAPI

app = FastAPI(title="LeadTriage", version="0.1.0")


@app.get("/health", tags=["service"])
def health() -> dict[str, str]:
    """Liveness probe for Docker and humans."""
    return {"status": "ok"}
