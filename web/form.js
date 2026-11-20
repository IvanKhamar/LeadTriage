// Demo form: client-side checks for quick feedback (the API checks everything again), then POST /api/leads.
// The page talks only to its own origin; no token is ever needed or present here.
"use strict";

const form = document.getElementById("lead-form");
const statusLine = document.getElementById("status");
const submit = document.getElementById("submit");
const message = document.getElementById("message");
const result = document.getElementById("result");

message.addEventListener("input", () => {
  document.getElementById("message-count").textContent = String(message.value.length);
});

function fieldOk(input) {
  const value = input.type === "checkbox" ? input.checked : input.value.trim();
  if (input.type === "checkbox") return value;
  if (input.id === "phone" && value === "") return true;
  if (input.id === "message" || input.id === "name") {
    return value.length >= Number(input.minLength) && value.length <= Number(input.maxLength);
  }
  return input.checkValidity() && value !== "";
}

function markFields(names) {
  for (const box of form.querySelectorAll(".field")) box.classList.remove("invalid");
  for (const name of names) {
    const input = document.getElementById(name);
    if (input) input.closest(".field").classList.add("invalid");
  }
}

function setStatus(text, kind) {
  statusLine.textContent = text;
  statusLine.className = "status " + (kind || "");
}

function show(id, text) {
  document.getElementById(id).textContent = text;
}

function showTriage(leadId, triage) {
  if (!triage || !triage.classification) {
    result.hidden = true;
    return;
  }
  const c = triage.classification;
  show("r-category", c.category);
  const priority = document.getElementById("r-priority");
  priority.textContent = "";
  const badge = document.createElement("span");
  badge.className = "badge " + c.priority;
  badge.textContent = c.priority;
  priority.appendChild(badge);
  show("r-language", c.language);
  show("r-confidence", Number(c.confidence).toFixed(2));
  show("r-review", triage.needsReview ? "yes" : "no");
  show("r-summary", c.summary || "—");
  show("r-reply", c.replyDraft || "—");
  show("r-id", leadId);
  result.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const names = ["name", "email", "phone", "message", "consent"];
  const bad = names.filter((name) => !fieldOk(document.getElementById(name)));
  markFields(bad);
  if (bad.length) {
    setStatus("Please check the marked fields.", "fail");
    document.getElementById(bad[0]).focus();
    return;
  }

  const body = {
    name: form.name.value.trim(),
    email: form.email.value.trim(),
    phone: form.phone.value.trim() || null,
    message: form.message.value.trim(),
    consent: form.consent.checked,
    locale: form.locale.value,
    pageUrl: window.location.href,
    submittedAt: new Date().toISOString(),
    website: form.website.value,
  };

  submit.disabled = true;
  setStatus("Sending… the workflow may take a few seconds.");
  result.hidden = true;
  try {
    const response = await fetch("/api/leads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 202 || response.status === 200) {
      setStatus("Thank you! Your message was received.", "ok");
      showTriage(data.leadId, data.triage);
      form.reset();
      document.getElementById("message-count").textContent = "0";
    } else if (response.status === 400) {
      markFields(data.errors || []);
      setStatus("Please check the marked fields.", "fail");
    } else if (response.status === 429) {
      setStatus("Too many messages from your address. Please wait a minute.", "fail");
    } else if (response.status === 503) {
      setStatus("The service is busy right now. Please try again in a minute.", "fail");
    } else {
      setStatus("Something went wrong. Please try again later.", "fail");
    }
  } catch {
    setStatus("No connection to the server. Please try again.", "fail");
  } finally {
    submit.disabled = false;
  }
});
