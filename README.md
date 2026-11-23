# LeadTriage

AI lead triage for the contact form of [Verde Kitchen](https://github.com/IvanKhamar/verde-kitchen-drupal), an
invented healthy food and drinks brand: **n8n + Python (FastAPI) + Claude API + Airtable**.

Every message from the site is validated, enriched, classified by Claude (category, priority, language, summary,
draft reply), deduplicated and written to Airtable, so a manager gets a sorted, prioritised list instead of an inbox.

> Work in progress. The plan is in [docs/plan.md](docs/plan.md).

## How it works

1. A visitor fills in the contact form on the Verde Kitchen site (Drupal).
2. Drupal saves the message and sends it, server to server, to the LeadTriage API.
3. The FastAPI service validates it and forwards it to an n8n webhook.
4. n8n normalises the data, asks the Python service for deterministic enrichment, asks Claude to classify the lead,
   checks for duplicates and writes the result to Airtable.
5. High-priority leads trigger a notification. Failures are retried, then logged for a human.

LeadTriage also works without Drupal: it has its own demo form and a mock LLM mode, so it runs with Docker only.

## Run it (mock mode: no keys, no Drupal)

Needs Docker. From the repository folder:

```
cp .env.example .env                 # fake tokens are fine for a local demo
docker compose run --rm n8n-init     # imports the credentials (from .env) and the workflows into n8n
docker compose up -d --build         # n8n on 127.0.0.1:5678, the app on 127.0.0.1:8000
```

Open <http://127.0.0.1:8000>, send a message, and the page shows how the workflow classified it.
API docs: <http://127.0.0.1:8000/docs>. n8n UI: <http://127.0.0.1:5678> (create the owner account on first visit).
`LLM_MODE` in `.env` picks who classifies: `mock` (default, no key), `gemini` (free key from Google AI Studio), `claude`
(Anthropic key), or `mock-fail` (shows what happens when the LLM does not answer); then `docker compose up -d n8n`.
Keys go into `.env` with `powershell -ExecutionPolicy Bypass -File tools\set-secret.ps1 GEMINI_API_KEY` (hidden input),
then `docker compose run --rm n8n-init`. `uv run python tools/send_sample_leads.py` sends 12 invented leads.

Workflows live in `n8n/workflows/` and are the source of truth: after editing one in the n8n UI, run
`uv run python tools/export_workflows.py` (it strips pinned data and owner info) and commit the JSON.

## Documents

- [Lead intake contract](docs/lead-intake-contract.md)
- [Plan](docs/plan.md) · [Brief](docs/brief.md)
