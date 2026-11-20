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

## Documents

- [Lead intake contract](docs/lead-intake-contract.md)
- [Plan](docs/plan.md) · [Brief](docs/brief.md)
