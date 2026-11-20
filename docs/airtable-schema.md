# Airtable base "LeadTriage"

The n8n workflow writes every lead here (free plan is enough). Field names must match exactly, because the workflow
maps to them by name. The workflow writes with `typecast`, so a missing single-select option is added by Airtable.

## Setting it up

1. In Airtable, create an empty base named `LeadTriage`.
2. Create the access token (below), with `schema.bases:write` added for this one run, and put it and the base id
   into `.env` without showing them:
   `powershell -ExecutionPolicy Bypass -File tools\set-secret.ps1 AIRTABLE_TOKEN` (and `AIRTABLE_BASE_ID`).
3. `uv run python tools/airtable_setup.py` creates both tables with every field below. The schema is code in that
   script; running it again only adds what is missing.
4. Remove `schema.bases:write` from the token again.
5. Create the three views by hand (the Airtable API cannot create views), and delete the default "Table 1".
6. Set `AIRTABLE_MODE=on` in `.env`, then `docker compose run --rm n8n-init` and `docker compose up -d n8n`.

The tables below describe the same schema for people, and for creating it by hand.

## Table `Leads`

One record per person (e-mail) per 30 days: a new message from the same e-mail within 30 days updates the record and
is appended to `History`.

| # | Field | Type | Notes |
|---|---|---|---|
| 1 | `Name` | Single line text | primary field (rename the default "Name" field if it is already there) |
| 2 | `Email` | Email | dedupe key, stored lower-case |
| 3 | `Phone` | Phone number | |
| 4 | `Source` | Single select | `verde-kitchen`, `demo-form` |
| 5 | `ExternalId` | Single line text | the source's id, e.g. `verde-kitchen:contact:123` |
| 6 | `LeadId` | Single line text | LeadTriage's id of the first message |
| 7 | `Message` | Long text | the latest message |
| 8 | `History` | Long text | earlier messages, newest first, with time and lead id |
| 9 | `Category` | Single select | `product_question`, `where_to_buy`, `wholesale`, `order_issue`, `complaint`, `partnership`, `spam`, `other` |
| 10 | `Priority` | Single select | `high`, `medium`, `low` |
| 11 | `Language` | Single select | `uk`, `en`, `other` |
| 12 | `Summary` | Long text | ≤ 200 characters |
| 13 | `ReplyDraft` | Long text | ≤ 600 characters; a draft for a person, never sent automatically |
| 14 | `Confidence` | Number | decimal, precision 1.00 |
| 15 | `NeedsReview` | Checkbox | invalid LLM output, LLM not reachable, or low confidence |
| 16 | `Issues` | Long text | why it needs review (field names and reasons, no lead text) |
| 17 | `RawText` | Long text | the model's raw answer, only when it was invalid (for debugging) |
| 18 | `EmailDomain` | Single line text | |
| 19 | `FreeMail` | Checkbox | gmail, ukr.net, … |
| 20 | `Disposable` | Checkbox | throwaway address services |
| 21 | `PhoneCountry` | Single line text | from the calling code |
| 22 | `Model` | Single line text | `mock` or the Claude model name |
| 23 | `InputTokens` | Number | integer |
| 24 | `OutputTokens` | Number | integer |
| 25 | `CostUsd` | Number | decimal, precision 1.000000 (or the finest Airtable offers) |
| 26 | `LatencyMs` | Number | integer |
| 27 | `ReceivedAt` | Date | include time, 24-hour, "Use the same time zone for all collaborators": Kyiv (Airtable still calls it `Europe/Kiev`) |
| 28 | `Status` | Single select | `new`, `in progress`, `done` — set by people; the workflow sets `new` on create only |

### Views

| View | Type | Filter | Sort |
|---|---|---|---|
| `Urgent` | Grid | `Priority` is `high` **and** `Status` is `new` | `ReceivedAt` newest first |
| `Needs review` | Grid | `NeedsReview` is checked | `ReceivedAt` newest first |
| `Wholesale` | Grid | `Category` is `wholesale` | `ReceivedAt` newest first |

## Table `Errors`

Filled by the Error Trigger workflow (phase 6). No secrets and no full payloads.

| # | Field | Type |
|---|---|---|
| 1 | `Workflow` | Single line text (primary) |
| 2 | `Node` | Single line text |
| 3 | `Message` | Long text |
| 4 | `ExecutionId` | Single line text |
| 5 | `OccurredAt` | Date, include time, Europe/Kyiv |

## Access token

A personal access token (<https://airtable.com/create/tokens>) with only these scopes:

- `data.records:read`
- `data.records:write`
- `schema.bases:read`
- (`schema.bases:write` only while `tools/airtable_setup.py` runs; remove it afterwards)

Access: only the `LeadTriage` base. The token goes into the git-ignored `.env` as `AIRTABLE_TOKEN` (with
`AIRTABLE_BASE_ID`, the `app…` part of the base URL); `docker compose run --rm n8n-init` copies it into n8n's
encrypted credential store. It never goes into the repository or the chat.

## How the workflow uses it

`Airtable on?` (IF on `AIRTABLE_MODE`) → `Find by email` (formula: same `Email` and `ReceivedAt` within 30 days; the
e-mail is inserted with `JSON.stringify`, so quotes in an address cannot change the formula) → `Prepare record`
(Code: fields named like the columns; for a known lead the earlier message moves into `History`) →
`Known lead?` → `Update lead` or `Create lead` (both "auto-map" the prepared fields).

## Free plan limits

The free plan limits records per base and API calls per month. Each lead costs two calls (search + create/update).
Check the current numbers on Airtable's pricing page before relying on them; phase 10 adds retention and a limit
check for the live site.
