"""Validation of the LLM's classification. n8n calls it through POST /api/validate.

Why here and not in an n8n Code node: one implementation, covered by pytest, that cannot drift from a copy.
The model's output is untrusted data: it is parsed, checked against enums and lengths, and anything else falls back
to a safe default with needsReview = true. Nothing is executed or sent because of what the model wrote.
"""

import json
import re

from pydantic import ValidationError

from app.models import Classification, ValidateOut

# Below this the classification goes to a human even when it is formally valid.
MIN_CONFIDENCE = 0.5

FALLBACK = Classification(
    category="other", priority="medium", language="other", summary="", reply_draft="", confidence=0.0
)

FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def cost_usd(input_tokens: int, output_tokens: int, price_in_per_mtok: float, price_out_per_mtok: float) -> float:
    return round(input_tokens * price_in_per_mtok / 1e6 + output_tokens * price_out_per_mtok / 1e6, 6)


def _extract_json(raw: str) -> object:
    """Accepts plain JSON or JSON inside a ``` fence (models sometimes add one)."""
    text = raw.strip()
    match = FENCE.match(text)
    if match:
        text = match.group(1)
    return json.loads(text)


def validate(raw_text: str, input_tokens: int, output_tokens: int, price_in: float, price_out: float) -> ValidateOut:
    cost = cost_usd(input_tokens, output_tokens, price_in, price_out)

    def fallback(issues: list[str]) -> ValidateOut:
        return ValidateOut(
            classification=FALLBACK, needs_review=True, issues=issues, raw_text=raw_text[:5000], cost_usd=cost
        )

    try:
        data = _extract_json(raw_text)
    except ValueError:
        return fallback(["not valid JSON"])
    if not isinstance(data, dict):
        return fallback(["not a JSON object"])

    try:
        classification = Classification.model_validate(data)
    except ValidationError as exc:
        # Field names and error kinds only, e.g. "category: literal_error".
        return fallback([f"{'.'.join(str(p) for p in e['loc'])}: {e['type']}" for e in exc.errors()])

    issues = [] if classification.confidence >= MIN_CONFIDENCE else ["low confidence"]
    return ValidateOut(
        classification=classification, needs_review=bool(issues), issues=issues, raw_text=None, cost_usd=cost
    )
