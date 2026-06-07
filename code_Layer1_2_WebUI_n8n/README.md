# AI-Powered Property Triage - WebUI and n8n Orchestration

This repository currently implements only the assigned project responsibilities:

- Layer 1: Streamlit WebUI
- Layer 2: n8n orchestration integration

The EC2 microservices and external LLM services are intentionally not implemented here. Their future integration points are represented as TODO-marked placeholders in the n8n payload.

## Project Structure

```text
CV_Project/
|-- ARCHITECTURE.md
|-- README.md
|-- requirements.txt
|-- .env.example
|-- config/
|   |-- __init__.py
|   `-- settings.py
|-- frontend/
|   |-- __init__.py
|   `-- app.py
`-- orchestration/
    |-- __init__.py
    `-- n8n_client.py
```

## Setup

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create your local environment file:

```bash
cp .env.example .env
```

Update `.env` with your n8n webhook URL:

```bash
N8N_WEBHOOK_URL=http://localhost:5678/webhook/property-triage
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
REQUEST_TIMEOUT_SECONDS=30
```

## Run

Start Ollama separately if you want to use the assistant:

```bash
ollama pull llama3
ollama serve
```

Run the Streamlit app:

```bash
streamlit run frontend/app.py
```

## What to Test First

1. Open the app and confirm both tabs render.
2. In the Assistant tab, ask a real estate listing question and confirm Ollama responds.
3. In the Submit Listing tab, enter an agent name, listing description, and one image.
4. Submit with no n8n server running and confirm the app shows a clean connection error.
5. Point `N8N_WEBHOOK_URL` to a test webhook and confirm the JSON payload arrives.

## Integration TODOs

- TODO: Connect n8n to the teammate Guardrails service for input and output checks.
- TODO: Connect n8n to the teammate RAG service for similar listing retrieval.
- TODO: Connect n8n to the teammate Image Analyzer service once its final image contract is available.
- TODO: Connect n8n to the teammate LangGraph Agent for multi-step listing questions.
- TODO: Replace placeholder payload fields with final schemas after the team locks service contracts.
