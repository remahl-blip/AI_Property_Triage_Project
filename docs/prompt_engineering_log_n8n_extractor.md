# Prompt Engineering Log — Surface #1: n8n Information Extractor (Ollama substitute)

**Component:** `code_LLM_Service` → `POST /extract` (replaces Gemini Information Extractor node)  
**Model:** local Ollama `llama3` with rule-based fallback

## Test suite (10 cases)
Valid apartment/rent/sale descriptions, missing price, commercial office, Hebrew only, English only, spam, off-topic, multi-feature, studio, villa.

## Version 1 — Baseline
Simple prompt: "Extract property fields as JSON."
**Failure:** Model invented prices and rooms not in text.

## Version 2
Added: "Extract only facts present; use null for missing fields."
**Failure:** Inconsistent property_type values (`flat` vs `apartment`).

## Version 3
Added enum constraint for `property_type` and array type for `features`.
**Improved:** Consistent types; still missed Hebrew room counts occasionally.

## Version 4
Added Hebrew examples in system prompt and explicit `rooms` integer rule.
**Improved:** Hebrew extraction stable; occasional extra features hallucinated.

## Version 5 — Final (shipped)
```text
Return ONLY valid JSON: property_type, location, price, rooms, features, certifications.
Use null for missing fields. Never invent values. property_type enum enforced.
```
**Pass rate:** 9/10 (spam correctly handled by Guardrails upstream).  
**Fallback:** `_rule_extract()` regex parser when Ollama unavailable.
