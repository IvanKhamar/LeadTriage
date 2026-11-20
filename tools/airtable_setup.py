"""Creates the `Leads` and `Errors` tables in the Airtable base from .env (AIRTABLE_TOKEN, AIRTABLE_BASE_ID).

    uv run python tools/airtable_setup.py

The schema lives here as code (docs/airtable-schema.md describes it for people). Safe to run again: existing tables
and fields are kept, only missing ones are added. Needs the `schema.bases:write` scope once; remove it from the token
afterwards, because the workflow needs only data.records:read/write and schema.bases:read.
Views (Urgent, Needs review, Wholesale) cannot be created through the API: make them in the UI.
"""

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.airtable.com/v0/meta/bases"

# Airtable's list still uses the old IANA name of the Kyiv zone (same zone, renamed to Europe/Kyiv in 2022).
KYIV_DATETIME = {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "Europe/Kiev"}
CHECKBOX = {"icon": "check", "color": "greenBright"}


def text(name: str) -> dict:
    return {"name": name, "type": "singleLineText"}


def long_text(name: str) -> dict:
    return {"name": name, "type": "multilineText"}


def number(name: str, precision: int = 0) -> dict:
    return {"name": name, "type": "number", "options": {"precision": precision}}


def checkbox(name: str) -> dict:
    return {"name": name, "type": "checkbox", "options": CHECKBOX}


def select(name: str, *choices: str) -> dict:
    return {"name": name, "type": "singleSelect", "options": {"choices": [{"name": c} for c in choices]}}


def date_time(name: str) -> dict:
    return {"name": name, "type": "dateTime", "options": KYIV_DATETIME}


CATEGORIES = (
    "product_question", "where_to_buy", "wholesale", "order_issue", "complaint", "partnership", "spam", "other",
)  # fmt: skip

# The first field of each table is its primary field.
TABLES = {
    "Leads": [
        text("Name"),
        {"name": "Email", "type": "email"},
        {"name": "Phone", "type": "phoneNumber"},
        select("Source", "verde-kitchen", "demo-form"),
        text("ExternalId"),
        text("LeadId"),
        long_text("Message"),
        long_text("History"),
        select("Category", *CATEGORIES),
        select("Priority", "high", "medium", "low"),
        select("Language", "uk", "en", "other"),
        long_text("Summary"),
        long_text("ReplyDraft"),
        number("Confidence", 2),
        checkbox("NeedsReview"),
        long_text("Issues"),
        long_text("RawText"),
        text("EmailDomain"),
        checkbox("FreeMail"),
        checkbox("Disposable"),
        text("PhoneCountry"),
        text("Model"),
        number("InputTokens"),
        number("OutputTokens"),
        number("CostUsd", 6),
        number("LatencyMs"),
        date_time("ReceivedAt"),
        select("Status", "new", "in progress", "done"),
    ],
    "Errors": [
        text("Workflow"),
        text("Node"),
        long_text("Message"),
        text("ExecutionId"),
        date_time("OccurredAt"),
    ],
}


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def fail(response: httpx.Response, what: str) -> None:
    # Airtable's error type and message only; the request (with the token) is never printed.
    try:
        error = response.json().get("error", {})
    except ValueError:
        error = {}
    detail = error.get("message") or error.get("type") or response.reason_phrase
    sys.exit(f"{what}: HTTP {response.status_code} {detail}")


def main() -> None:
    env = read_env(ROOT / ".env")
    token, base = env.get("AIRTABLE_TOKEN", ""), env.get("AIRTABLE_BASE_ID", "")
    if not token or not base:
        sys.exit("Set AIRTABLE_TOKEN and AIRTABLE_BASE_ID in .env first (tools/set-secret.ps1).")

    with httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=30) as client:
        response = client.get(f"{API}/{base}/tables")
        if not response.is_success:
            fail(response, "Reading the base")
        existing = {table["name"]: table for table in response.json()["tables"]}

        for name, fields in TABLES.items():
            table = existing.get(name)
            if table is None:
                response = client.post(f"{API}/{base}/tables", json={"name": name, "fields": fields})
                if not response.is_success:
                    fail(response, f"Creating table {name}")
                print(f"created table {name} with {len(fields)} fields")
                continue

            have = {field["name"] for field in table["fields"]}
            missing = [field for field in fields if field["name"] not in have]
            for field in missing:
                response = client.post(f"{API}/{base}/tables/{table['id']}/fields", json=field)
                if not response.is_success:
                    fail(response, f"Adding {name}.{field['name']}")
            print(f"table {name}: {len(missing)} missing fields added" if missing else f"table {name}: up to date")


if __name__ == "__main__":
    main()
