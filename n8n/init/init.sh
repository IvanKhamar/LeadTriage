#!/bin/sh
# Imports LeadTriage's credentials and workflows into n8n and publishes the workflows.
# Run:  docker compose run --rm n8n-init   then   docker compose restart n8n   (if n8n was already running).
# Safe to run again: the same ids are updated, so the workflows in git always win over edits made in the UI
# (export UI edits first with tools/export_workflows.py).
set -eu

creds=$(mktemp)
# The credential file holds plain token values: it lives only inside this throwaway container and is deleted.
trap 'rm -f "$creds"' EXIT

node /init/credentials.js > "$creds"
n8n import:credentials --input="$creds"
n8n import:workflow --separate --input=/workflows

for id in $(node -e '
  const fs = require("fs");
  for (const f of fs.readdirSync("/workflows").filter((f) => f.endsWith(".json"))) {
    const wf = JSON.parse(fs.readFileSync("/workflows/" + f, "utf8"));
    if (wf.active) console.log(wf.id);
  }'); do
  n8n publish:workflow --id="$id"
done

echo "LeadTriage: credentials and workflows imported. If n8n is running, restart it: docker compose restart n8n"
