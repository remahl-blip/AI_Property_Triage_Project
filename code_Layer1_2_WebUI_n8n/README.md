# AI-Powered Property Triage - WebUI and n8n Orchestration

Layers 1 and 2 for the course project:

- **Layer 1:** Streamlit WebUI (`frontend/app.py`)
- **Layer 2:** n8n orchestration (`orchestration/workflows/property_triage_workflow.json`)

This folder is wired to the existing Layer 3/4 services in the repo root:

| Service | Docker hostname | Endpoint |
|---------|-----------------|----------|
| Image Analyser | `image_analyser` | `POST /analyse` (multipart: `file`, `condition_description`) |
| Property Triage | `property_triage` | `POST /triage`, `GET /history` |

RAG, Guardrails, and LangGraph remain placeholders in the payload metadata.

## Project structure

```text
code_Layer1_2_WebUI_n8n/
|-- Dockerfile
|-- README.md
|-- requirements.txt
|-- .env.example
|-- config/
|   `-- settings.py
|-- frontend/
|   `-- app.py
`-- orchestration/
    |-- n8n_client.py
    |-- n8n_import.sh
    `-- workflows/
        `-- property_triage_workflow.json
```

## Run with the full Docker stack (recommended)

From the repo root:

```bash
docker compose up --build
```

Services:

| UI / tool | URL |
|-----------|-----|
| Layer 1 WebUI (partner) | http://localhost:8502 |
| Layer 3+4 Streamlit UI | http://localhost:8501 |
| n8n editor | http://localhost:5678 |
| Image Analyser docs | http://localhost:8002/docs |
| Property Triage docs | http://localhost:8003/docs |

The `layer1_webui` container posts to `http://n8n:5678/webhook/property-triage`.
The n8n workflow calls `http://image_analyser:8002/analyse` and/or `http://property_triage:8003/triage`.

### First-time n8n workflow check

On first startup, compose imports `property_triage_workflow.json` and activates **Property Triage Orchestration** before n8n starts.

If the webhook returns 404:

1. Open http://localhost:5678
2. Confirm **Property Triage Orchestration** exists and is **Active**
3. If missing, import manually: **Workflows → Import from file** → `orchestration/workflows/property_triage_workflow.json`, then toggle **Active**
4. If import failed on an older volume, reset n8n data: `docker compose down` then `docker volume rm ai_property_triage_project_n8n_data`, then `docker compose up --build`

## Run locally (host Streamlit + Docker backend)

Start backend services only:

```bash
docker compose up --build postgres_db property_triage image_analyser n8n
```

Create env file and run Streamlit on the host:

```bash
cd code_Layer1_2_WebUI_n8n
cp .env.example .env
pip install -r requirements.txt
streamlit run frontend/app.py
```

Use `N8N_WEBHOOK_URL=http://localhost:5678/webhook/property-triage` in `.env`.

## Direct curl tests (bypass WebUI)

**Layer 4:**

```bash
curl -X POST http://localhost:8003/triage \
  -H "Content-Type: application/json" \
  -d "{\"room_type\":\"kitchen\",\"condition_description\":\"severe water leak near the sink\"}"
```

**Layer 3 → 4:**

```bash
curl -X POST http://localhost:8002/analyse \
  -F "file=@kitchen_leak.jpg" \
  -F "condition_description=severe water leak near the sink"
```

**n8n webhook (text-only listing, no image):**

```bash
curl -X POST http://localhost:5678/webhook/property-triage \
  -H "Content-Type: application/json" \
  -d "{\"source\":\"curl-test\",\"listing\":{\"description\":\"severe water leak in kitchen\",\"agent_name\":\"Test Agent\",\"images\":[],\"image_urls\":[]}}"
```

## Integration status

- Connected: Image Analyser, Property Triage (via n8n Code node)
- Pending: RAG, Guardrails, LangGraph (not required for Layers 3+4 demo)
