"""Apartment chat module.

Answers natural-language (Hebrew) questions about the apartment listings.
Uses a local Ollama model when one is reachable, and falls back to a
deterministic rule-based engine so the feature keeps working fully offline
without any API keys.
"""

import os

import requests

import listings_search as ls
from listings_search import DEAL_LABELS, TYPE_LABELS

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "30"))


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
    criteria = ls.parse_query(user_message, listings)

    if not criteria:
        sample = "\n".join(_format_listing(item) for item in listings[:3])
        return (
            "אפשר לחפש לפי עיר, סוג עסקה (מכירה/השכרה), מספר חדרים, מחיר מקסימלי "
            "('עד 2000000') או מאפיינים (למשל 'מרפסת', 'חניה').\n\n"
            "הנה כמה דירות לדוגמה:\n\n" + sample
        )

    results = ls.filter_by_criteria(listings, criteria)
    description = ls.describe_criteria(criteria)

    if not results:
        return f"לא נמצאו דירות שתואמות ל: {description}. נסו להרחיב את החיפוש."

    body = "\n\n".join(_format_listing(item) for item in results)
    return f"נמצאו {len(results)} דירות עבור: {description}\n\n{body}"


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
