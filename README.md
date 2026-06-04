```markdown
# AI Property Triage Project 🏢🤖

An automated, microservices-based system designed to streamline property maintenance management using AI and rule-based decision engines. This repository contains the core analytical and triage layers of the application ecosystem.

## Architecture & Layers Overview 📐

The project focuses on processing, analyzing, and triaging property issues through dedicated microservices managed via Docker containers, representing the core intelligence layers:

1. **Layer 3: Image Analyser (`port 8002`)** A FastAPI service that handles the visual analysis stage. It is designed to utilize the Hugging Face `Salesforce/blip-image-captioning-large` model to generate descriptive image captions and detect room types. To counter local network or DNS restrictions, it includes an advanced offline robust fallback mechanism that securely processes metadata without crashing.
   
2. **Layer 4: Property Triage (RAG / Rule Engine) (`port 8003`)** A FastAPI service acting as the decision-making engine. It receives the structural metadata and descriptions compiled by Layer 3 (or via automated workflows). By checking inputs against a specialized property maintenance knowledge base, it scans for critical hazard keywords (e.g., flood, leak, mold, fire, gas) to classify the ticket's severity (`Emergency`, `Medium`, `Low`) and generates actionable dispatch instructions.

---

## Project Structure 📁

```text
AI_Property_Triage_Project/
├── code_Image_Analyser/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── code_Property_Triage/
│   ├── triage_service.py
│   ├── Dockerfile
│   └── requirements.txt
└── docker-compose.yml

```

---

## Quick Start 🚀

### 1. Prerequisites

Make sure you have the following running on your machine:

* **Docker Desktop**

### 2. Up and Running

To spin up both Layer 3 and Layer 4 simultaneously with their internal networking isolated and configured, open your terminal in the project root directory (`AI_Property_Triage_Project`) and run:

```bash
docker compose up --build

```

Docker will pull the official Python environment, install necessary dependencies (`FastAPI`, `Uvicorn`, `requests`, and `python-multipart` for Python 3.14+ compatibility), handle port binding, and attach the log streams.

---

## API Documentation & Endpoint Testing 🌐

With the containers active, you can access the interactive Swagger UIs to inspect and test the layers independently:

* **Layer 3 (Image Analyser Dashboard):** [http://localhost:8002/docs](https://www.google.com/search?q=http://localhost:8002/docs)
* **Layer 4 (Property Triage Dashboard):** [http://localhost:8003/docs](https://www.google.com/search?q=http://localhost:8003/docs)

### Testing Layer 3 (`POST /analyse`)

* Form Data: Upload any image file (`.jpg`, `.png`).
* *Robustness Check:* If outbound internet calls to Hugging Face are blocked by local firewalls/proxies, the offline fallback safely takes over and infers context straight from the filename structure (e.g., uploading `kitchen_leak.jpg` gracefully falls back to identifying a `kitchen` environment with a `200 OK` status).

### Testing Layer 4 (`POST /triage`)

Send a JSON payload simulating compiled data:

```json
{
  "room_type": "kitchen",
  "condition_description": "There is a severe water leak near the sink and it is causing a flood"
}

```

**Response Output:**

```json
{
  "priority": "Emergency",
  "action_required": "Dispatch emergency plumber/technician immediately and shut off main valves.",
  "summary": "CRITICAL: Emergency detected in kitchen based on description keywords."
}

```

---

## Workflow Integration 🔗

These layers are decoupled and optimized to sit inside an automated pipeline (e.g., driven by upstream automation or n8n nodes):

1. **Trigger / Entry Layers (Layers 1 & 2):** Handle incoming communication channels, ingest user reports, and routes data forward.
2. **Layer 3 Integration:** n8n passes the gathered image binary to `http://localhost:8002/analyse`.
3. **Layer 4 Integration:** The parsed results flow straight into `http://localhost:8003/triage` where the final severity routing is determined, triggering conditional downstream actions (e.g., immediate SMS dispatches for emergencies).

```
