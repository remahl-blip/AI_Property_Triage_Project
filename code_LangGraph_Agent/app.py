import os

import requests
from fastapi import FastAPI
from pydantic import BaseModel, Field

from agent_graph import configure, run_agent

app = FastAPI(title="LangGraph Agent (Layer 3)")

RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://rag_service:8001")
IMAGE_ANALYSER_URL = os.getenv("IMAGE_ANALYSER_URL", "http://image_analyser:8002")

configure(RAG_SERVICE_URL, IMAGE_ANALYSER_URL)


class AgentRunRequest(BaseModel):
    query: str = Field(..., min_length=1)


class AgentRunResponse(BaseModel):
    answer: str
    tools_used: list[str]
    reasoning_steps: list[str]


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.on_event("startup")
def startup():
    print("[LangGraph Agent] StateGraph ready (planner → tools → synthesizer).")


@app.post("/agent/run", response_model=AgentRunResponse)
def agent_run(request: AgentRunRequest):
    return run_agent(request.query.strip())


@app.post("/chat")
def chat_with_agent(request: ChatRequest):
    result = run_agent(request.message)
    history = list(request.history)
    history.append({"role": "user", "content": request.message})
    history.append({"role": "assistant", "content": result["answer"]})
    return {"reply": result["answer"], "history": history}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "layer": 3,
        "service": "langgraph_agent",
        "graph": "StateGraph(planner→tools→synthesizer)",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)
