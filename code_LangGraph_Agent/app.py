import os
import io
import json
from typing import Annotated, TypedDict, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from dotenv import load_dotenv

load_dotenv()
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

app = FastAPI(title="Property Compliance & Triage Operations AI")

def get_sanitized_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        paths = ['.env', '../.env', '../../.env', '/app/.env']
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, 'r') as f:
                        for line in f:
                            if line.strip().startswith("GEMINI_API_KEY"):
                                parts = line.split("=", 1)
                                if len(parts) > 1:
                                    key = parts[1].strip()
                                    break
                except Exception:
                    pass
            if key:
                break
    if key:
        key = key.replace('"', '').replace("'", "").strip()
        key = "".join(key.split())
    return key

GEMINI_API_KEY = get_sanitized_api_key()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

def parse_json_from_model_reply(reply: str) -> dict:
    clean = reply.strip()
    if clean.startswith("```"):
        clean = clean.removeprefix("```json").removeprefix("```").strip()
        if clean.endswith("```"):
            clean = clean[:-3].strip()
    return json.loads(clean)

def call_gemini_direct(prompt: str, system_instruction: str = None) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is empty or missing")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": ""
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [
                {"text": system_instruction}
            ]
        }
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    if response.status_code == 200:
        res_data = response.json()
        try:
            return res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            raise ValueError(f"Unexpected response structure: {res_data}")
    else:
        raise ValueError(f"Status {response.status_code}: {response.text}")

print("\n" + "="*50)
print("[DIAGNOSTIC] Starting Gemini API Connection Test...")
if GEMINI_API_KEY:
    masked = f"{GEMINI_API_KEY[:6]}...{GEMINI_API_KEY[-4:]}"
    print(f"[DIAGNOSTIC] Sanitized Key: {masked} (Length: {len(GEMINI_API_KEY)})")
    try:
        test_reply = call_gemini_direct("Respond with only the word: SUCCESS")
        print(f"[DIAGNOSTIC] TEST RESULT: Connection successful! Gemini responded: {test_reply}")
    except Exception as e:
        print(f"[DIAGNOSTIC] TEST RESULT: Failed to connect to Gemini API. Error details:")
        print(f"             {e}")
else:
    print("[DIAGNOSTIC] TEST RESULT: Failed. GEMINI_API_KEY is empty!")
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
        state["next_step"] = "respond"
        state["messages"].append({
            "role": "assistant",
            "content": f"סליחה, נתקלתי בקושי בניתוח הבקשה שלך. שגיאה: {e}"
        })
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
        state["messages"].append({"role": "assistant", "content": f"הפעולה בוצעה בהצלחה, אך נכשלה יצירת הסיכום: {e}"})
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