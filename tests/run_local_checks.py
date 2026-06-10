"""One-off local verification script (no Docker required)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code_Guardrails_Service"))
sys.path.insert(0, str(ROOT / "code_Image_Analyser"))

from guardrails_engine import check_input_text, check_output_text  # noqa: E402
from image_analysis import analyse_metadata_only  # noqa: E402


def main() -> int:
    failed = 0

    print("=== INPUT GUARDRAILS ===")
    for name, text, expect in [
        ("valid listing", "דירה למכירה בחיפה 3 חדרים", True),
        ("spam", "buy crypto casino amazing deal click here", False),
        ("off-topic", "hello world nothing relevant here at all", False),
    ]:
        r = check_input_text(text)
        ok = r.pass_ == expect
        print(f"{name}: pass={r.pass_} expected={expect} -> {'PASS' if ok else 'FAIL'}")
        failed += 0 if ok else 1

    print("=== OUTPUT GUARDRAILS ===")
    for name, text, expect in [
        ("unsafe guarantee", "guaranteed 100% legal approval permit #123456", False),
        ("safe output", "נמצאו 3 נכסים דומים בחיפה במחירים סבירים.", True),
    ]:
        r = check_output_text(text)
        ok = r.pass_ == expect
        print(f"{name}: pass={r.pass_} expected={expect} -> {'PASS' if ok else 'FAIL'}")
        failed += 0 if ok else 1

    print("=== IMAGE METADATA ANALYSIS ===")
    result = analyse_metadata_only("kitchen_leak.jpg", "severe water leak near sink")
    ok = all(k in result for k in ("room_type", "condition_score", "confidence"))
    print(f"shape ok={ok} room={result.get('room_type')} score={result.get('condition_score')}")
    failed += 0 if ok else 1

    print("=== LISTINGS AUDIT ===")
    for rel in ("code_Frontend_UI/listings.json", "code_RAG_Service/data/listings.json"):
        data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        ids = {x["id"] for x in data}
        rent_haifa = [x for x in data if x.get("deal") == "rent" and x.get("city") == "חיפה" and x.get("rooms") == 3]
        rent_tlv = [x for x in data if x.get("deal") == "rent" and x.get("city") == "תל אביב" and x.get("rooms") == 3]
        print(f"{rel}: count={len(data)} L025={'L025' in ids} L026={'L026' in ids} rent3_haifa={len(rent_haifa)} rent3_tlv={len(rent_tlv)}")

    print("=== PROMPT LOG AUDIT ===")
    logs = sorted((ROOT / "docs").glob("prompt_engineering_log_*.md"))
    for path in logs:
        text = path.read_text(encoding="utf-8")
        versions = sum(1 for i in range(1, 6) if f"Version {i}" in text or f"| v{i}" in text)
        has_failure = "Failure" in text or "failure" in text or "F1" in text
        has_metric = any(w in text for w in ("Pass rate", "pass rate", "/10", "/20", "%"))
        print(f"{path.name}: versions~={versions} failure_analysis={has_failure} metrics={has_metric}")

    print(f"\nTOTAL FAILURES: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
