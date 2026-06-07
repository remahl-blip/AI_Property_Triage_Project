"""LangGraph StateGraph: planner → tool execution → synthesizer."""

import json
import operator
from typing import Annotated, TypedDict

import requests
from langgraph.graph import END, StateGraph

RAG_URL = None
IMAGE_URL = None


def configure(rag_url: str, image_url: str):
    global RAG_URL, IMAGE_URL
    RAG_URL = rag_url
    IMAGE_URL = image_url


class AgentState(TypedDict):
    query: str
    plan: list[str]
    tool_results: dict
    reasoning_steps: Annotated[list[str], operator.add]
    answer: str


def planner_node(state: AgentState) -> dict:
    query = state["query"].lower()
    tools = []
    steps = ["Planner: analyze query and select tools."]
    search_kw = ("find", "search", "similar", "דירה", "נכס", "apartment", "rent", "sale")
    image_kw = ("image", "photo", "תמונה", "leak", "נזילה", "repair", "תיקון")
    if any(k in query for k in search_kw):
        tools.append("rag_query")
        steps.append("Plan: call RAG /query for similar listings.")
    if any(k in query for k in image_kw):
        tools.append("image_analyse")
        steps.append("Plan: call Image Analyser /analyse.")
    if not tools:
        tools = ["rag_query"]
        steps.append("Plan: default to RAG /query.")
    return {"plan": tools, "reasoning_steps": steps}


def tool_node(state: AgentState) -> dict:
    results = {}
    steps = []
    for tool in state["plan"]:
        if tool == "rag_query":
            steps.append("Tool: POST RAG /query")
            try:
                r = requests.post(f"{RAG_URL}/query", json={"description": state["query"]}, timeout=20)
                results[tool] = r.json() if r.ok else {"error": r.text}
            except Exception as exc:
                results[tool] = {"error": str(exc)}
        elif tool == "image_analyse":
            steps.append("Tool: POST Image Analyser /analyse")
            try:
                r = requests.post(
                    f"{IMAGE_URL}/analyse",
                    json={"condition_description": state["query"], "filename": "query.jpg"},
                    timeout=20,
                )
                results[tool] = r.json() if r.ok else {"error": r.text}
            except Exception as exc:
                results[tool] = {"error": str(exc)}
    return {"tool_results": results, "reasoning_steps": steps}


def synthesizer_node(state: AgentState) -> dict:
    parts = []
    rag = state.get("tool_results", {}).get("rag_query", {})
    if rag.get("insight"):
        parts.append(rag["insight"])
    img = state.get("tool_results", {}).get("image_analyse", {})
    if img.get("room_type"):
        parts.append(
            f"ניתוח תמונה: {img.get('room_type')}, ציון {img.get('condition_score', 'N/A')}/5."
        )
    answer = " ".join(parts) if parts else "לא נמצאו תוצאות רלוונטיות."
    return {
        "answer": answer,
        "reasoning_steps": ["Synthesizer: merged tool outputs into final answer."],
    }


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("tools", tool_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.set_entry_point("planner")
    graph.add_edge("planner", "tools")
    graph.add_edge("tools", "synthesizer")
    graph.add_edge("synthesizer", END)
    return graph.compile()


_compiled = None


def run_agent(query: str) -> dict:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    result = _compiled.invoke({
        "query": query,
        "plan": [],
        "tool_results": {},
        "reasoning_steps": [],
        "answer": "",
    })
    tools_used = result.get("plan", [])
    return {
        "answer": result.get("answer", ""),
        "tools_used": tools_used,
        "reasoning_steps": result.get("reasoning_steps", []),
    }
