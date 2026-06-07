import json
import os
from typing import List

import requests
from fastapi import FastAPI
from pydantic import BaseModel, Field

try:
    from google.genai import types
    from gemini_config import (
        create_gemini_client_safe,
        describe_auth_setup,
        get_auth_mode,
        get_gemini_model,
    )

    GEMINI_AVAILABLE = True
except Exception:
    types = None
    GEMINI_AVAILABLE = False

    def get_gemini_model():
        return "gemini-2.5-flash"

    def create_gemini_client_safe():
        return None

    def get_auth_mode():
        return "none"

    def describe_auth_setup():
        return "not configured"

app = FastAPI(title="LangGraph Agent (Layer 3)")

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://rag_service:8001")
IMAGE_ANALYSER_URL = os.getenv("IMAGE_ANALYSER_URL", "http://image_analyser:8002")
TRIAGE_SERVICE_URL = os.getenv("TRIAGE_SERVICE_URL", "http://property_triage:8003")

GEMINI_MODEL = get_gemini_model() if GEMINI_AVAILABLE else "offline"
gemini_client = create_gemini_client_safe() if GEMINI_AVAILABLE else None

IMAGE_KEYWORDS = ("image", "photo", "picture", "תמונה", "צילום", "jpg", "png")
SEARCH_KEYWORDS = (
    "find", "search", "similar", "listing", "apartment", "rent", "sale",
    "דירה", "נכס", "חיפוש", "דומה", "השכרה", "מכירה",
)
ISSUE_KEYWORDS = (
    "leak", "broken", "issue", "problem", "flood", "mold", "fire", "repair",
    "נזילה", "שבור", "תקלה", "בעיה", "הצפה", "עובש", "תיקון",
)
HISTORY_KEYWORDS = (
    "history", "ticket", "tickets", "past", "previous", "report",
    "היסטוריה", "כרטיס", "דיווח", "דוחות",
)


def call_gemini_direct(prompt: str, system_instruction: str | None = None) -> str:
    if not gemini_client:
        raise ValueError("Gemini client not configured")

    config = None
    if system_instruction and types is not None:
        config = types.GenerateContentConfig(system_instruction=system_instruction)

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=config,
    )
    if not response or not response.text:
        raise ValueError("Empty response from Gemini API")
    return response.text.strip()


