"""HTTP endpoints: the two intake entry points (contract v1) and the two helpers n8n calls."""

import logging
import uuid
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app import classification, enrich
from app.config import Settings
from app.forwarder import ForwardError, N8nForwarder
from app.models import DemoLeadIn, EnrichIn, EnrichOut, IntakeAnswer, LeadIn, SourceLeadIn, ValidateIn, ValidateOut
from app.ratelimit import RateLimiter
from app.security import token_matches
from app.store import IdempotencyStore

log = logging.getLogger("leadtriage")
KYIV = ZoneInfo("Europe/Kyiv")
DEMO_SOURCE = "demo-form"

router = APIRouter(prefix="/api")

PROBLEM = {"content": {"application/problem+json": {}}}
INTAKE_RESPONSES = {
    200: {"model": IntakeAnswer, "description": "Duplicate: this externalId was accepted before"},
    400: {**PROBLEM, "description": "Validation failed; `errors` lists the field names"},
    413: {**PROBLEM, "description": "Body too large"},
    503: {**PROBLEM, "description": "n8n cannot be reached; retry later"},
}


def settings_of(request: Request) -> Settings:
    return request.app.state.settings


def rate_limited(request: Request) -> None:
    limiter: RateLimiter = request.app.state.limiter
    ip = request.client.host if request.client else "unknown"
    wait = limiter.retry_after(ip)
    if wait:
        raise HTTPException(429, headers={"Retry-After": str(wait)})


def source_authorized(request: Request, source: str, x_source_token: Annotated[str | None, Header()] = None) -> None:
    """An unknown source gets the same 401 as a wrong token: no hint which sources exist."""
    expected = settings_of(request).source_tokens().get(source)
    if expected is None or not token_matches(x_source_token, expected):
        raise HTTPException(401, "Missing or wrong X-Source-Token.")


def n8n_authorized(request: Request, x_enrich_token: Annotated[str | None, Header()] = None) -> None:
    if not token_matches(x_enrich_token, settings_of(request).enrich_token):
        raise HTTPException(401, "Missing or wrong X-Enrich-Token.")


async def accept(request: Request, lead: LeadIn, source: str, *, show_triage: bool) -> JSONResponse:
    """Shared by both entry points: idempotency check, forward to n8n, answer per contract."""
    state = request.app.state
    store: IdempotencyStore = state.store
    forwarder: N8nForwarder = state.forwarder
    received_at = datetime.now(KYIV)
    external_id = lead.external_id

    if external_id:
        reservation = store.reserve(source, external_id, received_at)
        if reservation.outcome == "forwarded":
            log.info("duplicate lead %s from %s", reservation.lead_id, source)
            body = IntakeAnswer(status="duplicate", lead_id=reservation.lead_id)
            return JSONResponse(body.model_dump(by_alias=True, exclude_none=True), status_code=200)
        if reservation.outcome == "pending":
            # Another request with the same id is in flight. "Duplicate" here could lose the lead if that one fails.
            raise HTTPException(503, "This externalId is being processed.", headers={"Retry-After": "30"})
        lead_id = reservation.lead_id
    else:
        lead_id = str(uuid.uuid4())

    payload = {
        "leadId": lead_id,
        "source": source,
        "receivedAt": received_at.isoformat(),
        **lead.model_dump(by_alias=True, mode="json", exclude={"website"}),
    }
    try:
        answer = await forwarder.forward(payload)
    except ForwardError:
        if external_id:
            store.release(source, external_id)
        log.warning("lead %s from %s not forwarded; answered 503", lead_id, source)
        raise HTTPException(503, headers={"Retry-After": "60"}) from None

    if external_id:
        store.mark_forwarded(source, external_id)
    log.info("lead %s from %s forwarded", lead_id, source)
    triage = answer.get("triage") if show_triage and isinstance(answer.get("triage"), dict) else None
    body = IntakeAnswer(status="received", lead_id=lead_id, triage=triage)
    return JSONResponse(body.model_dump(by_alias=True, exclude_none=True), status_code=202)


@router.post(
    "/leads",
    status_code=202,
    response_model=IntakeAnswer,
    responses={**INTAKE_RESPONSES, 429: {**PROBLEM, "description": "Rate limit per IP"}},
    dependencies=[Depends(rate_limited)],
    summary="Lead from the demo form (browser, same origin)",
)
async def demo_lead(request: Request, lead: DemoLeadIn) -> JSONResponse:
    if lead.website:
        # Honeypot filled: a bot. Answer as usual so it learns nothing; log without personal data.
        log.info("honeypot: dropped a demo-form submission")
        body = IntakeAnswer(status="received", lead_id=str(uuid.uuid4()))
        return JSONResponse(body.model_dump(by_alias=True, exclude_none=True), status_code=202)
    return await accept(request, lead, DEMO_SOURCE, show_triage=True)


@router.post(
    "/sources/{source}/leads",
    status_code=202,
    response_model=IntakeAnswer,
    responses={**INTAKE_RESPONSES, 401: {**PROBLEM, "description": "Missing or wrong X-Source-Token"}},
    dependencies=[Depends(source_authorized)],
    summary="Lead from a server-to-server source (first one: verde-kitchen)",
)
async def source_lead(request: Request, source: str, lead: SourceLeadIn) -> JSONResponse:
    return await accept(request, lead, source, show_triage=False)


@router.post(
    "/enrich",
    response_model=EnrichOut,
    dependencies=[Depends(n8n_authorized)],
    summary="Deterministic facts about a lead (called by n8n)",
)
def enrich_lead(body: EnrichIn) -> EnrichOut:
    return enrich.enrich(body.email, body.phone, body.message)


@router.post(
    "/validate",
    response_model=ValidateOut,
    dependencies=[Depends(n8n_authorized)],
    summary="Validate the LLM classification and compute its cost (called by n8n)",
)
def validate_classification(request: Request, body: ValidateIn) -> ValidateOut:
    settings = settings_of(request)
    return classification.validate(
        body.raw_text,
        body.input_tokens,
        body.output_tokens,
        settings.llm_price_input_per_mtok,
        settings.llm_price_output_per_mtok,
    )
