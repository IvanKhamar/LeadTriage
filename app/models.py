"""Request and response models of the lead intake contract v1 (docs/lead-intake-contract.md).

JSON uses camelCase (the contract), Python uses snake_case; `alias_generator=to_camel` maps the two,
like [JsonPropertyName] in C#.
"""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, StringConstraints
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30, pattern=r"^\+?[0-9 ()\-]{6,30}$")]
PageUrl = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500, pattern=r"^https?://")]
ExternalId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class LeadIn(CamelModel):
    """The payload both entry points accept. Unknown fields are ignored, so a source may send more."""

    external_id: ExternalId | None = None
    name: Name
    email: EmailStr
    phone: Phone | None = None
    message: Message
    consent: Literal[True]  # the visitor must agree; anything else is a 400
    locale: Literal["uk", "en"]
    page_url: PageUrl | None = None
    submitted_at: AwareDatetime  # ISO 8601 with a zone; a time without a zone is a 400


class SourceLeadIn(LeadIn):
    """Server-to-server sources must send their own id: it makes their retries idempotent."""

    external_id: ExternalId


class DemoLeadIn(LeadIn):
    """The demo form adds a honeypot: a field people never see, so only bots fill it in."""

    website: str | None = Field(default=None, max_length=200)


class IntakeAnswer(CamelModel):
    status: Literal["received", "duplicate"]
    lead_id: str
    # Only the demo form gets it: the classification n8n answered with, shown on the page.
    triage: dict | None = None


class EnrichIn(CamelModel):
    email: str = Field(max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    message: str = Field(max_length=4000)


class EnrichOut(CamelModel):
    email_domain: str
    free_mail: bool
    disposable: bool
    phone_country: str | None
    message_length: int
    word_count: int
    language_guess: Literal["uk", "en", "other"]


class ValidateIn(CamelModel):
    # Who answered: decides which prices apply (mock costs nothing).
    provider: Literal["claude", "gemini", "mock"] = "claude"
    raw_text: str = Field(max_length=20000)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class Classification(CamelModel):
    category: Literal[
        "product_question", "where_to_buy", "wholesale", "order_issue", "complaint", "partnership", "spam", "other"
    ]
    priority: Literal["high", "medium", "low"]
    language: Literal["uk", "en", "other"]
    summary: str = Field(max_length=200)
    reply_draft: str = Field(max_length=600)
    confidence: float = Field(ge=0, le=1)


class ValidateOut(CamelModel):
    classification: Classification
    needs_review: bool
    # Problems found in the model output (field names and reasons, never the lead text). Empty when valid.
    issues: list[str]
    # Kept only when the output was invalid, for debugging in Airtable.
    raw_text: str | None
    cost_usd: float
