"""Validation of the LLM output: the model's text is untrusted data."""

import json

import pytest

from app.classification import cost_usd, validate
from tests.conftest import ENRICH_TOKEN

GOOD = {
    "category": "wholesale",
    "priority": "high",
    "language": "uk",
    "summary": "A cafe in Lviv asks about wholesale delivery.",
    "replyDraft": "Добрий день! Дякуємо за інтерес до Verde Kitchen.",
    "confidence": 0.92,
}


def run(raw: str):
    return validate(raw, 1000, 200, price_in=1.0, price_out=5.0)


def test_valid_output_passes():
    result = run(json.dumps(GOOD))

    assert result.classification.category == "wholesale"
    assert not result.needs_review
    assert result.issues == []
    assert result.raw_text is None


def test_json_inside_a_code_fence_is_accepted():
    result = run("```json\n" + json.dumps(GOOD) + "\n```")

    assert not result.needs_review


@pytest.mark.parametrize(
    ("raw", "issue"),
    [
        ("Sure! Here is the classification: wholesale", "not valid JSON"),
        ("[1, 2, 3]", "not a JSON object"),
        (json.dumps({**GOOD, "category": "rm -rf"}), "category: literal_error"),
        (json.dumps({**GOOD, "priority": "urgent!!!"}), "priority: literal_error"),
        (json.dumps({**GOOD, "summary": "x" * 201}), "summary: string_too_long"),
        (json.dumps({**GOOD, "replyDraft": "x" * 601}), "replyDraft: string_too_long"),
        (json.dumps({**GOOD, "confidence": 3}), "confidence: less_than_equal"),
        (json.dumps({k: v for k, v in GOOD.items() if k != "language"}), "language: missing"),
    ],
)
def test_invalid_output_falls_back_to_other_with_review(raw, issue):
    result = run(raw)

    assert result.classification.category == "other"
    assert result.needs_review
    assert issue in result.issues
    assert result.raw_text == raw  # kept for debugging


def test_low_confidence_needs_review_but_keeps_the_classification():
    result = run(json.dumps({**GOOD, "confidence": 0.3}))

    assert result.classification.category == "wholesale"
    assert result.needs_review
    assert result.issues == ["low confidence"]


def test_cost_uses_the_configured_prices():
    assert cost_usd(1_000_000, 0, 1.0, 5.0) == 1.0
    assert cost_usd(1000, 200, 1.0, 5.0) == 0.002
    assert run(json.dumps(GOOD)).cost_usd == 0.002


def test_validate_endpoint(client):
    body = {"rawText": json.dumps(GOOD), "inputTokens": 1000, "outputTokens": 200}

    assert client.post("/api/validate", json=body).status_code == 401
    response = client.post("/api/validate", json=body, headers={"X-Enrich-Token": ENRICH_TOKEN})

    assert response.status_code == 200
    assert response.json()["classification"]["replyDraft"].startswith("Добрий")
    assert response.json()["needsReview"] is False
    assert response.json()["costUsd"] == 0.002


@pytest.mark.parametrize(("provider", "cost"), [("claude", 0.002), ("gemini", 0.0), ("mock", 0.0)])
def test_cost_depends_on_who_answered(client, provider, cost):
    body = {"provider": provider, "rawText": json.dumps(GOOD), "inputTokens": 1000, "outputTokens": 200}

    response = client.post("/api/validate", json=body, headers={"X-Enrich-Token": ENRICH_TOKEN})

    assert response.json()["costUsd"] == cost  # test settings: Claude 1/5 USD, Gemini free tier 0
