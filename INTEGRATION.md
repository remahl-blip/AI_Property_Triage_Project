# Integration test checklist

Run after `docker compose up --build -d`.

## Health checks

```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8005/health
```

## RAG Service (8001)

```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d "{\"description\": \"דירת 3 חדרים למכירה בחיפה עם מרפסת\"}"
```

Expected: `similar_listings` array (≥1) and Hebrew/English `insight`.

## Guardrails Service (8005)

```bash
curl -X POST http://localhost:8005/check/input \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"דירה למכירה בחיפה 3 חדרים\"}"

curl -X POST http://localhost:8005/check/output \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"guaranteed 100% legal approval permit #123456\"}"
```

Expected: input `pass: true`; output `pass: false`.

## Image Analyser (8002)

Metadata-only JSON:

```bash
curl -X POST http://localhost:8002/analyse \
  -H "Content-Type: application/json" \
  -d "{\"condition_description\": \"severe water leak in kitchen\", \"filename\": \"kitchen_leak.jpg\"}"
```

Expected: `room_type`, `condition_score` (1–5), `confidence`, optional `triage_decision`.

## LangGraph Agent (8004)

```bash
curl -X POST http://localhost:8004/agent/run \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"חפש דירה דומה בחיפה עם מרפסת\"}"
```

Expected: `answer`, `tools_used` (includes `rag_query`), `reasoning_steps`.

## Property Triage — support service (8003)

```bash
curl -X POST http://localhost:8003/triage \
  -H "Content-Type: application/json" \
  -d "{\"room_type\": \"kitchen\", \"condition_description\": \"severe water leak and flood\"}"
```

Expected: `priority` High or Emergency, `audit_report.ticket_id`.

## n8n webhook (5678)

```bash
curl -X POST http://localhost:5678/webhook/property-triage \
  -H "Content-Type: application/json" \
  -d "{\"listing\": {\"description\": \"דירת 3 חדרים למכירה בחיפה עם מרפסת\", \"property_type\": \"residential\", \"agent_name\": \"Test\"}}"
```

Expected: `status: success`, `rag_result`, `agent_result`, `route: residential`.

## Unit tests

```bash
docker compose run --rm --no-deps -v "%cd%:/workspace" rag_service sh -c "pip install -q Pillow && cd /workspace && PYTHONPATH=code_Guardrails_Service:code_RAG_Service:code_Image_Analyser python -m unittest tests.test_layer3_services -v"
```

On Linux/macOS replace `%cd%` with `` `pwd` ``.

## Validate compose file

```bash
docker compose config
```
