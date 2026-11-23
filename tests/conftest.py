"""Shared fixtures. Every token here is an obviously fake test value."""

import pytest
import respx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app

N8N_URL = "http://n8n.test/webhook/leads"
SOURCE_TOKEN = "test-source-token"
ENRICH_TOKEN = "test-enrich-token"
WEBHOOK_TOKEN = "test-webhook-token"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,  # never read the developer's real .env in tests
        webhook_token=SecretStr(WEBHOOK_TOKEN),
        enrich_token=SecretStr(ENRICH_TOKEN),
        source_token_verde_kitchen=SecretStr(SOURCE_TOKEN),
        n8n_webhook_url=N8N_URL,
        data_dir=tmp_path,
        rate_limit_per_minute=5,
        # Round test prices, independent of the real defaults in config.py.
        llm_price_input_per_mtok=1.0,
        llm_price_output_per_mtok=5.0,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def n8n():
    """respx intercepts httpx calls (like a mocked HttpMessageHandler in .NET); the test decides what n8n answers."""
    with respx.mock(assert_all_called=False) as router:
        yield router.post(N8N_URL)


def lead(**overrides) -> dict:
    body = {
        "externalId": "verde-kitchen:contact:123",
        "name": "Olena Test",
        "email": "olena@example.com",
        "phone": "+380501234567",
        "message": "Do you deliver to Lviv? We run a small cafe and want to order wholesale.",
        "consent": True,
        "locale": "uk",
        "pageUrl": "https://verde.ddev.site/uk/contact",
        "submittedAt": "2026-11-21T10:15:00+02:00",
    }
    body.update(overrides)
    return {k: v for k, v in body.items() if v is not None}
