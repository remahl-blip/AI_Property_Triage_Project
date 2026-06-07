"""Minimal unit tests for Layer 3 microservice logic (no Docker required)."""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code_Guardrails_Service"))
sys.path.insert(0, str(ROOT / "code_Image_Analyser"))

from guardrails_engine import check_input_text, check_output_text  # noqa: E402
from image_analysis import analyse_metadata_only  # noqa: E402

LISTINGS_PATH = ROOT / "code_RAG_Service" / "data" / "listings.json"


def _rule_extract(text: str) -> dict:
    """Mirror of llm_service offline extractor for lightweight tests."""
    lowered = text.lower()
    result = {"property_type": None, "location": None, "price": None, "rooms": None, "features": []}
    if any(h in lowered or h in text for h in ("דירה", "דירת", "apartment", "flat")):
        result["property_type"] = "apartment"
    for city in ("חיפה", "תל אביב", "haifa", "tel aviv"):
        if city.lower() in lowered or city in text:
            result["location"] = city
            break
    rooms_m = re.search(r"(\d+)\s*(?:rooms?|חדר)", lowered)
    if rooms_m:
        result["rooms"] = int(rooms_m.group(1))
    return result


class GuardrailsTests(unittest.TestCase):
    def test_accepts_real_estate_input(self):
        result = check_input_text("דירת 3 חדרים למכירה בחיפה עם מרפסת ונוף לים")
        self.assertTrue(result.pass_)
        self.assertIn("safe", result.reason.lower())

    def test_rejects_spam(self):
        result = check_input_text("buy now crypto casino amazing deal")
        self.assertFalse(result.pass_)

    def test_rejects_off_topic(self):
        result = check_input_text("hello world nothing relevant here at all")
        self.assertFalse(result.pass_)

    def test_flags_invented_output(self):
        result = check_output_text("guaranteed 50% return on this apartment investment")
        self.assertFalse(result.pass_)

    def test_accepts_safe_output(self):
        result = check_output_text("נמצאו 3 נכסים דומים בחיפה במחירים סבירים.")
        self.assertTrue(result.pass_)


class RAGTests(unittest.TestCase):
    def test_listings_file_has_at_least_20(self):
        with open(LISTINGS_PATH, encoding="utf-8") as f:
            listings = json.load(f)
        self.assertGreaterEqual(len(listings), 20)
        self.assertIn("id", listings[0])

    def test_listing_schema_fields(self):
        with open(LISTINGS_PATH, encoding="utf-8") as f:
            listing = json.load(f)[0]
        for key in ("id", "title", "description", "city", "property_type", "price"):
            self.assertIn(key, listing)


class ImageAnalyserTests(unittest.TestCase):
    def test_metadata_analysis_shape(self):
        result = analyse_metadata_only("kitchen_leak.jpg", "severe water leak near sink")
        self.assertIn("room_type", result)
        self.assertIn("condition_score", result)
        self.assertGreaterEqual(result["condition_score"], 1)
        self.assertLessEqual(result["condition_score"], 5)
        self.assertIn("confidence", result)


class LLMServiceTests(unittest.TestCase):
    def test_rule_extract_hebrew_listing(self):
        fields = _rule_extract("דירת 3 חדרים למכירה בחיפה עם מרפסת, מחיר 2,500,000")
        self.assertEqual(fields["property_type"], "apartment")
        self.assertEqual(fields["rooms"], 3)
        self.assertIn("חיפה", fields["location"] or "")


if __name__ == "__main__":
    unittest.main()
