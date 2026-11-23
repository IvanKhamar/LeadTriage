# Decisions

Design decisions made while building LeadTriage are listed in [plan.md](plan.md) ("Decisions"). This file holds the
ones about running together with Verde Kitchen.

## How the Drupal site (DDEV) reaches LeadTriage locally

**Decision (2026-11-23): `VERDE_LEADS_URL=http://host.docker.internal:8000`** in Verde Kitchen's git-ignored
`.ddev/.env`, together with `VERDE_LEADS_TOKEN` (the same value as `SOURCE_TOKEN_VERDE_KITCHEN` in LeadTriage's
`.env`).

Why: it is the simplest setup that works. LeadTriage publishes the app on `127.0.0.1:8000` of the host. On Docker
Desktop (Windows, macOS), `host.docker.internal` inside any container means "the host", and Docker Desktop forwards
it to ports published on the host's loopback. So the DDEV web container reaches the app without extra compose files
in either project, and nothing is exposed beyond `127.0.0.1`.

The alternative from the plan, a shared external Docker network (`verde-leads`) that both compose projects join,
was not needed locally. It stays the plan for the live server (phase 10): on Linux, `host.docker.internal` needs an
`extra_hosts: host-gateway` entry and does **not** reach ports bound to `127.0.0.1`, and the live setup publishes no
ports at all. There, Drupal will call `http://app:8000` over the shared network.

Checked from inside the DDEV web container: `curl http://host.docker.internal:8000/health` → `{"status":"ok"}`.

## End to end with the real contact form (phase 8)

Run on 2026-11-23 with DDEV, LeadTriage in Docker, `LLM_MODE=gemini`, `AIRTABLE_MODE=on`, invented data only.

| Step | Result |
|---|---|
| Message sent from `/uk/contact` (a cafe in Dnipro asking for wholesale terms) | Drupal saved it as message 14, status `pending`, one queue item |
| `drush queue:run verde_leads_forward` | sent in about 5 s; Drupal status `sent` |
| Airtable `Leads` | `ExternalId verde-kitchen:contact:14`, source `verde-kitchen`, `wholesale`, `high`, `uk`, a Ukrainian draft reply; it shows in the Urgent and Wholesale views |
| LeadTriage app stopped, message sent from `/contact` (a torn bag in an order) | saved as message 15, `pending`; the queue run fails and Drupal schedules the next attempt (about a minute later, growing towards a day) |
| App started again, next queue run after the due time | sent; Airtable: `order_issue`, `high`, `en` |

Notes for the Verde Kitchen side (not changed here):
- `https://verde-kitchen.ddev.site` answered 502 from the DDEV router during the test; `http://` worked. Most likely
  the local certificate (`mkcert -install`); it does not affect the server-to-server call.
- Its README says messages are sorted "with Claude"; the local demo now uses Gemini's free tier
  (`LLM_MODE=gemini`), with Claude ready for a key.
- In this shell, `ddev drush` failed ("Git Bash is not installed in standard locations"); `ddev exec drush ...` works.
