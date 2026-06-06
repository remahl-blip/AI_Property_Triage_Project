import os
import json
from typing import TypedDict, List
from fastapi import FastAPI
from pydantic import BaseModel
import requests
from google.genai import types
from dotenv import load_dotenv
from gemini_config import (
    create_gemini_client_safe,
    describe_auth_setup,
    get_auth_mode,
    get_gemini_model,
)

load_dotenv()
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

app = FastAPI(title="Property Compliance & Triage Operations AI")

GEMINI_MODEL = get_gemini_model()
gemini_client = create_gemini_client_safe()

def parse_json_from_model_reply(reply: str) -> dict:
    clean = reply.strip()
    if clean.startswith("```"):
        clean = clean.removeprefix("```json").removeprefix("```").strip()
        if clean.endswith("```"):
            clean = clean[:-3].strip()
    return json.loads(clean)

def call_gemini_direct(prompt: str, system_instruction: str = None) -> str:
    if not gemini_client:
        if get_auth_mode() == "vertex_ai":
            raise ValueError(
                "Vertex AI is enabled but not configured. Set GOOGLE_CLOUD_PROJECT and "
                "mount a service-account JSON at GOOGLE_APPLICATION_CREDENTIALS."
            )
        raise ValueError("GEMINI_API_KEY is empty or missing")

    config = None
    if system_instruction:
        config = types.GenerateContentConfig(system_instruction=system_instruction)

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=config,
    )
    if not response or not response.text:
        raise ValueError("Empty response from Gemini API")
    return response.text.strip()

HISTORY_KEYWORDS = (
    "history", "ticket", "tickets", "past", "previous", "report", "reports",
    "היסטוריה", "כרטיס", "כרטיסים", "דיווח", "דיווחים", "דוחות",
)
ISSUE_KEYWORDS = (
    "leak", "broken", "issue", "problem", "flood", "mold", "fire", "repair",
    "נזילה", "שבור", "תקלה", "בעיה", "הצפה", "עובש", "תיקון",
)
ROOM_KEYWORDS = {
    "kitchen": ("kitchen", "מטבח"),
    "bathroom": ("bathroom", "שירותים", "אמבטיה"),
    "bedroom": ("bedroom", "חדר שינה"),
    "living room": ("living room", "סלון"),
    "hallway": ("hallway", "מסדרון"),
}

def detect_room_type(text: str) -> str:
    lowered = text.lower()
    for room, keywords in ROOM_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return room
    return "unknown"

def wants_history_lookup(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in HISTORY_KEYWORDS)

def wants_new_issue(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ISSUE_KEYWORDS)

def summarize_history_offline(raw_history: str) -> str:
    try:
        records = json.loads(raw_history)
    except json.JSONDecodeError:
        return raw_history

    if not records:
        return "אין עדיין דיווחים שמורים במערכת."

    lines = ["סיכום דיווחים אחרונים:"]
    for record in records[:5]:
        lines.append(
            f"- {record.get('ticket_id', 'N/A')}: {record.get('room_type', 'unknown')} | "
            f"{record.get('priority', 'N/A')} | {record.get('compliance_status', 'N/A')}"
        )
    if len(records) > 5:
        lines.append(f"... ועוד {len(records) - 5} דיווחים נוספים.")
    return "\n".join(lines)

def summarize_triage_offline(raw_triage: str) -> str:
    try:
        record = json.loads(raw_triage)
    except json.JSONDecodeError:
        return f"הדיווח נשמר. פרטים: {raw_triage}"

    audit = record.get("audit_report", {})
    return (
        "הדיווח נשמר בהצלחה.\n"
        f"מספר כרטיס: {audit.get('ticket_id', 'N/A')}\n"
        f"עדיפות: {record.get('priority', 'N/A')}\n"
        f"סטטוס: {audit.get('compliance_status', 'N/A')}\n"
        f"SLA: {audit.get('sla_deadline', 'N/A')}"
    )

def offline_agent_decision(user_query: str) -> dict:
    if wants_history_lookup(user_query):
        return {"next_step": "call_fetch_history", "tool_output": ""}

    if wants_new_issue(user_query):
        return {
            "next_step": "call_triage_issue",
            "tool_output": json.dumps({
                "action": "triage_issue",
                "room_type": detect_room_type(user_query),
                "description": user_query,
            }),
        }

    return {
        "next_step": "respond",
        "reply": (
            "שלום! כרגע חיבור Gemini לא זמין (מפתחות AQ חדשים או Vertex AI לא מוגדרים).\n"
            "אפשר עדיין לנסות: 'הצג היסטוריית דיווחים' או לתאר תקלה חדשה, למשל 'נזילה במטבח'."
        ),
    }

print("\n" + "="*50)
print("[DIAGNOSTIC] Starting Gemini Connection Test...")
print(f"[DIAGNOSTIC] Auth mode: {get_auth_mode()}")
print(f"[DIAGNOSTIC] Setup: {describe_auth_setup()}")
if gemini_client:
    try:
        test_reply = call_gemini_direct("Respond with only the word: SUCCESS")
        print(f"[DIAGNOSTIC] TEST RESULT: Connection successful! Gemini responded: {test_reply}")
    except Exception as e:
        print("[DIAGNOSTIC] TEST RESULT: Failed to connect to Gemini.")
        print(f"             {e}")
