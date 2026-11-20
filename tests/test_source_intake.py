"""POST /api/sources/{source}/leads: the server-to-server entry point of contract v1."""

import json

import httpx
import pytest

from tests.conftest import SOURCE_TOKEN, WEBHOOK_TOKEN, lead

URL = "/api/sources/verde-kitchen/leads"
AUTH = {"X-Source-Token": SOURCE_TOKEN}


def test_valid_lead_is_forwarded_with_the_webhook_token(client, n8n):
    n8n.respond(200, json={"status": "ok"})

    response = client.post(URL, json=lead(), headers=AUTH)

    assert response.status_code == 202
    assert response.json()["status"] == "received"
    sent = n8n.calls.last.request
    assert sent.headers["X-Webhook-Token"] == WEBHOOK_TOKEN
    payload = json.loads(sent.content)
    assert payload["source"] == "verde-kitchen"
    assert payload["leadId"] == response.json()["leadId"]
    assert payload["externalId"] == "verde-kitchen:contact:123"
    assert payload["receivedAt"].endswith(("+02:00", "+03:00"))  # Kyiv time with its zone
    assert "triage" not in response.json()  # only the demo form gets the classification back


@pytest.mark.parametrize("headers", [{}, {"X-Source-Token": "wrong-token"}])
def test_missing_or_wrong_token_is_401(client, n8n, headers):
    response = client.post(URL, json=lead(), headers=headers)

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert not n8n.called


def test_unknown_source_is_401_like_a_wrong_token(client, n8n):
    response = client.post("/api/sources/someone-else/leads", json=lead(), headers=AUTH)

    assert response.status_code == 401


def test_token_is_checked_before_the_body(client, n8n):
    response = client.post(URL, json={"nonsense": True})

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"externalId": "x" * 101}, "externalId"),
        ({"name": "A"}, "name"),
        ({"email": "not-an-email"}, "email"),
        ({"message": "short"}, "message"),
        ({"message": "x" * 2001}, "message"),
        ({"consent": False}, "consent"),
        ({"locale": "de"}, "locale"),
        ({"phone": "call me maybe"}, "phone"),
        ({"submittedAt": "2026-11-21T10:15:00"}, "submittedAt"),  # no zone
        ({"pageUrl": "javascript:alert(1)"}, "pageUrl"),
    ],
)
def test_invalid_field_is_400_naming_only_the_field(client, n8n, override, field):
    response = client.post(URL, json=lead(**override), headers=AUTH)

    assert response.status_code == 400
    assert response.json()["errors"] == [field]
    assert "olena@example.com" not in response.text  # no submitted values echoed back
    assert not n8n.called


def test_source_must_send_an_external_id(client, n8n):
    body = lead()
    del body["externalId"]

    response = client.post(URL, json=body, headers=AUTH)

    assert response.status_code == 400
    assert response.json()["errors"] == ["externalId"]


def test_body_that_is_not_json_is_400(client, n8n):
    response = client.post(URL, content=b"{not json", headers={**AUTH, "Content-Type": "application/json"})

    assert response.status_code == 400
    assert response.json()["errors"] == ["body"]


def test_too_large_body_is_413(client, n8n):
    response = client.post(URL, content=b"x" * (17 * 1024), headers={**AUTH, "Content-Type": "application/json"})

    assert response.status_code == 413
    assert not n8n.called


def test_too_large_chunked_body_is_413(client, n8n):
    def chunks():
        for _ in range(20):
            yield b"x" * 1024

    response = client.post(URL, content=chunks(), headers={**AUTH, "Content-Type": "application/json"})

    assert response.status_code == 413


def test_same_external_id_twice_is_a_duplicate_and_forwarded_once(client, n8n):
    n8n.respond(200, json={})

    first = client.post(URL, json=lead(), headers=AUTH)
    second = client.post(URL, json=lead(), headers=AUTH)

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json() == {"status": "duplicate", "leadId": first.json()["leadId"]}
    assert n8n.call_count == 1


def test_n8n_down_is_503_and_the_retry_later_is_processed(client, n8n):
    n8n.side_effect = httpx.ConnectError("refused")

    down = client.post(URL, json=lead(), headers=AUTH)

    assert down.status_code == 503
    assert down.headers["Retry-After"]
    assert n8n.call_count == 2  # first try + one retry

    n8n.side_effect = None
    n8n.return_value = httpx.Response(200, json={})
    retried = client.post(URL, json=lead(), headers=AUTH)
    assert retried.status_code == 202  # the id was released, so nothing is lost


def test_one_connection_error_is_retried(client, n8n):
    n8n.side_effect = [httpx.ConnectError("refused"), httpx.Response(200, json={})]

    response = client.post(URL, json=lead(), headers=AUTH)

    assert response.status_code == 202
    assert n8n.call_count == 2


def test_read_timeout_is_not_retried(client, n8n):
    n8n.side_effect = httpx.ReadTimeout("slow")

    response = client.post(URL, json=lead(), headers=AUTH)

    assert response.status_code == 503
    assert n8n.call_count == 1  # n8n may still be working on it; a second copy would be processed twice


def test_n8n_error_status_is_503_without_its_details(client, n8n):
    n8n.respond(500, json={"message": "workflow failed"})

    response = client.post(URL, json=lead(), headers=AUTH)

    assert response.status_code == 503
    assert "workflow failed" not in response.text
