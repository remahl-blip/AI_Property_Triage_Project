# Architecture — AI Property Triage System

Annotated design for this repository (local Docker deployment).

## Layer 1 — User Interface

| Component | URL | Technology |
|-----------|-----|------------|
| Partner WebUI | `:8502` | Streamlit — listing form + Ollama chat |
| Streamlit UI | `:8501` | Streamlit — triage demo, Hebrew search, apartment chat |

**Design decision:** Two UIs share the same backend; partner folder satisfies Layer 1+2 coursework structure.

## Layer 2 — n8n Orchestration

| Component | URL |
|-----------|-----|
| n8n | `:5678` |

Workflow: `code_Layer1_2_WebUI_n8n/orchestration/workflows/property_triage_workflow.json`

**Design decision:** Gemini/GPT nodes replaced by HTTP calls to `llm_service` (Ollama) — no cloud API keys.

## Layer 3 — Microservices (FastAPI + Docker)

```
                    ┌─────────────────┐
   n8n webhook ───► │ guardrails :8005│
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   llm_service :8006    rag_service :8001   langgraph :8004
         │                   │                   │
         └─────────┬─────────┴─────────┬─────────┘
                   ▼                   ▼
            image_analyser :8002   property_triage :8003 (support)
```

| Service | Stack | Endpoint |
|---------|-------|----------|
| RAG | LangChain, ChromaDB, HuggingFace embeddings, Ollama insight | `POST /query` |
| Image Analyser | PyTorch ResNet-18, PIL fallback | `POST /analyse` |
| Guardrails | Rule engine + YAML rails | `POST /check/input`, `/check/output` |
| LangGraph | StateGraph planner→tools→synthesizer | `POST /agent/run` |

## Layer 4 — LLM Runtime

| Runtime | Used by |
|---------|---------|
| Ollama `llama3` (host) | WebUI chat, RAG insight, llm_service |
| Rule/template fallbacks | All Layer 4 paths when Ollama unavailable |

## Data

- `code_RAG_Service/data/listings.json` — 24 synthetic listings (ChromaDB index)
- `code_Frontend_UI/listings.json` — synced copy for search/chat
- PostgreSQL — Property Triage audit tickets

## Security

- EC2 security groups should restrict ports to n8n IP only (see `DEPLOYMENT.md`).
- No API keys committed; Ollama runs on developer host.
