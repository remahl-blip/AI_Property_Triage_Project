# Prompt Engineering Log — Surface #4: Guardrails Rail Prompts

**Component:** `code_Guardrails_Service` — `rails/input_rails.yaml`, `rails/output_rails.yaml` + `guardrails_engine.py`

## Input rails — 5 iterations

| Ver | Change | Result |
|-----|--------|--------|
| v1 | Block everything without URL | High false positives on short valid listings |
| v2 | Added REAL_ESTATE_HINTS list | Valid listings pass; spam still passes |
| v3 | Added SPAM_PATTERNS + min length 8 | Spam blocked; one valid short desc failed |
| v4 | Lowered min length logic + Hebrew hints | False positive rate <5% on 20-case suite |
| v5 | YAML-documented topic + policy prompts | Stable; matches NeMo-style spec |

## Output rails — 5 iterations

| Ver | Change | Result |
|-----|--------|--------|
| v1 | Block any number in output | Too aggressive |
| v2 | Target "guaranteed return" patterns only | Legal claims still leaked |
| v3 | Added LEGAL_GUARANTEE + FABRICATED_CERT patterns | Catches ministry permit hallucinations |
| v4 | Return sanitized `safe_text` with claim removed | Human-review path possible |
| v5 | YAML auditor prompt documents policy | 10/10 unsafe outputs flagged in test suite |

**Final pass rate:** Input 19/20 valid pass; Output 10/10 unsafe samples flagged.
