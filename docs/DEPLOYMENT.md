# Deployment Notes

## Local development (this repository)

All four guideline Layer 3 microservices run via **Docker Compose** on the developer machine instead of separate AWS EC2 instances. This satisfies the architecture for development and demo; production deployment follows the same containers on EC2.

| Service | Container | Port | EC2 equivalent |
|---------|-----------|------|----------------|
| RAG | `rag_service` | 8001 | t3.large, 8001 |
| Image Analyser | `image_analyser` | 8002 | t3.medium, 8002 |
| Property Triage (support) | `property_triage` | 8003 | t3.small, 8003 |
| LangGraph Agent | `langgraph_agent` | 8004 | t3.large, 8004 |
| Guardrails | `guardrails_service` | 8005 | t3.small, 8005 |
| LLM helper (Ollama substitute) | `llm_service` | 8006 | n8n LM nodes |
| n8n | `n8n` | 5678 | n8n.cloud or EC2 |
| WebUI (partner) | `layer1_webui` | 8502 | localhost |
| Streamlit UI | `frontend_ui` | 8501 | localhost |

## Prerequisites

- Docker Desktop
- Python 3.10+ (optional, for local unit tests)
- [Ollama](https://ollama.com) on host: `ollama pull llama3`

## Start stack

```powershell
cd C:\Users\rema7\Desktop\AI_Property_Triage_Project
docker compose up --build
```

First build may take 15–30 minutes (ChromaDB embeddings + PyTorch model training in Image Analyser image).

## EC2 deployment checklist

1. Launch Ubuntu EC2 (t3.large recommended for RAG + LangGraph).
2. Install Docker: `sudo apt-get update && sudo apt-get install -y docker.io`
3. Clone repo and run `docker compose up -d` per service or full stack.
4. Security group: allow inbound **only** from n8n IP and your dev machine (not `0.0.0.0/0`).
5. Set `OLLAMA_URL` to host Ollama or skip for rule-based fallbacks.
6. Update n8n HTTP node URLs from `http://rag_service:8001` to `http://<EC2_PUBLIC_IP>:8001`.

## Deviations from guideline

| Guideline | Our implementation |
|-----------|-------------------|
| Gemini / GPT-4o in n8n | `llm_service` with local Ollama + rule/template fallbacks |
| Llama.cpp in RAG | ChromaDB + HuggingFace embeddings; Ollama for insight generation |
| NeMo Guardrails runtime | Rule engine + YAML rail configs (NeMo-compatible prompts) |
| 200 real labelled images | 240 synthetic images for ResNet-18 fine-tuning (documented) |
| Separate EC2 per service | Single Docker network locally; can split to multiple EC2 |

## n8n workflow reset

If the workflow does not update after JSON changes:

```powershell
docker compose down
docker volume rm ai_property_triage_project_n8n_data
docker compose up --build
```