else:
    print("[DIAGNOSTIC] TEST RESULT: Gemini client not configured.")
print("="*50 + "\n")

TRIAGE_SERVICE_URL = "http://property_triage:8003"

def fetch_property_history_tool() -> str:
    try:
        response = requests.get(f"{TRIAGE_SERVICE_URL}/history", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if not data:
                return "No property issues recorded in the database yet."
            return json.dumps(data, indent=2, ensure_ascii=False)
        return f"Error fetching history: status code {response.status_code}"
    except Exception as e:
        return f"Failed to connect to database service: {e}"

def triage_new_issue_tool(room_type: str, description: str) -> str:
    try:
        payload = {
            "room_type": room_type,
            "condition_description": description
        }
        response = requests.post(f"{TRIAGE_SERVICE_URL}/triage", json=payload, timeout=5)
        if response.status_code == 200:
            return json.dumps(response.json(), indent=2, ensure_ascii=False)
        return f"Error evaluating triage: {response.text}"
    except Exception as e:
        return f"Failed to connect to triage service: {e}"

class AgentState(TypedDict):
    messages: List[dict]
    next_step: str
    tool_output: str

def agent_decision_node(state: AgentState) -> AgentState:
    user_query = state["messages"][-1]["content"]
    system_instruction = (
        "You are an intelligent Property Operations Agent.\n"
        "You help property managers manage, analyze and log repair tasks.\n"
        "You have access to two tools:\n"
        "1. fetch_property_history_tool: Use this when the user asks about past tickets, reports, statistics, or existing issues.\n"
        "2. triage_new_issue_tool: Use this ONLY when the user is reporting a brand new maintenance issue to be logged and analyzed.\n\n"
        "If you need to use a tool, reply STRICTLY with one of the following JSON formats (do not include markdown wrapping):\n"
        '{"action": "fetch_history"}\n'
        "or\n"
        '{"action": "triage_issue", "room_type": "ROOM_NAME", "description": "DETAILED_DESCRIPTION"}\n\n'
        "If you do not need any tools, reply with a natural, friendly, helpful message in Hebrew."
    )
    try:
        reply = call_gemini_direct(user_query, system_instruction)
        try:
            tool_call = parse_json_from_model_reply(reply)
            if not isinstance(tool_call, dict) or "action" not in tool_call:
                raise ValueError("not a tool call")
            action = tool_call.get("action")
            if action == "fetch_history":
                state["next_step"] = "call_fetch_history"
            elif action == "triage_issue":
                state["next_step"] = "call_triage_issue"
                state["tool_output"] = json.dumps(tool_call)
            else:
                state["next_step"] = "respond"
                state["messages"].append({"role": "assistant", "content": reply})
        except (json.JSONDecodeError, ValueError):
            state["next_step"] = "respond"
            state["messages"].append({"role": "assistant", "content": reply})
    except Exception as e:
        print(f"[FALLBACK] Gemini unavailable, using rule-based agent. Error: {e}")
        fallback = offline_agent_decision(user_query)
        state["next_step"] = fallback["next_step"]
        state["tool_output"] = fallback.get("tool_output", "")
        if fallback["next_step"] == "respond":
            state["messages"].append({"role": "assistant", "content": fallback["reply"]})
    return state

def tool_execution_node(state: AgentState) -> AgentState:
    next_step = state["next_step"]
    if next_step == "call_fetch_history":
        result = fetch_property_history_tool()
        summary_prompt = (
            f"Here is the raw database history of property tickets:\n{result}\n\n"
            f"Please summarize this data nicely for the user in professional Hebrew. Highlight emergency or high priority tickets."
        )
    elif next_step == "call_triage_issue":
        tool_params = json.loads(state["tool_output"])
        result = triage_new_issue_tool(
            room_type=tool_params.get("room_type", "unknown"),
            description=tool_params.get("description", "")
        )
        summary_prompt = (
            f"A new issue was successfully logged and evaluated:\n{result}\n\n"
            f"Please write a concise success summary to the user in friendly Hebrew, including Ticket ID, Priority, and SLA Deadline."
        )
    else:
        return state
    try:
        reply = call_gemini_direct(summary_prompt)
        state["messages"].append({"role": "assistant", "content": reply})
    except Exception as e:
        print(f"[FALLBACK] Gemini summary unavailable. Error: {e}")
        if next_step == "call_fetch_history":
            reply = summarize_history_offline(result)
        else:
            reply = summarize_triage_offline(result)
        state["messages"].append({"role": "assistant", "content": reply})
    state["next_step"] = "respond"
    return state

class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []

@app.post("/chat")
def chat_with_agent(request: ChatRequest):
    messages = []
    for msg in request.history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": request.message})
    state = {
        "messages": messages,
        "next_step": "decision",
        "tool_output": ""
    }
    state = agent_decision_node(state)
    if state["next_step"] in ["call_fetch_history", "call_triage_issue"]:
        state = tool_execution_node(state)
    return {
        "reply": state["messages"][-1]["content"],
        "history": state["messages"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
