import re

from pydantic import BaseModel, Field, ConfigDict

SPAM_PATTERNS = [
    r"\b(crypto|casino|viagra|buy now|click here)\b",
    r"(הלוואות|מזל טוב|פרסומת|עקבו אחריי|שיווק|discount|free money)",
    r"(http://|https://|www\.)",
    r"(.)\1{8,}",
]

OFFENSIVE_PATTERNS = [
    r"\b(idiot|stupid|hate you)\b",
    r"(טמבל|מטומטם|שונא)",
]

REAL_ESTATE_HINTS = [
    "apartment", "house", "villa", "rent", "sale", "room", "kitchen", "bathroom",
    "office", "commercial", "property", "listing", "price", "sqm", "lease",
    "דירה", "בית", "וילה", "השכרה", "מכירה", "חדר", "מטבח", "שירותים",
    "משרד", "נכס", "מחיר", "מרפסת", "גינה", "נזילה", "תיקון", "leak", "repair",
]

INVENTED_PRICE_PATTERNS = [
    r"guaranteed\s+\d+%(?:\s+return)?",
    r"מובטח\s+\d+%",
    r"רווח\s+מובטח",
    r"price\s+will\s+double",
]

LEGAL_GUARANTEE_PATTERNS = [
    r"legally\s+guaranteed",
    r"100%\s+(?:approved|legal\s+approval)",
    r"מאושר\s+חוקית",
    r"ערבות\s+משפטית",
    r"no\s+risk\s+investment",
    r"ללא\s+סיכון",
]

FABRICATED_CERT_PATTERNS = [
    r"certified\s+by\s+ministry",
    r"(?:official\s+)?permit\s+#\d+",
    r"תעודת\s+היתר\s+רשמית",
    r"אישור\s+משרד\s+השיכון",
    r"license\s+number\s*:\s*\d{6,}",
]


class GuardrailsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pass_: bool = Field(alias="pass")
    reason: str
    safe_text: str


def _matches_any(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return pattern
    return None


def _is_real_estate_related(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in REAL_ESTATE_HINTS)


def _sanitize_text(text: str) -> str:
    cleaned = re.sub(r"https?://\S+", "[link removed]", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def check_input_text(text: str) -> GuardrailsResponse:
    raw = text or ""
    cleaned = _sanitize_text(raw)

    if len(cleaned) < 8:
        return GuardrailsResponse(
            pass_=False,
            reason="Input too short; provide a meaningful property description.",
            safe_text=cleaned,
        )

    spam = _matches_any(cleaned, SPAM_PATTERNS)
    if spam:
        return GuardrailsResponse(
            pass_=False,
            reason="Spam or promotional content detected.",
            safe_text=cleaned,
        )

    offensive = _matches_any(cleaned, OFFENSIVE_PATTERNS)
    if offensive:
        return GuardrailsResponse(
            pass_=False,
            reason="Offensive language detected.",
            safe_text=cleaned,
        )

    if not _is_real_estate_related(cleaned):
        return GuardrailsResponse(
            pass_=False,
            reason="Off-topic: input does not appear to be real-estate related.",
            safe_text=cleaned,
        )

    return GuardrailsResponse(
        pass_=True,
        reason="Input is safe and relevant.",
        safe_text=cleaned,
    )


def check_output_text(text: str) -> GuardrailsResponse:
    raw = text or ""
    cleaned = _sanitize_text(raw)

    for label, patterns in (
        ("Invented or guaranteed returns/price claims", INVENTED_PRICE_PATTERNS),
        ("Legal guarantees or risk-free claims", LEGAL_GUARANTEE_PATTERNS),
        ("Fabricated permits or certifications", FABRICATED_CERT_PATTERNS),
    ):
        hit = _matches_any(cleaned, patterns)
        if hit:
            safe = re.sub(hit, "[removed claim]", cleaned, flags=re.IGNORECASE)
            return GuardrailsResponse(
                pass_=False,
                reason=f"Output flagged: {label}.",
                safe_text=safe,
            )

    return GuardrailsResponse(
        pass_=True,
        reason="Output contains no flagged hallucinations or illegal claims.",
        safe_text=cleaned,
    )
