// Prints n8n credentials as JSON for `n8n import:credentials`, built from the init container's environment.
// n8n encrypts `data` with N8N_ENCRYPTION_KEY on import. The ids are fixed, so the workflow JSON in git can refer
// to them without holding any value.
"use strict";

function required(name) {
  const value = process.env[name];
  if (!value) {
    console.error(`LeadTriage init: ${name} is not set in .env`);
    process.exit(1);
  }
  return value;
}

const credentials = [
  {
    id: "ltWebhookToken01",
    name: "LeadTriage webhook token",
    type: "httpHeaderAuth",
    data: { name: "X-Webhook-Token", value: required("WEBHOOK_TOKEN") },
  },
  {
    id: "ltAppToken000001",
    name: "LeadTriage app token",
    type: "httpHeaderAuth",
    data: { name: "X-Enrich-Token", value: required("ENRICH_TOKEN") },
  },
  {
    // Always created, so the workflow can be published without an Airtable account. With AIRTABLE_MODE=off the
    // Airtable nodes never run; with a placeholder token and AIRTABLE_MODE=on, Airtable answers 401.
    id: "ltAirtable000001",
    name: "LeadTriage Airtable token",
    type: "airtableTokenApi",
    data: { accessToken: process.env.AIRTABLE_TOKEN || "not-set" },
  },
  {
    // Same idea: with LLM_MODE=mock the Claude node never runs; a placeholder key gets a 401 from Anthropic,
    // which the workflow handles like any Claude failure (the lead is saved with needsReview).
    id: "ltAnthropicKey01",
    name: "LeadTriage Anthropic key",
    type: "httpHeaderAuth",
    data: { name: "x-api-key", value: process.env.ANTHROPIC_API_KEY || "not-set" },
  },
];

process.stdout.write(JSON.stringify(credentials));
