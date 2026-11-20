"""Deterministic enrichment: facts about a lead computed by plain rules, no AI.

Cheap, fast and testable, so the LLM gets them as context and a human can trust them.
"""

import re

from app.models import EnrichOut

FREE_MAIL = frozenset(
    {
        "gmail.com", "googlemail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com", "icloud.com", "me.com",
        "aol.com", "proton.me", "protonmail.com", "gmx.com", "gmx.de", "mail.com", "zoho.com",
        "ukr.net", "i.ua", "meta.ua", "email.ua", "bigmir.net", "wp.pl", "onet.pl", "o2.pl",
    }
)  # fmt: skip

# A small static list on purpose: catches the common throwaway services without a network call.
DISPOSABLE = frozenset(
    {
        "mailinator.com", "guerrillamail.com", "guerrillamail.net", "sharklasers.com", "10minutemail.com",
        "temp-mail.org", "tempmail.com", "yopmail.com", "trashmail.com", "getnada.com", "dispostable.com",
        "maildrop.cc", "throwawaymail.com", "fakeinbox.com", "mintemail.com",
    }
)  # fmt: skip

# Calling codes → ISO country. Longest prefix wins (+380 before +38, +1 is shared by the US and Canada).
CALLING_CODES = {
    "380": "UA", "48": "PL", "49": "DE", "44": "GB", "33": "FR", "39": "IT", "34": "ES", "31": "NL",
    "32": "BE", "43": "AT", "420": "CZ", "421": "SK", "36": "HU", "40": "RO", "373": "MD", "370": "LT",
    "371": "LV", "372": "EE", "45": "DK", "46": "SE", "47": "NO", "358": "FI", "41": "CH", "90": "TR",
    "1": "US/CA",
}  # fmt: skip

UK_ONLY = set("іїєґ")  # letters Ukrainian has and Russian does not
RU_ONLY = set("ыэъё")  # and the other way round
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
LATIN = re.compile(r"[a-zA-Z]")


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower() if "@" in email else ""


def phone_country(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if phone.strip().startswith("00"):
        digits = digits[2:]
    elif not phone.strip().startswith("+"):
        # No international prefix: a Ukrainian local number (0XX XXX XX XX) is the common case for this shop.
        return "UA" if len(digits) == 10 and digits.startswith("0") else None
    for length in (3, 2, 1):
        country = CALLING_CODES.get(digits[:length])
        if country:
            return country
    return None


def guess_language(text: str) -> str:
    """Counts letters: mostly Latin → en; Cyrillic with Ukrainian-only letters → uk; with Russian-only → other.
    Cyrillic without either marker is most likely Ukrainian on this site."""
    lower = text.lower()
    cyrillic = len(CYRILLIC.findall(lower))
    latin = len(LATIN.findall(lower))
    if cyrillic == 0 and latin == 0:
        return "other"
    if latin > cyrillic:
        return "en"
    uk_marks = sum(lower.count(ch) for ch in UK_ONLY)
    ru_marks = sum(lower.count(ch) for ch in RU_ONLY)
    if ru_marks > uk_marks:
        return "other"
    return "uk"


def enrich(email: str, phone: str | None, message: str) -> EnrichOut:
    domain = email_domain(email)
    return EnrichOut(
        email_domain=domain,
        free_mail=domain in FREE_MAIL,
        disposable=domain in DISPOSABLE,
        phone_country=phone_country(phone),
        message_length=len(message),
        word_count=len(message.split()),
        language_guess=guess_language(message),
    )
