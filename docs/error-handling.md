# Error handling

The rule: **no lead is ever lost.** Every failure ends in one of three ways:

1. **Handled inside the workflow:** the lead is saved anyway, with `NeedsReview` and the reason in `Issues`.
2. **Handed back to the source:** the app answers `503`, the source keeps the lead and sends it again later
   (Verde Kitchen keeps it in its queue). The idempotency store releases the `externalId` on a failed hand-over,
   so the retry is processed as new, and a retry of an already accepted lead gets `200 duplicate`.
3. **Rejected for good:** bad input (`400`), wrong token (`401`), too large (`413`). The source must not retry
   `400`/`413`; on `401` it keeps the lead and warns its admin.

When a workflow run fails, n8n starts the **error workflow** `LeadTriage errors` (an Error Trigger). It writes the
workflow name, the failed node, the error message (e-mail addresses masked, at most 500 characters), the execution
id and the time to the Airtable table `Errors`. No payload and no secrets. The execution id leads to the full run in
n8n's **Executions** list (kept 7 days).

## Retries

| Where | Tries | Wait | Why |
|---|---|---|---|
| app → n8n webhook | 2 | none | only on connection errors (the request surely did not arrive); a read timeout is not retried, because n8n may still be working on the lead |
| n8n → `/api/enrich`, `/api/validate` | 3 | 2 s | the app is next door; a short outage passes |
| n8n → Claude / Gemini | 2 | 3 s | an LLM call is slow; after that the lead goes on with `NeedsReview` |
| n8n → Airtable | 3 | 2 s | Airtable rate limits and short outages |

n8n's "Retry On Fail" waits the same time between tries; growing waits (exponential backoff) would need a loop of
nodes, which costs more clarity than it gives here. The source's own retries (minutes apart, from its queue) are the
long backoff. The app waits up to 60 s for the whole workflow, retries included.

## Failure paths

| # | What fails | What happens | Result for the lead | Checked by |
|---|---|---|---|---|
| 1 | Invalid input, missing consent, no zone in `submittedAt` | `400` ProblemDetails with the field names | rejected, the source shows the error | `tests/test_source_intake.py` |
| 2 | Missing or wrong `X-Source-Token`, unknown source | `401` | source keeps it, warns its admin | `tests/test_source_intake.py` |
| 3 | Body over 16 KiB | `413` | rejected | `tests/test_source_intake.py` |
| 4 | Demo form: more than 5 per minute per IP | `429` + `Retry-After` | the visitor waits | `tests/test_demo_intake.py` |
| 5 | n8n down or unreachable | one retry on connection error, then `503` | source retries; processed after n8n is back | tests + drill 3 |
| 6 | n8n answers an error status, or the read times out | `503`, no automatic retry | source retries | `tests/test_source_intake.py` |
| 7 | Same `externalId` sent twice | `200 duplicate`, not forwarded again | processed once | `tests/test_source_intake.py` |
| 8 | Same `externalId` while the first copy is still in flight | `503` (a "duplicate" answer could lose it if the first copy then fails) | source retries | `tests/test_source_intake.py` |
| 9 | `/api/enrich` or `/api/validate` fails | 3 tries, then the run fails → `Errors` record, `503` | source retries | drill 1 |
| 10 | LLM: wrong key, quota, outage, timeout | 2 tries, then "LLM failed" → `NeedsReview`, reason in `Issues` | saved, a person classifies it | drill 4 (no key: Claude 401, Gemini 400) |
| 11 | LLM: refusal, blocked prompt, cut-off answer | flagged in "Read … answer" → `NeedsReview` | saved for review | code review; mock-fail drill covers the path |
| 12 | LLM: invalid JSON, unknown category, too long, confidence out of range | `/api/validate` falls back to `other` + `NeedsReview`, raw text kept | saved for review | `tests/test_classification.py` |
| 13 | LLM: low confidence (< 0.5) | classification kept, `NeedsReview` | saved for review | `tests/test_classification.py` |
| 14 | Prompt injection in the message | message inside `<lead_message>` delimiters, rules say "data only", output used only as validated data | classified normally (the sample one became `spam`) | `tools/send_sample_leads.py` lead 12 |
| 15 | Airtable down, wrong token or wrong base | 3 tries, then the run fails → `503` | source retries; processed after Airtable is back | drill 2 |
| 16 | Airtable down while logging an error | the error workflow fails too | the failed run is still in n8n's Executions list | drill 2 (same base) |
| 17 | Visitor typed a bot honeypot field | `202` as usual, not forwarded, logged without personal data | dropped on purpose | `tests/test_demo_intake.py` |

## Drills (run against the local stack)

Each drill was run on 2026-11-23 with `docker compose` and invented leads; commands in brackets.

1. **Enrichment down** (`ENRICH_TOKEN=wrong docker compose up -d app`, send a lead, then `docker compose up -d app`):
   `503` after 4 s; `Errors` got `Workflow: LeadTriage main, Node: Enrich, Message: Authorization failed …`.
2. **Airtable down** (`AIRTABLE_BASE_ID=appDrillNotReal1 docker compose up -d --force-recreate n8n`): `503`;
   after restoring, the same lead → `202`, sent once more → `200 duplicate`.
3. **n8n down** (`docker compose stop n8n`): `503`; after `docker compose start n8n` the same lead → `202`.
4. **LLM unavailable** (`LLM_MODE=claude` or `gemini` without a valid key): the lead is saved with `NeedsReview`
   and the provider's error in `Issues`.
5. **LLM failure mode** (`LLM_MODE=mock-fail`): the same path without any provider.

Found by drill 1: in n8n 2.x an error workflow runs only when it is **active** (published); older versions did not
need that. `n8n/workflows/leadtriage-errors.json` is therefore `"active": true`.
