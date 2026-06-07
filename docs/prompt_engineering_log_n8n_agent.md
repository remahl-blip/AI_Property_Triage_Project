# Prompt Engineering Log — Surface #2: n8n AI Agent (Ollama substitute)

**Component:** `code_LLM_Service` → `POST /agent` + LangGraph `POST /agent/run`  
**Role:** Senior property analyst merging RAG + image outputs

## Version 1 — Baseline
"Analyze the listing."
**Failure:** Generic advice, ignored image scores.

## Version 2
Added structured JSON output keys: summary, recommended_actions, risk_flags, confidence.
**Failure:** Invented legal recommendations.

## Version 3
Added: "Do not invent prices or legal claims; use only provided data."
**Improved:** Safer outputs; tool selection still random in n8n.

## Version 4
LangGraph tool descriptions clarified: RAG for search, Image for condition.
**Improved:** Correct tool routing in 8/10 benchmark queries.

## Version 5 — Final
```text
Senior property analyst. JSON: summary, recommended_actions, risk_flags, confidence.
Base answer ONLY on extracted fields, RAG insight, and image analysis provided.
```
**Pass rate:** 8/10 benchmark queries. Offline template fallback when Ollama times out.
