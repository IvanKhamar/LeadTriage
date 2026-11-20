# LeadTriage

AI lead triage for **Verde Kitchen** (the user's Drupal portfolio site, `F:\PROJECTS\VerdeKitchen_DrupalProj`,
repo `IvanKhamar/verde-kitchen-drupal`): n8n + Python (FastAPI) + Claude API + Airtable. Portfolio piece for an
AI Automation Developer job. The brief is `docs/brief.md`; phases, decisions and their status are in `docs/plan.md`.

## Working with the user

- The user must be able to explain every node and every file in an interview. Explain each new n8n or Python concept
  in 1–2 sentences, mapped to what they know (C#/.NET, PHP/OpenCart, Drupal, FastAPI from NewErpPython).
- Steps that need the user (n8n owner account, Airtable base and token, Anthropic key, Telegram bot, screenshots):
  one step at a time: what to do, where, what they should see. Never ask them to paste a key into the chat.
- After building or importing a workflow, say what to open in the n8n UI and what to look at.

## Stack and structure

Python 3.13, uv, FastAPI, Pydantic v2 + pydantic-settings, httpx, pytest + respx, ruff. n8n self-hosted in Docker.

- `app/` FastAPI service: intake API (`docs/lead-intake-contract.md`), `/api/enrich`, `/api/validate`, demo form.
  `main.py` is the composition root (like `Program.cs`).
- `web/` demo form: plain HTML, CSS, JavaScript, served by FastAPI from the same origin.
- `n8n/workflows/` exported workflow JSON; `n8n/init/` imports workflows and credentials into a fresh n8n.
- `tools/` scripts: `export_workflows`, `send_sample_leads.py`.
- The intake contract is shared with the Verde Kitchen brief (`docs/phase-9-contact-form.md` there): a change goes
  into both repos.

## Security (the repository is public)

- Secrets (`ANTHROPIC_API_KEY`, Airtable token, `WEBHOOK_TOKEN`, `ENRICH_TOKEN`, `SOURCE_TOKEN_*`,
  `N8N_ENCRYPTION_KEY`, Telegram token) live only in the git-ignored `.env` or in n8n's encrypted credential store.
  `.env.example` lists every variable with fake values. Never print secret values in command output.
- Tokens are compared with `hmac.compare_digest`. A 500 gives no exception details; 400 names fields only.
- The lead message is untrusted input: in the prompt it sits inside delimiters and is treated as data; model output
  is used only as data (enums and lengths validated, nothing executed or sent because of it).
- Workflow export: no credential values, no `pinData`, no real e-mails. `tests/test_workflows.py` checks it.
- Only invented leads (`example.com` addresses) in tests, seeds, screenshots and the demo.
- Containers publish ports on `127.0.0.1` only; live, LeadTriage publishes no ports at all.
- Check the diff for secrets before each commit; CI runs gitleaks.

## Commands

```
docker compose up -d --build        # n8n (127.0.0.1:5678) + app (127.0.0.1:8000)
uv sync                             # create .venv and install dependencies
uv run fastapi dev app/main.py      # run the app without Docker; /health, /docs
uv run pytest                       # tests
uv run ruff check . ; uv run ruff format --check .
```

Times are ISO 8601 with a zone; display time is Kyiv (`Europe/Kyiv`).

Push only after all CI steps (`ruff check`, `ruff format --check`, `pytest`) pass locally, each exit code checked:
a failed CI run e-mails the user. Code goes through a branch and a PR; direct pushes to `main` are for docs only.
