# LeadTriage — work plan

Source: [brief.md](brief.md) (copy of `F:\PROJECTS\LeadTriage\LeadTriage_TZ.md`, written 2026-11-20).
Each phase ends with green CI and a PR merged into `main` (rules: `F:\PROJECTS\CLAUDE.md`).

Note: the Verde Kitchen repo is at `F:\PROJECTS\VerdeKitchen_DrupalProj` (the brief says `DrupalProj`). Its
`docs/phase-9-contact-form.md` uses the same intake contract v1 (checked 2026-11-20).

## Phases

| # | Phase | What is delivered | Needs the user | Status |
|---|---|---|---|---|
| 0 | Bootstrap | Both `CLAUDE.md` files, `.gitignore`, `.env.example`, README skeleton, `pyproject.toml` (uv, Python 3.13, ruff, pytest), CI (ruff + pytest + gitleaks), Dependabot, public repo `LeadTriage` | — | todo |
| 1 | Stack runs | `Dockerfile` for the app, `docker-compose.yml` (n8n pinned version + app), ports on `127.0.0.1`, `/health`, named volumes | create the n8n owner account in the UI (step by step) | todo |
| 2 | Intake API | Both contract endpoints, Pydantic models, ProblemDetails, body limit, rate limit, honeypot, idempotency store, forwarding with retry / 503, `/api/enrich`, demo form (`web/`), security headers, tests | — | todo |
| 3 | n8n v1, mock mode | Main workflow: webhook (header auth) → normalise → enrich → mock classify → validate → respond; init step that imports workflows and credentials; `tools/export_workflows`; workflow-export test. **Contract goes live: the Verde Kitchen phase 9 can start.** | open the workflow in the UI and walk through the nodes | todo |
| 4 | Airtable | `docs/airtable-schema.md`, Airtable nodes: search by email (30 days) → create or update with history | create the base, tables, views and a scoped token | todo |
| 5 | Real Claude | Prompt with delimiters, Messages API call, `/api/validate`, fallback to `needsReview`, tokens / cost / latency logged | put `ANTHROPIC_API_KEY` in `.env` (never in the chat) | todo |
| 6 | Errors | Retry On Fail on HTTP / Claude / Airtable nodes, Error Trigger workflow → `Errors` table, `docs/error-handling.md`, a test for each failure path | — | todo |
| 7 | Notifications | "Urgent" view; optional Telegram behind `NOTIFY_TELEGRAM=true` | optional: create a Telegram bot | todo |
| 8 | End to end with Drupal | Connect DDEV to the API, real form submissions, `docs/decisions.md` entry, screenshots | run DDEV, set the token in `.ddev/.env`, take screenshots | waits for Verde Kitchen phase 9 |
| 9 | Polish | README (story, Mermaid diagram, run in 5 commands, design decisions, "in production I would add"), `tools/send_sample_leads.py`, tag `v1.0` | screenshots | todo |
| 10 | Live on Oracle | Separate compose project on the Verde Kitchen VM, arm64 image, shared network, no public ports, daily LLM budget, retention, Airtable limit check, `docs/deployment.md` | server steps one by one, in Ukrainian | waits for Verde Kitchen phase 8.6 |

## Decisions the brief leaves open (proposed)

1. **Calling Claude: n8n HTTP Request node to the Messages API, not the Anthropic node.** The HTTP node shows the raw
   request and response, so `usage.input_tokens` / `output_tokens` are available for cost logging, the model and
   `max_tokens` come from env, and the same call is easy to explain and to reproduce with `curl`.
2. **LLM-output validation lives in Python: n8n calls `POST /api/validate`** (protected by `ENRICH_TOKEN`). One
   implementation, tested with pytest, no copy in a Code node that could drift. It also computes `costUsd` from the
   token counts and the price from config.
3. **Mock mode** is an IF node on `LLM_MODE` (`mock` → fixed valid classification; `mock-fail` → simulated failure,
   for the error-path tests; `live` → Claude). n8n needs env access in nodes for this (`N8N_BLOCK_ENV_ACCESS_IN_NODE=false`);
   only non-secret settings are read that way, the API key stays in a credential.
4. **Demo without any key:** `AIRTABLE_MODE=off` skips the Airtable nodes, and the webhook answer (category,
   priority, summary, draft) is shown on the demo form. So `docker compose up` + a few commands works with no
   Anthropic and no Airtable account.
5. **Idempotency store: SQLite** (stdlib `sqlite3`, file in a git-ignored Docker volume), unique key
   `(source, externalId)`. One app instance needs no Redis or database server; the README says what would change with
   several instances (Postgres or Redis).
6. **Rate limit:** a small in-memory sliding window per IP (no extra dependency, easy to test). Behind a proxy only
   a trusted `X-Forwarded-For` is used.
7. **Credentials in n8n for a fresh clone:** an init container generates credential JSON from `.env` inside the
   container and runs `n8n import:credentials` / `import:workflow`; nothing with values is written to the repo. The
   exact CLI commands (import, activate/publish) are checked on the pinned n8n version in phase 3.
8. **Drupal ↔ API locally:** try a shared external Docker network `verde-leads` first (DDEV joins it through
   `.ddev/docker-compose.leads.yaml`), because the live server uses the same idea; fall back to
   `host.docker.internal`. Checked with a real request in phase 8, written to `docs/decisions.md`.
9. **Sample data:** Faker plus hand-written texts, only `example.com` addresses.

## Questions for the user

None that block phase 0. Phase 4 needs a free Airtable account and phase 5 an Anthropic API key with a little credit;
both are only needed then.
