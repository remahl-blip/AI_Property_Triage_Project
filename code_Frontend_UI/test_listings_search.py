"""Unit tests for the shared listings_search helper module.

Framework-agnostic; run with the standard library:

    python -m unittest test_listings_search

(They also work under pytest if installed: ``pytest test_listings_search.py``.)
"""

import unittest

import listings_search as ls

SAMPLE = [
    {
        "id": "A1", "title": "דירת 3 חדרים בחיפה", "property_type": "apartment",
        "deal": "sale", "city": "חיפה", "neighborhood": "כרמל", "rooms": 3,
        "price": 1850000, "size_sqm": 78, "features": ["מרפסת", "חניה", "נוף לים"],
        "description": "דירה מוארת עם נוף לים.",
    },
    {
        "id": "A2", "title": "וילה בהרצליה", "property_type": "villa",
        "deal": "sale", "city": "הרצליה", "neighborhood": "פיתוח", "rooms": 6,
        "price": 8500000, "size_sqm": 320, "features": ["בריכה", "גינה"],
        "description": "וילה יוקרתית עם בריכה.",
    },
    {
        "id": "A3", "title": "דירת 4 חדרים בתל אביב", "property_type": "apartment",
        "deal": "rent", "city": "תל אביב", "neighborhood": "רוטשילד", "rooms": 4,
        "price": 9500, "size_sqm": 95, "features": ["מרפסת", "מעלית"],
        "description": "דירה מרווחת במרכז.",
    },
    {
        "id": "A4", "title": "סטודיו בירושלים", "property_type": "apartment",
        "deal": "rent", "city": "ירושלים", "neighborhood": "מרכז", "rooms": 1,
        "price": 3800, "size_sqm": 32, "features": ["מעלית"],
        "description": "סטודיו קומפקטי.",
    },
]


def _ids(results):
    return sorted(item["id"] for item in results)


class FeatureVocabularyTests(unittest.TestCase):
    def test_collects_all_unique_features(self):
        vocab = ls.feature_vocabulary(SAMPLE)
        self.assertEqual(
            vocab,
            {"מרפסת", "חניה", "נוף לים", "בריכה", "גינה", "מעלית"},
        )

    def test_handles_missing_features_key(self):
        self.assertEqual(ls.feature_vocabulary([{"id": "X"}]), set())


class MatchesQueryTests(unittest.TestCase):
    def test_empty_query_matches_everything(self):
        self.assertTrue(ls.matches_query(SAMPLE[0], ""))
        self.assertTrue(ls.matches_query(SAMPLE[0], "   "))
        self.assertTrue(ls.matches_query(SAMPLE[0], None))

    def test_matches_city_and_feature_and_description(self):
        item = SAMPLE[0]
        self.assertTrue(ls.matches_query(item, "חיפה"))
        self.assertTrue(ls.matches_query(item, "נוף לים"))
        self.assertTrue(ls.matches_query(item, "כרמל"))

    def test_non_matching_query(self):
        self.assertFalse(ls.matches_query(SAMPLE[0], "באר שבע"))


class FilterListingsTests(unittest.TestCase):
    def test_no_criteria_returns_all(self):
        self.assertEqual(len(ls.filter_listings(SAMPLE)), len(SAMPLE))

    def test_filter_by_cities(self):
        self.assertEqual(_ids(ls.filter_listings(SAMPLE, cities=["חיפה"])), ["A1"])

    def test_filter_by_multiple_cities(self):
        self.assertEqual(
            _ids(ls.filter_listings(SAMPLE, cities=["חיפה", "ירושלים"])),
            ["A1", "A4"],
        )

    def test_filter_by_deal(self):
        self.assertEqual(_ids(ls.filter_listings(SAMPLE, deals=["rent"])), ["A3", "A4"])

    def test_filter_by_property_type(self):
        self.assertEqual(
            _ids(ls.filter_listings(SAMPLE, property_types=["apartment"])),
            ["A1", "A3", "A4"],
        )

    def test_filter_by_rooms_range(self):
        self.assertEqual(
            _ids(ls.filter_listings(SAMPLE, rooms_range=(3, 6))),
            ["A1", "A2", "A3"],
        )

    def test_filter_by_price_range(self):
        self.assertEqual(
            _ids(ls.filter_listings(SAMPLE, price_range=(0, 100000))),
            ["A3", "A4"],
        )

    def test_filter_by_max_price(self):
        self.assertEqual(
            _ids(ls.filter_listings(SAMPLE, max_price=5000)),
            ["A4"],
        )

    def test_filter_by_features_requires_all(self):
        self.assertEqual(
            _ids(ls.filter_listings(SAMPLE, features=["מרפסת", "חניה"])),
            ["A1"],
        )
        self.assertEqual(
            _ids(ls.filter_listings(SAMPLE, features=["מרפסת"])),
            ["A1", "A3"],
        )

    def test_filter_by_free_text_query(self):
        self.assertEqual(_ids(ls.filter_listings(SAMPLE, query="רוטשילד")), ["A3"])

    def test_combined_criteria(self):
        results = ls.filter_listings(
            SAMPLE, deals=["sale"], property_types=["apartment"], features=["מרפסת"]
        )
        self.assertEqual(_ids(results), ["A1"])

    def test_no_match_returns_empty(self):
        self.assertEqual(ls.filter_listings(SAMPLE, cities=["אילת"]), [])


