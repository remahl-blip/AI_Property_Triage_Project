"""LLM helper service — Ollama-backed endpoints for n8n (substitutes Gemini/GPT nodes)."""

import json
import os
import re

import requests
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="LLM Service (Layer 4 — local Ollama)")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))


def _ollama_chat(system: str, user: str) -> str:
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
            },
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception:
        return ""


EXTRACTOR_SYSTEM = """You extract structured fields from real-estate listing text.
Return ONLY valid JSON with keys: property_type, location, price, rooms, features, certifications.
Use null for missing fields. Extract only facts present in the text — never invent values.
property_type must be one of: apartment, house, villa, office, retail, industrial, studio, other.
features is an array of strings. price is a number or null. rooms is an integer or null."""

AGENT_SYSTEM = """You are a senior property analyst. Given structured listing fields and service outputs,
produce a JSON object with keys: summary, recommended_actions, risk_flags, confidence (0-1).
Do not invent prices or legal claims. Base your answer only on the provided data."""

REPORT_SYSTEM = """You write a publishable property listing brief in Markdown (Hebrew preferred).
Integrate: extracted fields, image condition scores, similar listings from RAG.
Do not invent missing information. Include sections: Overview, Key Features, Condition, Comparable Listings, Recommendation."""


class ExtractRequest(BaseModel):
    text: str = Field(..., min_length=1)


class AgentRequest(BaseModel):
    extracted_fields: dict = Field(default_factory=dict)
    rag_result: dict = Field(default_factory=dict)
    image_results: list = Field(default_factory=list)
    query: str = ""


class ReportRequest(BaseModel):
    extracted_fields: dict = Field(default_factory=dict)
    rag_result: dict = Field(default_factory=dict)
    image_results: list = Field(default_factory=list)
    agent_result: dict = Field(default_factory=dict)


def _parse_json_from_llm(text: str) -> dict:
    if not text:
        return {}
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"raw": text}


def _rule_extract(text: str) -> dict:
    """Offline fallback extractor (Node 4 substitute)."""
    lowered = text.lower()
    result = {
        "property_type": None,
        "location": None,
        "price": None,
        "rooms": None,
        "features": [],
        "certifications": None,
    }
    types = {
        "apartment": ("apartment", "דירה", "דירת", "flat"),
        "house": ("house", "בית", "cottage"),
        "villa": ("villa", "וילה"),
        "office": ("office", "משרד"),
        "retail": ("retail", "חנות"),
        "industrial": ("industrial", "מחסן"),
    }
    for ptype, hints in types.items():
        if any(h in lowered for h in hints):
            result["property_type"] = ptype
            break
    cities = ["תל אביב", "חיפה", "ירושלים", "הרצליה", "נתניה", "tel aviv", "haifa"]
    for city in cities:
        if city.lower() in lowered or city in text:
            result["location"] = city
            break
    rooms_m = re.search(r"(\d+)\s*(?:rooms?|חדר)", lowered)
    if rooms_m:
        result["rooms"] = int(rooms_m.group(1))
    price_m = re.search(r"(\d[\d,]{3,})", text.replace(",", ""))
    if price_m:
        result["price"] = int(price_m.group(1).replace(",", ""))
    for feat in ("מרפסת", "חניה", "מעלית", "balcony", "parking", "elevator", "pool"):
        if feat in lowered or feat in text:
            result["features"].append(feat)
    return result


@app.post("/extract")
def extract_fields(request: ExtractRequest):
    llm_out = _ollama_chat(EXTRACTOR_SYSTEM, request.text)
    fields = _parse_json_from_llm(llm_out)
    if not fields or "raw" in fields:
        fields = _rule_extract(request.text)
    return {"extracted_fields": fields, "source": "ollama" if llm_out else "rule-based"}


@app.post("/agent")
def run_agent(request: AgentRequest):
    payload = json.dumps({
        "extracted": request.extracted_fields,
        "rag": request.rag_result,
        "images": request.image_results,
        "query": request.query,
    }, ensure_ascii=False)
    llm_out = _ollama_chat(AGENT_SYSTEM, payload)
    result = _parse_json_from_llm(llm_out)
    if not result or "raw" in result:
        similar = request.rag_result.get("similar_listings", [])
        result = {
            "summary": request.rag_result.get("insight", "Analysis complete."),
            "recommended_actions": ["Review similar listings", "Schedule inspection"],
            "risk_flags": [],
            "confidence": 0.7 if similar else 0.5,
        }
    return {"agent_result": result, "source": "ollama" if llm_out else "rule-based"}


@app.post("/report")
def write_report(request: ReportRequest):
    payload = json.dumps({
        "extracted": request.extracted_fields,
        "rag": request.rag_result,
        "images": request.image_results,
        "agent": request.agent_result,
    }, ensure_ascii=False)
    llm_out = _ollama_chat(REPORT_SYSTEM, payload)
    if llm_out:
        return {"report_markdown": llm_out, "format": "markdown", "source": "ollama"}
    # Offline template
    ext = request.extracted_fields
    lines = [
        "# דוח נכס",
        f"**סוג:** {ext.get('property_type', 'לא צוין')}",
        f"**מיקום:** {ext.get('location', 'לא צוין')}",
        f"**חדרים:** {ext.get('rooms', 'לא צוין')}",
        f"**מחיר:** {ext.get('price', 'לא צוין')}",
        "",
        "## תובנות",
        request.rag_result.get("insight", ""),
        "",
        "## המלצות",
        str(request.agent_result.get("summary", "")),
    ]
    return {"report_markdown": "\n".join(lines), "format": "markdown", "source": "template"}


@app.get("/health")
def health():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        ollama_up = r.status_code == 200
    except Exception:
        ollama_up = False
    return {"status": "ok", "ollama_available": ollama_up, "model": OLLAMA_MODEL}
