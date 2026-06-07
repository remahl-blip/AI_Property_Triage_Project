"""Minimal unit tests for Layer 3 microservice logic (no Docker required)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code_Guardrails_Service"))
sys.path.insert(0, str(ROOT / "code_RAG_Service"))
sys.path.insert(0, str(ROOT / "code_Image_Analyser"))

from guardrails_engine import check_input_text, check_output_text  # noqa: E402
from rag_engine import ListingIndex, rule_based_insight  # noqa: E402
from image_analysis import analyse_metadata_only  # noqa: E402


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
    @classmethod
    def setUpClass(cls):
        cls.index = ListingIndex()
        cls.index.load(ROOT / "code_RAG_Service" / "data" / "listings.json")

    def test_index_has_at_least_20_listings(self):
        self.assertGreaterEqual(len(self.index.listings), 20)

    def test_search_returns_results(self):
        hits = self.index.search("apartment for rent in Tel Aviv")
        self.assertTrue(hits)
        self.assertIn("similarity_score", hits[0])

    def test_insight_template(self):
        hits = self.index.search("דירה בחיפה")
        insight = rule_based_insight("דירה בחיפה", hits)
        self.assertIn("נכס", insight)


class ImageAnalyserTests(unittest.TestCase):
    def test_metadata_analysis_shape(self):
        result = analyse_metadata_only("kitchen_leak.jpg", "severe water leak near sink")
        self.assertIn("room_type", result)
        self.assertIn("condition_score", result)
        self.assertGreaterEqual(result["condition_score"], 1)
        self.assertLessEqual(result["condition_score"], 5)
        self.assertIn("confidence", result)


if __name__ == "__main__":
    unittest.main()
