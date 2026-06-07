# Prompt Engineering Log — Surface #3: LangChain RAG Retrieval Prompt

**Component:** `code_RAG_Service/rag_engine.py` — LangChain `ChatPromptTemplate` + ChromaDB retrieval

## Version 1 — Baseline
"Summarize similar listings."
**Failure:** Fabricated prices not in retrieved documents.

## Version 2
Added: "Use ONLY retrieved context" + listing IDs in context string.
**Improved:** Citations appear; still answered in English sometimes.

## Version 3
Added Hebrew-only instruction and "2-3 sentences" length limit.
**Improved:** Hebrew responses; occasional ID omission.

## Version 4
Explicit: "Cite listing IDs you reference."
**Improved:** IDs cited (L001, L003); insight quality good with Ollama.

## Version 5 — Final (shipped)
```text
You are a real-estate analyst. Use ONLY the retrieved listing context below.
Cite listing IDs you reference. Do not invent prices or features.
Respond in 2-3 Hebrew sentences.
```
**Pass rate:** 9/10 queries grounded correctly. Rule-based fallback when Ollama unavailable.
