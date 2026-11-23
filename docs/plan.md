# LeadTriage — work plan

Source: [brief.md](brief.md) (copy of `F:\PROJECTS\LeadTriage\LeadTriage_TZ.md`, written 2026-11-20).
Each phase ends with green CI and a PR merged into `main` (rules: `F:\PROJECTS\CLAUDE.md`).

Note: the Verde Kitchen repo is at `F:\PROJECTS\VerdeKitchen_DrupalProj` (the brief says `DrupalProj`). Its
`docs/phase-9-contact-form.md` uses the same intake contract v1 (checked 2026-11-20).

## Phases

| # | Phase | What is delivered | Needs the user | Status |
|---|---|---|---|---|
| 0 | Bootstrap | Both `CLAUDE.md` files, `.gitignore`, `.env.example`, README skeleton, `pyproject.toml` (uv, Python 3.13, ruff, pytest), CI (ruff + pytest + gitleaks), Dependabot, public repo `LeadTriage` | — | done |
| 1 | Stack runs | `Dockerfile` for the app, `docker-compose.yml` (n8n pinned version + app), ports on `127.0.0.1`, `/health`, named volumes | — (the owner account moved to phase 3: the UI is only needed to look at the workflow) | done |
| 2 | Intake API | Both contract endpoints, Pydantic models, ProblemDetails, body limit, rate limit, honeypot, idempotency store, forwarding with retry / 503, `/api/enrich`, demo form (`web/`), security headers, tests | — | done |
| 3 | n8n v1, mock mode | Main workflow: webhook (header auth) → normalise → enrich → mock classify → validate → respond; init step that imports workflows and credentials; `tools/export_workflows`; workflow-export test. **Contract goes live: the Verde Kitchen phase 9 can start.** | create the n8n owner account, open the workflow in the UI and walk through the nodes | done |
| 4 | Airtable | `docs/airtable-schema.md`, `tools/airtable_setup.py` (schema as code), Airtable nodes: search by email (30 days) → create or update with history | create the base, tables, views and a scoped token | done (views made by hand) |
| 5 | Real LLM | Shared prompt with delimiters, Claude (Messages API) and Gemini (free tier) branches, `/api/validate` with per-provider cost, fallback to `needsReview`, tokens / cost / latency logged, `tools/send_sample_leads.py` | an LLM key in `.env` (`tools/set-secret.ps1`) | done: Gemini tested (11/12 right, injection resisted); Claude built, waits for a key |
| 6 | Errors | Retry On Fail on HTTP / Claude / Airtable nodes, Error Trigger workflow → `Errors` table, `docs/error-handling.md`, a test for each failure path | — | done (drills in `docs/error-handling.md`) |
| 7 | Notifications | "Urgent" view; optional Telegram behind `NOTIFY_TELEGRAM=true` | optional: create a Telegram bot | done in code (`docs/notifications.md`); views made by the user |
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
3. **Mock mode** reads `LLM_MODE` (`mock` → fixed valid classification; `mock-fail` → simulated failure, for the
   error-path tests; `live` → Claude, from phase 5 through an IF node in front of the mock). Phase 3 built it as one
   Code node "LLM (mock)" followed by a no-op "LLM result" node, where the Claude branch joins later.
   n8n needs env access in nodes for this (`N8N_BLOCK_ENV_ACCESS_IN_NODE=false`), so n8n gets only non-secret
   settings as env vars: its encryption key arrives as a compose secret file, API keys live in credentials.
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
10. **Airtable schema as code** (decided in phase 4): `tools/airtable_setup.py` creates both tables through the
    Airtable API instead of 33 fields by hand. It needs `schema.bases:write` once; the scope is removed afterwards.
    Views stay manual, because the API cannot create them.
11. **Secrets into `.env` without an editor:** `tools/set-secret.ps1` reads a value with hidden input and writes it
    into `.env`, so it never shows on screen, in the shell history or in the chat.

12. **Two LLM providers** (decided in phase 5): `LLM_MODE=claude|gemini|mock|mock-fail`. The user preferred a free
    model, so Gemini (`gemini-3.5-flash-lite`, free tier) runs the demo and Claude (`claude-haiku-5-5`) is ready for a
    key. One shared "Build prompt" node gives both the same rules and JSON schema, so they can be compared fairly.
    The Gemini free tier lets Google use the content to improve its products: invented leads only, never real
    visitors (live needs Claude or a paid Gemini tier).
13. **Structured output on both providers:** the API enforces valid JSON and the enums; `/api/validate` still checks
    lengths and confidence, because neither schema limits them.

## Questions for the user

None open. Phase 5 needs an Anthropic API key with a little credit (set with `tools/set-secret.ps1`).
