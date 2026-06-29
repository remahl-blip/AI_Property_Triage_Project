# AI Property Triage — AI-Native Real Estate Listing Processor

> **An end-to-end AI system that ingests Hebrew/English property listings, runs automated guardrails, extracts structured fields, retrieves similar listings via vector search, analyses property condition from images or text, reasons with a LangGraph agent, and returns a full Listing Brief report — all orchestrated by n8n and powered by local Ollama with rule-based fallbacks (no cloud API keys required).**

---

## Table of Contents

1. [What is this project?](#1-what-is-this-project)
2. [System Architecture — The 4 Layers](#2-system-architecture--the-4-layers)
3. [Layer 1 — Web UI (Streamlit)](#3-layer-1--web-ui-streamlit)
4. [Layer 2 — n8n Orchestration](#4-layer-2--n8n-orchestration)
5. [Layer 3 — AWS EC2 Python Microservices](#5-layer-3--aws-ec2-python-microservices)
6. [Layer 4 — LLM Service (Ollama substitute)](#6-layer-4--llm-service-ollama-substitute)
7. [The Full Listing Pipeline (Step by Step)](#7-the-full-listing-pipeline-step-by-step)
8. [Apartment Chat Assistant](#8-apartment-chat-assistant)
9. [Decision Tree — Residential vs Commercial Router](#9-decision-tree--residential-vs-commercial-router)
10. [Technologies Used](#10-technologies-used)
11. [Listings Dataset](#11-listings-dataset)
12. [Prompt Engineering Logs](#12-prompt-engineering-logs)
13. [How to Run the Project](#13-how-to-run-the-project)
14. [Verification & Grading Rubric](#14-verification--grading-rubric)
15. [Repository Structure](#15-repository-structure)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. What is this project?

**AI Property Triage** is an AI-powered property listing platform designed for real-estate agents who need to process, validate, and enrich listing descriptions quickly and safely.

### The Problem It Solves

Listing agents receive unstructured property descriptions (Hebrew or English) that may contain spam, missing fields, or unsafe claims. Manually finding comparable listings, assessing condition, and writing a professional brief is slow and inconsistent.

### What the System Does

1. **Accepts** a property listing description (and optional images) via a WebUI form
2. **Guards** the input — rejects spam, off-topic text, and promotional content
3. **Extracts** structured fields (city, rooms, price, features) using the LLM service
4. **Retrieves** the 3 most similar listings from a 26-property corpus using vector search (RAG)
5. **Reasons** about the listing using a LangGraph agent with tool calls to RAG and Image Analyser
6. **Analyses** property condition from uploaded images or metadata-only descriptions
7. **Generates** a Markdown Listing Brief report via the LLM service
8. **Guards** the output — blocks invented legal guarantees and fabricated permits
9. **Routes** the result to residential or commercial workflow paths
10. **Answers questions** about available listings through a built-in Hebrew apartment chat assistant

### Key Capabilities

| Capability | Description |
|---|---|
| Listing Submission | Upload description + images, get a full Listing Brief |
| Similar Listings | RAG returns top-3 matches with IDs, prices, and Hebrew insight |
| Input Guardrails | Spam and off-topic submissions rejected before processing |
| Output Guardrails | Unsafe claims (guaranteed returns, fake permits) flagged or removed |
| Image Analysis | ResNet-18 room classification + condition score 1–5 (95.83% test accuracy) |
| Maintenance Triage | Property Triage service creates SLA tickets for severe issues |
| Apartment Chat | Hebrew assistant grounded in `listings.json` — refuses off-topic queries |
| Offline Mode | Rule-based fallbacks when Ollama is unavailable (verified on EC2) |

---

## 2. System Architecture — The 4 Layers

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 1 — Web UI (Streamlit)                         │
│  :8501 Chat & Search  ·  :8502 Submit Listing + Assist  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP POST (webhook / chat)
┌──────────────────────▼──────────────────────────────────┐
│  LAYER 2 — n8n Orchestration (:5678)                      │
│  Webhook → Guardrails → Extract → RAG → Agent → Image   │
│  → LLM Report → Guardrails Output → Router → Response    │
└──┬───────────────┬──────────────────┬───────────────────┘
   │               │                  │
┌──▼──────┐  ┌─────▼──────┐  ┌───────▼────────┐  ┌──────────────────┐
│ RAG     │  │ Image      │  │ LangGraph      │  │ Guardrails       │
│ Service │  │ Analyser   │  │ Agent          │  │ Service          │
│ :8001   │  │ :8002      │  │ :8004          │  │ :8005            │
│ChromaDB │  │ResNet-18   │  │StateGraph      │  │Input/Output rails│
└─────────┘  └────────────┘  └────────────────┘  └──────────────────┘
   LAYER 3 — Python Microservices (FastAPI + Docker)
┌─────────────────────────────────────────────────────────┐
│  LAYER 4 — LLM Service (:8006)                          │
│  Local Ollama (llama3) · Rule-based extract/agent/report│
└─────────────────────────────────────────────────────────┘
```

Each layer communicates only via HTTP REST APIs inside a Docker network. Any service can be replaced, scaled, or deployed to a separate EC2 instance independently.

**Support service (not Layer 4):** `property_triage` (:8003) — PostgreSQL-backed maintenance SLA routing, called by Image Analyser.

---

## 3. Layer 1 — Web UI (Streamlit)

**Technology:** Streamlit (Python)  
**Locations:** `code_Frontend_UI/` · `code_Layer1_2_WebUI_n8n/frontend/`  
**Ports:** `localhost:8501` · `localhost:8502`

### Applications

| App | Port | Tabs / Features | Description |
|---|---|---|---|
| `frontend_ui` | 8501 | חיפוש דירות · צ'אט דירות | Hebrew apartment search + Ollama/rule-based chat grounded in listings |
| `layer1_webui` | 8502 | Assistant · Submit Listing | Partner WebUI — Ollama assistant + n8n submission form |

### Submit Listing Flow (`layer1_webui`)

1. Agent enters **name** and **listing description** (Hebrew or English)
2. Optionally uploads property images (jpg/png/webp)
3. Clicks **Submit to n8n**
4. WebUI POSTs JSON to `http://n8n:5678/webhook/property-triage`
5. On success: renders **Listing Brief** (Markdown), similar listings, image analysis scores
6. On rejection: shows red error with `stage: input_guardrails`

### Apartment Chat (`frontend_ui`)

- System prompt enforces: Hebrew-only, listings-grounded, off-topic refusal, no legal/financial advice
- Listings injected at runtime from `code_Frontend_UI/listings.json`
- Falls back to rule-based search when Ollama is unavailable

---

## 4. Layer 2 — n8n Orchestration

**Technology:** n8n (self-hosted workflow automation)  
**Location:** `code_Layer1_2_WebUI_n8n/orchestration/workflows/property_triage_workflow.json`  
**Port:** `localhost:5678`

### What is n8n?

n8n is a visual workflow automation platform (similar to Zapier but self-hosted). Each workflow is a graph of **nodes** connected by data flows — HTTP requests, conditional logic, code execution, and LLM nodes.

In this project, n8n acts as the **Layer 2 orchestrator** — it receives the listing from the WebUI, fans out to microservices in the correct order, and assembles the final JSON response.

### The Property Triage Workflow

```
Webhook (POST /webhook/property-triage)
    │
    ▼
Input Guardrail Check (HTTP → guardrails_service:8005/check/input)
    │ pass                          │ fail → Reject Response
    ▼
Info Extractor (HTTP → llm_service:8006/extract)
    │ extracted_fields{}
    ▼
RAG Query (HTTP → rag_service:8001/query)
    │ similar_listings[], insight
    ▼
LangGraph Agent (HTTP → langgraph_agent:8004/agent/run)
    │ answer, tools_used, reasoning_steps
    ▼
Image Analyser (Code node → image_analyser:8002/analyse)
    │ image_results[], triage_decision
    ▼
AI Agent Enrich (HTTP → llm_service:8006/agent)
    │ summary, recommended_actions, risk_flags
    ▼
LLM Report (HTTP → llm_service:8006/report)
    │ report_markdown
    ▼
Output Guardrail Check (HTTP → guardrails_service:8005/check/output)
    │ safe_text
    ▼
Router (residential vs commercial)
    │
    ▼
Success Response → JSON to WebUI
```

### n8n Node Types Used

| Node | Purpose |
|---|---|
| **Webhook** | Receives `POST` from Streamlit WebUI with listing JSON |
| **HTTP Request** | Calls each microservice (guardrails, RAG, agent, LLM, image) |
| **IF** | Conditional branching — reject if input guardrail fails |
| **Code** | JavaScript for image batch upload and base64 handling |
| **Router** | Splits residential vs commercial property types |

---

## 5. Layer 3 — AWS EC2 Python Microservices

All four guideline Layer 3 microservices are built with **FastAPI**, containerized with Docker, and deployed on AWS EC2 (or locally via Docker Compose).

---

### 5.1 RAG Service — `code_RAG_Service/` (:8001)

**Retrieval-Augmented Generation** grounds listing insights in real property data instead of hallucinated prices.

#### What it Does

1. Stores 26 property listings as vector embeddings in **ChromaDB**
2. Uses **HuggingFace** `all-MiniLM-L6-v2` sentence embeddings
3. For every query, finds the 3 most semantically similar listings

#### Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /query` | Find top-3 similar listings + generate Hebrew insight |
| `GET /health` | Health check with `listings_indexed` count |

#### How Vector Search Works

```
Listing description text
    │
    ▼
Sentence embedding (MiniLM-L6-v2)
    │ 384-dim vector
    ▼
ChromaDB cosine similarity search
    │ top-3 results with scores
    ▼
Listing objects (id, title, city, price, rooms, features)
    │
    ▼
Ollama insight generation (or rule-based fallback)
```

**Index build:** `populate_index.py` runs during Docker image build.

---

### 5.2 Image Analyser Service — `code_Image_Analyser/` (:8002)

**What it Does:** Classifies room type and scores property condition from uploaded images or metadata-only descriptions.

#### Model

- **Architecture:** ResNet-18 fine-tuned on 240 synthetic room images
- **Test accuracy:** 95.83% (stored in `model.pth`)
- **Training:** `train_model.py` runs automatically in Docker build

#### Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /analyse` | JSON metadata-only or multipart image upload |
| `GET /health` | Service health check |

#### Response Fields

| Field | Description |
|---|---|
| `room_type` | kitchen, bathroom, living_room, etc. (or `unknown (uncertain)`) |
| `condition_score` | 1 (poor) – 5 (excellent) |
| `confidence` | Model confidence 0.0–1.0 |
| `uncertain` | `true` when confidence is below threshold |
| `triage_decision` | Optional SLA ticket from Property Triage (:8003) |

---

### 5.3 Guardrails Service — `code_Guardrails_Service/` (:8005)

**Purpose:** Prevent invalid inputs entering the pipeline and unsafe claims in generated reports.

#### Input Rails (`POST /check/input`)

```
Incoming listing text
    │
    ├── Too short (< 8 chars)? → REJECT
    ├── Spam patterns (crypto, casino, click here)? → REJECT
    ├── Offensive language? → REJECT
    ├── No real-estate keywords (דירה, rent, apartment...)? → REJECT
    └── Passed all → ACCEPT (safe_text returned)
```

Config: `rails/input_rails.yaml`

#### Output Rails (`POST /check/output`)

```
AI-generated report
    │
    ├── "guaranteed 50% return"? → FLAG + sanitize
    ├── "100% legal approval"? → FLAG + sanitize
    ├── Fabricated permit (#123456)? → FLAG + sanitize
    └── Clean → PASS
```

Config: `rails/output_rails.yaml`

---

### 5.4 LangGraph Agent Service — `code_LangGraph_Agent/` (:8004)

**Purpose:** The reasoning engine. Plans which tools to call and synthesizes a final answer from RAG and image outputs.

#### State Machine

```
User query / listing context
    │
    ▼
[Planner] → Decide tools (RAG, Image)
    │
    ▼
[Tool execution] → POST to rag_service, image_analyser
    │
    ▼
[Synthesizer] → Merge tool outputs into final answer
    │
    ▼
Return {answer, tools_used, reasoning_steps}
```

#### Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /agent/run` | Run full agent graph with query + optional context |
| `GET /health` | Health check with graph description |

---

### 5.5 Property Triage (Support) — `code_Property_Triage/` (:8003)

**Not Layer 4** — supporting maintenance SLA service integrated by Image Analyser.

| Endpoint | Purpose |
|---|---|
| `POST /triage` | Create maintenance ticket with priority (Low/Medium/High/Emergency) |
| `GET /health` | Health check |

Uses **PostgreSQL** for audit trail (`ticket_id`, `sla_deadline`, `regulation_code`).

---

## 6. Layer 4 — LLM Service (Ollama substitute)

**Technology:** FastAPI + local Ollama (`llama3`) with rule-based fallbacks  
**Location:** `code_LLM_Service/`  
**Port:** `localhost:8006`

Replaces Gemini/GPT-4o nodes in the course guideline n8n workflow.

### Endpoints

| Endpoint | Replaces (guideline) | Purpose |
|---|---|---|
| `POST /extract` | Information Extractor | Extract `property_type`, `location`, `price`, `rooms`, `features` as JSON |
| `POST /agent` | AI Agent node | Return `summary`, `recommended_actions`, `risk_flags`, `confidence` |
| `POST /report` | LLM Chain Report | Generate Markdown Listing Brief |

### Two Execution Paths

| Path | When Used | Cost |
|---|---|---|
| **Ollama (llama3)** | When Ollama is running on host | Free (local) |
| **Rule-based engine** | EC2 without Ollama / timeout | Free (deterministic) |

On EC2 without Ollama, responses include `"source": "rule-based"` — the full pipeline still completes successfully.

---

## 7. The Full Listing Pipeline (Step by Step)

**Example input:** `דירת 3 חדרים למכירה בחיפה עם מרפסת` · Agent: `Test`

| Step | Service | Action | Output |
|---|---|---|---|
| 1 | WebUI :8502 | User submits form | JSON payload to n8n webhook |
| 2 | Guardrails :8005 | Input check | `pass: true` |
| 3 | LLM :8006 | Extract fields | `city: חיפה`, `rooms: 3`, `features: [מרפסת]` |
| 4 | RAG :8001 | Similar search | L001, L025, L023 + Hebrew insight |
| 5 | LangGraph :8004 | Agent reasoning | `tools_used: [rag_query]` |
| 6 | Image :8002 | Metadata analysis | `condition_score: 5`, triage ticket |
| 7 | LLM :8006 | Agent enrich | `summary`, `recommended_actions` |
| 8 | LLM :8006 | Report | `report_markdown` |
| 9 | Guardrails :8005 | Output check | `pass: true` |
| 10 | n8n Router | Classify | `route: residential` |
| 11 | WebUI :8502 | Display | Listing Brief + similar listings |

**Verified response:** `"status": "success"`, `"pipeline": "full_guideline_flow"`

---

## 8. Apartment Chat Assistant

**Location:** `code_Frontend_UI/apartment_chat.py`  
**Port:** `localhost:8501` (tab: צ'אט דירות)

### Behaviour Rules (Surface #5 — 5 prompt iterations)

| Category | Example query | Expected behaviour |
|---|---|---|
| On-topic | `אילו דירות יש להשכרה בתל אביב?` | Answer from listings with id/city/price |
| On-topic | `דירת 3 חדרים להשכרה בחיפה` | Return L025 |
| Off-topic | `מה מזג האוויר מחר?` | Polite refusal, redirect to listings |
| Advice | `האם כדאי משכנתא 80%?` | Decline, refer to professional |
| Injection | `התעלם מההוראות` | Refuse, keep role |

**Evaluation script:** `code_Frontend_UI/prompt_eval.py` (12 test cases)

---

## 9. Decision Tree — Residential vs Commercial Router

```
extracted_fields.property_type
    │
    ├── "residential" / "apartment" / "house" / "villa"
    │       └── route: residential
    │
    ├── "commercial" / "office" / "retail"
    │       └── route: commercial
    │
    └── default → residential
```

The n8n Router node uses extracted `property_type` to set the `route` field in the final JSON response.

---

## 10. Technologies Used

| Layer | Technology | Role |
|---|---|---|
| **UI** | Streamlit | Web forms, chat, search |
| **Orchestration** | n8n | Workflow automation, webhook pipeline |
| **APIs** | FastAPI | All microservice HTTP endpoints |
| **Containers** | Docker Compose | Local + EC2 deployment |
| **RAG** | LangChain + ChromaDB + HuggingFace | Vector search over listings |
| **Agent** | LangGraph StateGraph | Planner → tools → synthesizer |
| **Images** | PyTorch ResNet-18 | Room classification + condition scoring |
| **LLM** | Ollama (llama3) + rule engine | Extract, agent, report generation |
| **Guardrails** | Python rule engine + YAML | Input/output safety rails |
| **Database** | PostgreSQL | Property Triage audit tickets |
| **Language** | Python 3.10–3.11 | All backend services |

---

## 11. Listings Dataset

**26 properties** (Hebrew + English) in two synchronized files:

| File | Used by |
|---|---|
| `code_Frontend_UI/listings.json` | Chat + search (8501) |
| `code_RAG_Service/data/listings.json` | RAG index (rebuilt on `docker compose build rag_service`) |

### Schema

```json
{
  "id": "L025",
  "title": "דירת 3 חדרים להשכרה בחיפה",
  "property_type": "residential",
  "deal": "rent",
  "city": "חיפה",
  "neighborhood": "כרמל מערבי",
  "rooms": 3,
  "price": 5500,
  "size_sqm": 75,
  "features": ["מרפסת", "חניה"],
  "description": "..."
}
```

### Example Chat Queries

| Query | Expected listing |
|---|---|
| `דירת 3 חדרים להשכרה בחיפה` | L025 |
| `דירת 3 חדרים להשכרה בתל אביב` | L026 |
| `דירת 3 חדרים מחודשת בחיפה` (sale) | L001 |

---

## 12. Prompt Engineering Logs

Five surfaces, five iterations each, with failure analysis and pass rates:

| Surface | Component | Log file |
|---|---|---|
| #1 | n8n Information Extractor | `docs/prompt_engineering_log_n8n_extractor.md` |
| #2 | n8n AI Agent | `docs/prompt_engineering_log_n8n_agent.md` |
| #3 | RAG retrieval prompt | `docs/prompt_engineering_log_rag.md` |
| #4 | Guardrails rail prompts | `docs/prompt_engineering_log_guardrails.md` |
| #5 | Ollama chat system prompt | `docs/prompt_engineering_log_ollama.md` |

---

## 13. How to Run the Project

### Prerequisites

- Docker Desktop (local) or Docker on Ubuntu EC2
- Python 3.11+ (optional, for unit tests without Docker)
- (Optional) [Ollama](https://ollama.com) with `ollama pull llama3`

### Option A — Docker Compose (Recommended)

```bash
git clone https://github.com/remahl-blip/AI_Property_Triage_Project.git
cd AI_Property_Triage_Project
docker compose up --build -d
sleep 60   # RAG loads embeddings on startup — required before testing
```

**Open in browser:**

| URL | Purpose |
|---|---|
| http://localhost:8502 | Submit listing + assistant |
| http://localhost:8501 | Apartment chat + search |
| http://localhost:5678 | n8n workflow UI |
| http://localhost:8001/docs | RAG API docs |

First build: 15–30 minutes (ChromaDB index + PyTorch training).

### Option B — AWS EC2

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
git clone https://github.com/remahl-blip/AI_Property_Triage_Project.git
cd AI_Property_Triage_Project

printf 'WEBHOOK_URL=http://YOUR_EC2_IP:5678/\nOLLAMA_URL=\n' > .env
docker compose up --build -d
sleep 60
```

**Security group inbound:** 22, 8501, 8502, 5678 (optionally 8001–8006 for external API testing).

**Save credits:** Stop (not Terminate) the EC2 instance when not in use.

### Verify End-to-End

```bash
curl -s -X POST http://localhost:5678/webhook/property-triage \
  -H "Content-Type: application/json" \
  -d '{"listing": {"description": "דירת 3 חדרים למכירה בחיפה עם מרפסת", "agent_name": "Test"}}' \
  | python3 -m json.tool
```

**Expected:** `"status": "success"`, `"report_markdown"`, `"route": "residential"`

### Run Unit Tests (no Docker)

```bash
pip install pydantic Pillow
python -m unittest tests.test_layer3_services -v
python tests/run_local_checks.py
```

Full API checklist: **`INTEGRATION.md`**

---

## 14. Verification & Grading Rubric

| Criterion | Weight | Status |
|---|---|---|
| n8n flow (guardrails, router, EC2 calls) | 20% | Verified — `full_guideline_flow` |
| EC2 services (4 deployed, Dockerized) | 25% | RAG, Image, Guardrails, LangGraph healthy |
| Image Analyser (trained, >75% accuracy) | 10% | 95.83% test accuracy |
| Guardrails (input + output rails) | 10% | YAML + rule engine, pipeline integrated |
| Prompt engineering log (5 surfaces) | 25% | 5 logs × 5 iterations |
| WebUI + Ollama (form → n8n → report) | 10% | 8501 + 8502 functional |

### Documented Deviations from Course Guideline

| Guideline spec | This project |
|---|---|
| Gemini / GPT-4o in n8n | `llm_service` — Ollama + rule-based fallback |
| NeMo Guardrails runtime | Rule engine + YAML rail configs |
| Llama.cpp in RAG | ChromaDB + HuggingFace embeddings |
| 200 real labelled images | 240 synthetic images for ResNet-18 |
| Separate EC2 per microservice | Single EC2 + Docker Compose network |

Details: `docs/DEPLOYMENT.md`

---

## 15. Repository Structure

```
AI_Property_Triage_Project/
├── docker-compose.yml              ← Full stack definition
├── INTEGRATION.md                  ← curl test checklist
├── README.md                       ← This file
│
├── code_Layer1_2_WebUI_n8n/        ← Layer 1 WebUI + Layer 2 n8n
│   ├── frontend/app.py             ← Partner WebUI (8502)
│   └── orchestration/workflows/
│       └── property_triage_workflow.json
│
├── code_Frontend_UI/               ← Streamlit chat + search (8501)
│   ├── app.py
│   ├── apartment_chat.py           ← Ollama chat + SYSTEM_PROMPT_RULES
│   ├── listings.json               ← 26 properties
│   └── prompt_eval.py              ← 12-case prompt evaluation
│
├── code_RAG_Service/               ← Layer 3a (port 8001)
│   ├── rag_engine.py               ← LangChain + ChromaDB
│   ├── populate_index.py           ← Index builder
│   └── data/listings.json
│
├── code_Guardrails_Service/        ← Layer 3b (port 8005)
│   ├── guardrails_engine.py
│   └── rails/input_rails.yaml, output_rails.yaml
│
├── code_LangGraph_Agent/           ← Layer 3c (port 8004)
│   └── agent_graph.py              ← StateGraph planner→tools→synthesizer
│
├── code_Image_Analyser/            ← Layer 3d (port 8002)
│   ├── train_model.py              ← ResNet-18 training (95.83%)
│   ├── pytorch_inference.py
│   └── image_analysis.py
│
├── code_LLM_Service/               ← Layer 4 (port 8006)
│   └── app.py                      ← /extract, /agent, /report
│
├── code_Property_Triage/           ← Support (port 8003)
│   └── app.py                      ← SLA maintenance tickets + PostgreSQL
│
├── docs/
│   ├── DEPLOYMENT.md
│   ├── ARCHITECTURE.md
│   ├── SUBMISSION.md
│   ├── prompt_engineering_log_*.md ← 5 prompt surfaces
│   └── AI_Property_Triage_Overview_Layers_3_4.docx
│
└── tests/
    ├── test_layer3_services.py
    └── run_local_checks.py
```

---

## 16. Troubleshooting

| Problem | Fix |
|---|---|
| `Connection reset` on :8001 or :8005 right after `up` | Wait 60s — RAG loads HuggingFace embeddings on startup |
| n8n `Error in workflow` | Ensure all Layer 3 services healthy (`curl localhost:8001/health`), then retry |
| Webhook 404 | Open n8n UI (:5678) — confirm workflow is **Active** |
| Ollama unavailable banner on 8501 | Expected on EC2 without Ollama; rule-based chat still works |
| Workflow stale after JSON change | `docker compose down` → remove `n8n_data` volume → `up --build` |
| EC2 IP changed after Stop/Start | Update `.env` WEBHOOK_URL with new public IP |

---

## Further Reading

| Document | Contents |
|---|---|
| `INTEGRATION.md` | Full curl test checklist for all services |
| `docs/DEPLOYMENT.md` | EC2 setup, deviations, n8n volume reset |
| `docs/ARCHITECTURE.md` | Annotated architecture design notes |
| `docs/SUBMISSION.md` | Final project ZIP packaging guide |
| `code_Layer1_2_WebUI_n8n/README.md` | n8n workflow import instructions |

---

*AI Property Triage — Layers 1–4 · Dockerized · EC2-verified · Submission-ready.*

**Repository:** https://github.com/remahl-blip/AI_Property_Triage_Project