def rag_query_tool(description: str) -> dict:
    try:
        response = requests.post(
            f"{RAG_SERVICE_URL}/query",
            json={"description": description},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {"error": str(exc), "similar_listings": [], "insight": ""}


def image_analyse_tool(description: str, filename: str = "inspection.jpg") -> dict:
    try:
        response = requests.post(
            f"{IMAGE_ANALYSER_URL}/analyse",
            json={
                "condition_description": description,
                "filename": filename,
            },
            timeout=20,
        )
        if response.status_code == 422:
            return {
                "note": "No image bytes supplied; metadata-only analysis skipped.",
                "room_type": "unknown",
                "condition_score": 3,
                "confidence": 0.2,
            }
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {"error": str(exc)}


def fetch_property_history_tool() -> str:
    try:
        response = requests.get(f"{TRIAGE_SERVICE_URL}/history", timeout=5)
        if response.status_code == 200:
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        return f"Error fetching history: status {response.status_code}"
    except Exception as exc:
        return f"Failed to connect to triage service: {exc}"


def triage_new_issue_tool(room_type: str, description: str) -> str:
    try:
        payload = {"room_type": room_type, "condition_description": description}
        response = requests.post(f"{TRIAGE_SERVICE_URL}/triage", json=payload, timeout=5)
        if response.status_code == 200:
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        return f"Error evaluating triage: {response.text}"
    except Exception as exc:
        return f"Failed to connect to triage service: {exc}"


def detect_room_type(text: str) -> str:
    lowered = text.lower()
    rooms = {
        "kitchen": ("kitchen", "מטבח"),
        "bathroom": ("bathroom", "שירותים", "אמבטיה"),
        "bedroom": ("bedroom", "חדר שינה"),
        "living room": ("living room", "סלון"),
        "hallway": ("hallway", "מסדרון"),
    }
    for room, keywords in rooms.items():
        if any(keyword in lowered for keyword in keywords):
            return room
    return "unknown"


def _wants_tool(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def plan_agent_run(query: str) -> tuple[list[str], list[str]]:
    tools: list[str] = []
    steps: list[str] = ["Parse user query and select tools."]

    if _wants_tool(query, SEARCH_KEYWORDS):
        tools.append("rag_query")
        steps.append("User appears to search listings — schedule RAG /query.")

    if _wants_tool(query, IMAGE_KEYWORDS) or _wants_tool(query, ISSUE_KEYWORDS):
        tools.append("image_analyse")
        steps.append("Maintenance or image context detected — schedule Image Analyser.")

    if _wants_tool(query, HISTORY_KEYWORDS):
        tools.append("fetch_history")
        steps.append("History lookup requested — schedule property triage /history.")

    if _wants_tool(query, ISSUE_KEYWORDS) and "triage_issue" not in tools:
        tools.append("triage_issue")
        steps.append("New maintenance issue — schedule property triage /triage.")

    if not tools:
        tools.append("rag_query")
        steps.append("Defaulting to RAG /query for general property assistance.")

    return tools, steps


def synthesize_answer(query: str, tool_results: dict, steps: list[str]) -> str:
    try:
        prompt = (
            "Summarize the following tool results for a property manager in Hebrew "
            "(2-4 sentences). Do not invent prices.\n\n"
            f"User query: {query}\n\nTool results:\n{json.dumps(tool_results, ensure_ascii=False)}"
        )
        return call_gemini_direct(prompt)
    except Exception:
        pass

    parts = []
    if "rag_query" in tool_results:
        rag = tool_results["rag_query"]
        if rag.get("insight"):
            parts.append(rag["insight"])
        elif rag.get("similar_listings"):
            parts.append(f"נמצאו {len(rag['similar_listings'])} נכסים דומים.")
    if "image_analyse" in tool_results:
        img = tool_results["image_analyse"]
        if img.get("room_type"):
            parts.append(
                f"ניתוח תמונה: חדר {img.get('room_type')}, "
                f"ציון מצב {img.get('condition_score', 'N/A')}/5."
            )
    if "triage_issue" in tool_results:
        parts.append("הדיווח נשמר במערכת הטריאז'.")
    if "fetch_history" in tool_results:
        parts.append("היסטוריית הדיווחים נשלפה מבסיס הנתונים.")
    if not parts:
        parts.append(
            "שלום! אפשר לחפש נכסים, לנתח תמונות, או לדווח על תקלת תחזוקה."
        )
    steps.append("Synthesized final answer (offline template).")
    return " ".join(parts)


class AgentRunRequest(BaseModel):
    query: str = Field(..., min_length=1)


class AgentRunResponse(BaseModel):
    answer: str
    tools_used: List[str]
    reasoning_steps: List[str]


class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []


@app.post("/agent/run", response_model=AgentRunResponse)
def agent_run(request: AgentRunRequest):
    query = request.query.strip()
    tools_used, reasoning_steps = plan_agent_run(query)
    tool_results: dict = {}

    for tool in tools_used:
        if tool == "rag_query":
            reasoning_steps.append("Calling RAG /query.")
            tool_results[tool] = rag_query_tool(query)
        elif tool == "image_analyse":
            reasoning_steps.append("Calling Image Analyser /analyse.")
            tool_results[tool] = image_analyse_tool(query)
        elif tool == "fetch_history":
            reasoning_steps.append("Calling Property Triage /history.")
            tool_results[tool] = fetch_property_history_tool()
        elif tool == "triage_issue":
            reasoning_steps.append("Calling Property Triage /triage.")
            tool_results[tool] = triage_new_issue_tool(detect_room_type(query), query)

    answer = synthesize_answer(query, tool_results, reasoning_steps)
    reasoning_steps.append("Agent run complete.")
    return {
        "answer": answer,
        "tools_used": tools_used,
        "reasoning_steps": reasoning_steps,
    }


@app.post("/chat")
def chat_with_agent(request: ChatRequest):
    result = agent_run(AgentRunRequest(query=request.message))
    history = list(request.history)
    history.append({"role": "user", "content": request.message})
    history.append({"role": "assistant", "content": result.answer})
    return {"reply": result.answer, "history": history}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "layer": 3,
        "service": "langgraph_agent",
        "gemini_configured": gemini_client is not None,
        "auth_mode": get_auth_mode() if GEMINI_AVAILABLE else "offline",
    }


@app.on_event("startup")
def startup_diagnostics():
    print("=" * 50)
    print("[LangGraph Agent] Starting")
    if GEMINI_AVAILABLE:
        print(f"[DIAGNOSTIC] Auth mode: {get_auth_mode()}")
        print(f"[DIAGNOSTIC] Setup: {describe_auth_setup()}")
        if gemini_client:
            try:
                test_reply = call_gemini_direct("Respond with only the word: SUCCESS")
                print(f"[DIAGNOSTIC] Gemini OK: {test_reply}")
            except Exception as exc:
                print(f"[DIAGNOSTIC] Gemini unavailable, offline mode. {exc}")
        else:
            print("[DIAGNOSTIC] Gemini client not configured — offline rule-based mode.")
    else:
        print("[DIAGNOSTIC] google-genai not available — offline rule-based mode.")
    print("=" * 50)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)
