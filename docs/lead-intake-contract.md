# Lead intake contract v1

Shared with the Verde Kitchen brief (`docs/phase-9-contact-form.md` in
[verde-kitchen-drupal](https://github.com/IvanKhamar/verde-kitchen-drupal)). Keep both copies identical.
FastAPI also publishes the OpenAPI description at `/openapi.json` (interactive docs at `/docs`).

## Entry points

Two entry points, one payload:

| Endpoint | Caller | Auth |
|---|---|---|
| `POST /api/leads` | LeadTriage's own demo form (browser, same origin) | none; rate limit + honeypot |
| `POST /api/sources/{source}/leads` | server-to-server sources, first one `verde-kitchen` | header `X-Source-Token`, one token per source, compared with `hmac.compare_digest` |

## Request body (JSON)

```json
{
  "externalId": "verde-kitchen:contact:123",
  "name": "Olena Test",
  "email": "olena@example.com",
  "phone": "+380501234567",
  "message": "Do you deliver to Lviv? We run a small cafe and want to order wholesale.",
  "consent": true,
  "locale": "uk",
  "pageUrl": "https://verde.ddev.site/uk/contact",
  "submittedAt": "2026-11-21T10:15:00+02:00"
}
```

- `externalId` (required for sources, ≤ 100 chars): the source's own id. Sending the same id again is **idempotent**:
  answer `200 {"status":"duplicate","leadId":...}` and do not process it twice. This makes source retries safe.
- `name` 2–100, `email` valid, `phone` optional, `message` 10–2000, `consent` must be `true`,
  `locale` `uk`/`en`, `pageUrl` optional, `submittedAt` ISO 8601 with zone.

## Answers

| Status | Body | Meaning for the source |
|---|---|---|
| `202` | `{"status":"received","leadId":"..."}` | accepted |
| `200` | `{"status":"duplicate","leadId":"..."}` | already accepted earlier; done |
| `400` | ProblemDetails, field names only, no internals | do not retry |
| `401` | ProblemDetails | wrong or missing token; keep it and warn the admin |
| `413` | ProblemDetails | body too large; do not retry |
| `429` | ProblemDetails | rate limit; retry later |
| `503` | ProblemDetails | n8n cannot be reached; retry later |