class ParseQueryTests(unittest.TestCase):
    def test_detects_rent(self):
        self.assertEqual(ls.parse_query("דירה להשכרה", SAMPLE).get("deal"), "rent")

    def test_detects_sale(self):
        self.assertEqual(ls.parse_query("דירה למכירה", SAMPLE).get("deal"), "sale")

    def test_detects_city(self):
        self.assertEqual(ls.parse_query("משהו בתל אביב", SAMPLE).get("city"), "תל אביב")

    def test_detects_property_type(self):
        self.assertEqual(ls.parse_query("וילה יפה", SAMPLE).get("property_type"), "villa")

    def test_detects_rooms(self):
        self.assertEqual(ls.parse_query("דירת 3 חדרים", SAMPLE).get("rooms"), 3)

    def test_detects_max_price_with_commas(self):
        self.assertEqual(
            ls.parse_query("עד 2,000,000", SAMPLE).get("max_price"), 2000000
        )

    def test_detects_features(self):
        criteria = ls.parse_query("דירה עם מרפסת ובריכה", SAMPLE)
        self.assertEqual(set(criteria["features"]), {"מרפסת", "בריכה"})

    def test_empty_query_returns_no_criteria(self):
        self.assertEqual(ls.parse_query("בלי שום מילת מפתח רלוונטית כאן", SAMPLE), {})

    def test_combined_parse(self):
        criteria = ls.parse_query("דירת 3 חדרים למכירה בחיפה עם מרפסת", SAMPLE)
        self.assertEqual(criteria.get("deal"), "sale")
        self.assertEqual(criteria.get("city"), "חיפה")
        self.assertEqual(criteria.get("rooms"), 3)
        self.assertIn("מרפסת", criteria.get("features", []))


class FilterByCriteriaTests(unittest.TestCase):
    def test_parsed_criteria_filters_correctly(self):
        criteria = ls.parse_query("דירה למכירה בחיפה עם מרפסת", SAMPLE)
        self.assertEqual(_ids(ls.filter_by_criteria(SAMPLE, criteria)), ["A1"])

    def test_rooms_criterion_is_exact(self):
        criteria = ls.parse_query("דירת 4 חדרים", SAMPLE)
        self.assertEqual(_ids(ls.filter_by_criteria(SAMPLE, criteria)), ["A3"])

    def test_no_results_for_impossible_combo(self):
        criteria = ls.parse_query("וילה להשכרה", SAMPLE)
        self.assertEqual(ls.filter_by_criteria(SAMPLE, criteria), [])


class DescribeCriteriaTests(unittest.TestCase):
    def test_describes_all_parts(self):
        criteria = {
            "city": "חיפה", "deal": "sale", "property_type": "apartment",
            "rooms": 3, "max_price": 2000000, "features": ["מרפסת"],
        }
        text = ls.describe_criteria(criteria)
        self.assertIn("עיר: חיפה", text)
        self.assertIn("מכירה", text)
        self.assertIn("דירה", text)
        self.assertIn("3 חדרים", text)
        self.assertIn("2,000,000", text)
        self.assertIn("מרפסת", text)

    def test_empty_criteria_is_empty_string(self):
        self.assertEqual(ls.describe_criteria({}), "")


if __name__ == "__main__":
    unittest.main()
