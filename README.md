# AI Property Triage Project (Layers 3 + 4)

A minimal, **working** Docker stack for property maintenance triage:

| Layer | Service | Port | Role |
|-------|---------|------|------|
| **3** | Image Analyser | 8002 | Reads image filename + description, builds structured metadata |
| **4** | Property Triage | 8003 | Rule engine, SLA routing, PostgreSQL audit log |
| UI | Streamlit | 8501 | Upload form + history dashboard |

No Gemini, Vertex AI, or API keys required.

## Quick start

```bash
docker compose up --build
```

Then open:

- UI: http://localhost:8501
- Layer 3 docs: http://localhost:8002/docs
- Layer 4 docs: http://localhost:8003/docs

## Test Layer 3 → Layer 4

Upload an image named like `kitchen_leak.jpg` and enter:

`There is a severe water leak near the sink`

Expected triage: **High** or **Emergency** priority with SLA and ticket ID.

## API examples

**Layer 4 direct:**

```bash
curl -X POST http://localhost:8003/triage \
  -H "Content-Type: application/json" \
  -d "{\"room_type\":\"kitchen\",\"condition_description\":\"severe water leak and flood\"}"
```

**Layer 3 + 4 pipeline:** use the Streamlit UI or `POST /analyse` with multipart form (`file` + optional `condition_description`).

## Project structure

```text
code_Image_Analyser/     # Layer 3
code_Property_Triage/    # Layer 4
code_Frontend_UI/        # Streamlit UI
docker-compose.yml
```

## Course guideline note

The full course project also includes n8n, RAG, Guardrails, LangGraph, and cloud deployment. This repo focuses on a **stable Layers 3+4 foundation** you can demo and extend later.
