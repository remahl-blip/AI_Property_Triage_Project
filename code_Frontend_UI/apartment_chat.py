"""Apartment chat module.

Answers natural-language (Hebrew) questions about the apartment listings.
Uses a local Ollama model when one is reachable, and falls back to a
deterministic rule-based engine so the feature keeps working fully offline
without any API keys.
"""

import os
import re

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "30"))

DEAL_LABELS = {"sale": "מכירה", "rent": "השכרה"}
TYPE_LABELS = {
    "apartment": "דירה",
    "villa": "וילה",
    "house": "בית",
    "penthouse": "פנטהאוז",
    "studio": "סטודיו",
    "duplex": "דופלקס",
    "cottage": "קוטג'",
}

_RENT_WORDS = ["השכרה", "להשכרה", "שכירות", "לשכור", "שכירה"]
_SALE_WORDS = ["מכירה", "למכירה", "לקנות", "קנייה", "קניה", "רכישה"]


def ollama_available():
    """Return True if a local Ollama server responds."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _listings_context(listings):
    lines = []
    for item in listings:
        deal = DEAL_LABELS.get(item.get("deal"), item.get("deal", ""))
        ptype = TYPE_LABELS.get(item.get("property_type"), item.get("property_type", ""))
        features = ", ".join(item.get("features", []) or [])
        lines.append(
            f"- {item.get('id')}: {item.get('title')} | {ptype} | {deal} | "
            f"עיר: {item.get('city')} ({item.get('neighborhood', '')}) | "
            f"{item.get('rooms')} חדרים | {item.get('size_sqm')} מ\"ר | "
            f"מחיר: {item.get('price')} ₪ | מאפיינים: {features}"
        )
    return "\n".join(lines)


def _ollama_chat(user_message, listings, history=None):
    system_prompt = (
        "אתה עוזר נדל\"ן שעונה בעברית בלבד, בקצרה וברורה. "
        "ענה אך ורק על סמך רשימת הדירות הבאה. אם אין דירה מתאימה, אמור זאת. "
        "כשאתה ממליץ על דירה, ציין את המזהה (id), העיר והמחיר.\n\n"
        "רשימת הדירות:\n" + _listings_context(listings)
    )
    messages = [{"role": "system", "content": system_prompt}]
    for turn in (history or []):
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"].strip()


def _parse_filters(text, listings):
    filters = {}

    lowered = text

    if any(word in lowered for word in _RENT_WORDS):
        filters["deal"] = "rent"
    elif any(word in lowered for word in _SALE_WORDS):
        filters["deal"] = "sale"

    cities = {item.get("city") for item in listings if item.get("city")}
    for city in cities:
        if city and city in text:
            filters["city"] = city
            break

    for ptype, label in TYPE_LABELS.items():
        if label and label in text:
            filters["property_type"] = ptype
            break

    rooms_match = re.search(r"(\d+)\s*חדר", text)
    if rooms_match:
        filters["rooms"] = int(rooms_match.group(1))

    price_match = re.search(r"עד\s*([\d,]+)", text)
    if price_match:
        filters["max_price"] = int(price_match.group(1).replace(",", ""))

    feature_vocab = set()
    for item in listings:
        for feat in item.get("features", []) or []:
            feature_vocab.add(feat)
    matched_features = [feat for feat in feature_vocab if feat in text]
    if matched_features:
        filters["features"] = matched_features

    return filters


def _apply_filters(filters, listings):
    results = []
    for item in listings:
        if "deal" in filters and item.get("deal") != filters["deal"]:
            continue
        if "city" in filters and item.get("city") != filters["city"]:
            continue
        if "property_type" in filters and item.get("property_type") != filters["property_type"]:
            continue
        if "rooms" in filters and int(item.get("rooms", 0)) != filters["rooms"]:
            continue
        if "max_price" in filters and int(item.get("price", 0)) > filters["max_price"]:
            continue
        if "features" in filters:
            item_features = set(item.get("features", []) or [])
            if not set(filters["features"]).issubset(item_features):
                continue
        results.append(item)
    return results


def _format_listing(item):
    deal = DEAL_LABELS.get(item.get("deal"), item.get("deal", ""))
    ptype = TYPE_LABELS.get(item.get("property_type"), item.get("property_type", ""))
    return (
        f"**{item.get('title')}** (`{item.get('id')}`)\n"
        f"  - {ptype} ל{deal} ב{item.get('city')}, {item.get('neighborhood', '')}\n"
        f"  - {item.get('rooms')} חדרים · {item.get('size_sqm')} מ\"ר · "
        f"₪{int(item.get('price', 0)):,}\n"
        f"  - {item.get('description', '')}"
    )


def _rule_based(user_message, listings):
    filters = _parse_filters(user_message, listings)

    if not filters:
        sample = "\n".join(_format_listing(item) for item in listings[:3])
        return (
            "אפשר לחפש לפי עיר, סוג עסקה (מכירה/השכרה), מספר חדרים, מחיר מקסימלי "
            "('עד 2000000') או מאפיינים (למשל 'מרפסת', 'חניה').\n\n"
            "הנה כמה דירות לדוגמה:\n\n" + sample
        )

    results = _apply_filters(filters, listings)

    crit_parts = []
    if "city" in filters:
        crit_parts.append(f"עיר: {filters['city']}")
    if "deal" in filters:
        crit_parts.append(DEAL_LABELS.get(filters["deal"], filters["deal"]))
    if "property_type" in filters:
        crit_parts.append(TYPE_LABELS.get(filters["property_type"], filters["property_type"]))
    if "rooms" in filters:
        crit_parts.append(f"{filters['rooms']} חדרים")
    if "max_price" in filters:
        crit_parts.append(f"עד ₪{filters['max_price']:,}")
    if "features" in filters:
        crit_parts.append("מאפיינים: " + ", ".join(filters["features"]))
    criteria = " · ".join(crit_parts)

    if not results:
        return f"לא נמצאו דירות שתואמות ל: {criteria}. נסו להרחיב את החיפוש."

    body = "\n\n".join(_format_listing(item) for item in results)
    return f"נמצאו {len(results)} דירות עבור: {criteria}\n\n{body}"


def answer(user_message, listings, history=None):
    """Return (response_text, source) where source is 'ollama' or 'rule-based'."""
    if not user_message or not user_message.strip():
        return "כתבו שאלה על הדירות (למשל: 'דירת 3 חדרים להשכרה בתל אביב').", "rule-based"

    if ollama_available():
        try:
            return _ollama_chat(user_message, listings, history), "ollama"
        except (requests.RequestException, KeyError, ValueError):
            pass

    return _rule_based(user_message, listings), "rule-based"
