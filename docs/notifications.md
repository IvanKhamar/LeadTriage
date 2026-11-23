# Notifications

High-priority leads (wholesale and stockist requests, complaints, order problems) should reach a person quickly.

## 1. The "Urgent" view in Airtable (main channel)

The `Leads` table has a view **Urgent**: `Priority` is `high` and `Status` is `new`, newest first
(see [airtable-schema.md](airtable-schema.md)). The manager works from this view and sets `Status` to `in progress`
or `done`, which takes the lead out of it. Nothing to run or pay for.

Optional, set up in Airtable itself: an automation "When a record enters view **Urgent** → Send an e-mail" (or a
Slack message). It runs on Airtable's side, so LeadTriage needs no mail server. The free plan limits automation runs
per month; check the current number on Airtable's pricing page.

## 2. Telegram (optional, off by default)

After the webhook has answered, the workflow checks `Urgent and Telegram on?` (priority `high` **and**
`NOTIFY_TELEGRAM=true`) and sends a short message through the **Telegram alert** node:

```
Urgent lead: wholesale (uk)
A cafe owner in Lviv wants weekly wholesale orders and asks about conditions.
Source: verde-kitchen, 2026-11-23 14:10 Kyiv time
Open the "Urgent" view in Airtable.
```

- No name, e-mail or phone in the chat: the details stay in Airtable.
- A failed alert (bot blocked, wrong token, Telegram down) never fails the lead: it is already saved and answered.
  The node retries once and then lets the run finish.

### Setting it up

1. In Telegram, open **@BotFather** → `/newbot` → choose a name. It gives you the bot token.
2. Send any message to your new bot, then open `https://api.telegram.org/bot<token>/getUpdates` in a browser:
   `"chat":{"id":...}` is your chat id. (Do this on your own machine; the token is in that URL.)
3. Put the token into `.env` without showing it:
   `powershell -ExecutionPolicy Bypass -File tools\set-secret.ps1 TELEGRAM_BOT_TOKEN`
4. In `.env` set `TELEGRAM_CHAT_ID=<the id>` and `NOTIFY_TELEGRAM=true`.
5. `docker compose run --rm n8n-init`, then `docker compose up -d n8n`.

Checked: with `NOTIFY_TELEGRAM=true` and a fake token, a high-priority lead was saved and answered as usual (4 s),
and the failed alert did not start the error workflow. A real send needs a real bot.
