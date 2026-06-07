# Demo Video Guide (5–8 minutes)

Record a screen capture showing all four required scenarios.

## 1. Successful end-to-end submission (~2 min)

1. `docker compose up --build`
2. Open http://localhost:8502 (Listing Submission tab)
3. Submit a valid Hebrew listing, e.g.:
   - Description: `דירת 3 חדרים למכירה בחיפה עם מרפסת ונוף לים, מחיר 2,200,000`
   - Agent name: `Demo Agent`
4. Show the returned **Listing Brief** (Markdown), similar listings, and image scores.

## 2. Input guardrail rejection (~1 min)

Submit spam text: `buy crypto casino amazing deal click here`

Expected: red error — `status: rejected`, `stage: input_guardrails`.

## 3. Output guardrail flag (~1 min)

Use curl or temporarily weaken output guardrails to show a report with `guaranteed 50% return` — or submit via n8n test with pre-built unsafe report.

Expected: `status: output_flagged` or sanitized `safe_text`.

## 4. Ollama conversational assistant (~2 min)

1. Open http://localhost:8501 → tab **צ'אט דירות** (or partner WebUI chat tab if present)
2. Ask: `מה המחיר הממוצע לדירה 3 חדרים בחיפה?`
3. Ask off-topic: `כתוב לי קוד Python למשחק` — show polite refusal
4. Optional: show `SOURCE: ollama` in response metadata

## Save

Place `demo.mp4` in this folder or upload to Drive/YouTube and add the link below.

**Video link:** _(add URL here before submission)_
