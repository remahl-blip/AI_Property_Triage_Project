# AI Property Triage Project

Docker stack aligned with the course guideline architecture (Layers 1–4). Offline-first: rule-based engines and optional local Ollama — no cloud API keys required.

## Guideline layer mapping

| Layer | Component | Port | Role |
|-------|-----------|------|------|
| **1** | Partner WebUI (`layer1_webui`) | 8502 | Listing form → n8n webhook |
| **2** | n8n orchestration | 5678 | Webhook → Guardrails → Layer 3 services → Router |
| **3a** | RAG Service (`rag_service`) | 8001 | `POST /query` — similar listings + insight |
| **3b** | Guardrails Service (`guardrails_service`) | 8005 | `POST /check/input`, `POST /check/output` |
| **3c** | LangGraph Agent (`langgraph_agent`) | 8004 | `POST /agent/run` — planner + tool calls |
| **3d** | Image Analyser (`image_analyser`) | 8002 | `POST /analyse` — pixel + metadata analysis |
| **4** | LLM Service (`llm_service`) | 8006 | Ollama-backed extract / agent / report (replaces Gemini/GPT n8n nodes) |
| **Support** | Property Triage (`property_triage`) | 8003 | Maintenance SLA routing + PostgreSQL audit (not Layer 4) |
| **UI** | Streamlit (`frontend_ui`) | 8501 | Direct upload + history dashboard |

Property Triage is a **supporting maintenance service** integrated by Image Analyser and the agent. It is **not** Layer 4 in the guideline sense (Layer 4 = LLM APIs).

## Quick start

```bash
docker compose up --build
```

Then open:

- Partner WebUI (Layer 1): http://localhost:8502
- n8n (Layer 2): http://localhost:5678
- Streamlit UI: http://localhost:8501
- RAG docs: http://localhost:8001/docs
- Image Analyser docs: http://localhost:8002/docs
- LangGraph Agent docs: http://localhost:8004/docs
- Guardrails docs: http://localhost:8005/docs
- LLM Service docs: http://localhost:8006/docs
- Property Triage docs: http://localhost:8003/docs

Optional: run [Ollama](https://ollama.com) on the host for RAG insights and chat (`OLLAMA_URL` defaults to `http://host.docker.internal:11434`).

See `INTEGRATION.md` for curl test checklist and `code_Layer1_2_WebUI_n8n/README.md` for n8n workflow import.

## n8n pipeline (Layer 2)

`property_triage_workflow.json` implements the full guideline flow:

1. **Webhook** — form POST from WebUI
2. **Guardrails input** — `POST /check/input`
3. **IF pass** — reject or continue
4. **Info Extractor** — `llm_service:8006/extract` (Ollama)
5. **RAG Query** — `rag_service:8001/query` (LangChain + ChromaDB)
6. **LangGraph Agent** — `langgraph_agent:8004/agent/run`
7. **Image Analyser** — Code node → `image_analyser:8002/analyse`
8. **AI Agent Enrich** — `llm_service:8006/agent`
9. **LLM Chain Report** — `llm_service:8006/report`
10. **Guardrails output** — `POST /check/output`
11. **Router** — residential vs commercial
12. **Success Response** — JSON with `report_markdown`

## Project structure

```text
code_Layer1_2_WebUI_n8n/  # Layers 1 + 2 (WebUI + n8n workflows)
code_RAG_Service/         # Layer 3 — RAG
code_Guardrails_Service/  # Layer 3 — Guardrails
code_LangGraph_Agent/     # Layer 3 — Agent
code_Image_Analyser/      # Layer 3 — Image analysis
code_LLM_Service/         # Layer 4 — Ollama extract/agent/report for n8n
code_Property_Triage/     # Support — maintenance triage + DB
code_Frontend_UI/         # Streamlit UI
docker-compose.yml
docs/                     # Prompt logs, DEPLOYMENT.md, SUBMISSION.md
demo/                     # Demo video guide
INTEGRATION.md
tests/
```

## Local tests

```bash
docker compose run --rm --no-deps -v "%cd%:/workspace" guardrails_service sh -c "pip install -q Pillow && cd /workspace && PYTHONPATH=code_Guardrails_Service:code_Image_Analyser python -m unittest tests.test_layer3_services -v"
python code_RAG_Service/populate_index.py
```
