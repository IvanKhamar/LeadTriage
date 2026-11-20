"""POST /api/leads (the demo form), the form page and its headers."""

import json

from tests.conftest import lead

URL = "/api/leads"


def demo_lead(**overrides):
    return lead(externalId=None, **overrides)


def test_demo_lead_is_forwarded_as_demo_form_and_gets_the_triage(client, n8n):
    triage = {"classification": {"category": "wholesale", "priority": "high"}, "needsReview": False}
    n8n.respond(200, json={"leadId": "x", "status": "processed", "triage": triage})

    response = client.post(URL, json=demo_lead())

    assert response.status_code == 202
    assert response.json()["triage"] == triage
    assert json.loads(n8n.calls.last.request.content)["source"] == "demo-form"


def test_honeypot_is_accepted_but_not_forwarded(client, n8n):
    response = client.post(URL, json=demo_lead(website="http://spam.example.com"))

    assert response.status_code == 202
    assert response.json()["status"] == "received"
    assert not n8n.called


def test_sixth_request_in_a_minute_is_429(client, n8n):
    n8n.respond(200, json={})

    answers = [client.post(URL, json=demo_lead()).status_code for _ in range(6)]

    assert answers == [202] * 5 + [429]


def test_429_says_when_to_retry(client, n8n):
    n8n.respond(200, json={})
    for _ in range(5):
        client.post(URL, json=demo_lead())

    response = client.post(URL, json=demo_lead())

    assert int(response.headers["Retry-After"]) > 0
    assert response.headers["content-type"] == "application/problem+json"


def test_form_page_has_security_headers(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_no_cors_permission_for_other_origins(client, n8n):
    response = client.options(
        URL, headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"}
    )

    assert "access-control-allow-origin" not in response.headers


def test_openapi_lists_both_entry_points(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/leads" in paths
    assert "/api/sources/{source}/leads" in paths
