"""Rules for the exported n8n workflows in a public repository: no secrets, no test data, webhooks authenticated."""

import json
import re
from pathlib import Path

import pytest

from tools.export_workflows import clean

WORKFLOW_DIR = Path(__file__).resolve().parent.parent / "n8n" / "workflows"
FILES = sorted(WORKFLOW_DIR.glob("*.json"))

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
ALLOWED_EMAIL_DOMAINS = ("example.com", "example.org", "example.net")
SECRET_PATTERNS = {
    "Anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
    "Airtable token": re.compile(r"pat[A-Za-z0-9]{14}\.[a-f0-9]{20,}"),
    "Telegram bot token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),
    "bearer token": re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"),
    "placeholder token from .env.example": re.compile(r"change-me-[a-z-]+"),
}
TOKEN_HEADER = re.compile(r"authorization|api[-_]?key|token", re.IGNORECASE)


def nodes(workflow: dict, node_type: str) -> list[dict]:
    return [node for node in workflow["nodes"] if node["type"] == node_type]


def test_there_are_workflows():
    assert FILES, "n8n/workflows/ is empty"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
class TestExportedWorkflow:
    def test_is_clean(self, path):
        workflow = json.loads(path.read_text(encoding="utf-8"))

        assert workflow["id"] and workflow["name"] and workflow["nodes"]
        assert not workflow.get("pinData"), "pinned test data must not be committed"
        for key in ("staticData", "meta", "shared"):
            assert key not in workflow, f"{key} must be stripped (tools/export_workflows.py)"

    def test_credentials_are_references_only(self, path):
        workflow = json.loads(path.read_text(encoding="utf-8"))

        for node in workflow["nodes"]:
            for ref in (node.get("credentials") or {}).values():
                assert set(ref) <= {"id", "name"}, f"{node['name']}: credential holds more than a reference"

    def test_no_secrets_or_real_emails(self, path):
        text = path.read_text(encoding="utf-8")

        for label, pattern in SECRET_PATTERNS.items():
            assert not pattern.search(text), f"looks like a {label}"
        for match in EMAIL.finditer(text):
            assert match.group(0).lower().endswith(ALLOWED_EMAIL_DOMAINS), "real-looking e-mail address"

    def test_webhooks_use_header_auth(self, path):
        workflow = json.loads(path.read_text(encoding="utf-8"))

        for node in nodes(workflow, "n8n-nodes-base.webhook"):
            assert node["parameters"].get("authentication") == "headerAuth", node["name"]
            assert "httpHeaderAuth" in node.get("credentials", {}), node["name"]

    def test_http_requests_take_tokens_from_credentials(self, path):
        workflow = json.loads(path.read_text(encoding="utf-8"))

        for node in nodes(workflow, "n8n-nodes-base.httpRequest"):
            headers = node["parameters"].get("headerParameters", {}).get("parameters", [])
            for header in headers:
                assert not TOKEN_HEADER.search(header.get("name", "")), f"{node['name']}: token header in plain text"


def test_clean_drops_everything_that_should_not_be_public():
    exported = {
        "id": "abc",
        "name": "Flow",
        "active": True,
        "nodes": [{"name": "n"}],
        "connections": {},
        "settings": {},
        "pinData": {"n": [{"json": {"email": "someone@real-domain.test"}}]},
        "staticData": {"x": 1},
        "meta": {"instanceId": "f00"},
        "shared": [{"project": {"name": "Owner Name <owner@real-domain.test>"}}],
        "updatedAt": "2026-11-20T00:00:00Z",
        "versionId": "v1",
        "tags": [{"id": "t1", "name": "leadtriage", "createdAt": "x"}],
    }

    assert clean(exported) == {
        "id": "abc",
        "name": "Flow",
        "active": True,
        "nodes": [{"name": "n"}],
        "connections": {},
        "settings": {},
        "tags": [{"name": "leadtriage"}],
    }
