"""Shared apartment listings search/filter helpers.

Framework-agnostic (no Streamlit / pandas dependency) so both the Streamlit
search tab and the chat module reuse the same filtering logic.
"""

import re

DEAL_LABELS = {"sale": "מכירה", "rent": "השכרה"}
TYPE_LABELS = {
    "apartment": "דירה",
    "villa": "וילה",
    "house": "בית",
    "penthouse": "פנטהאוז",
    "studio": "סטודיו",
    "duplex": "דופלקס",
    "cottage": "קוטג'",
}

_RENT_WORDS = ["השכרה", "להשכרה", "שכירות", "לשכור", "שכירה"]
_SALE_WORDS = ["מכירה", "למכירה", "לקנות", "קנייה", "קניה", "רכישה"]


def feature_vocabulary(listings):
    """Return the set of all features that appear across the listings."""
    vocab = set()
    for item in listings:
        for feat in item.get("features", []) or []:
            vocab.add(feat)
    return vocab


def matches_query(item, query):
    """Free-text substring match across the listing's text fields."""
    if not query or not query.strip():
        return True
    haystack = " ".join([
        str(item.get("title", "")),
        str(item.get("city", "")),
        str(item.get("neighborhood", "")),
        str(item.get("description", "")),
        " ".join(item.get("features", []) or []),
    ])
    return query.strip() in haystack


def filter_listings(listings, cities=None, deals=None, property_types=None,
                    rooms_range=None, price_range=None, max_price=None,
                    features=None, query=None):
    """Filter listings by any combination of criteria.

    All arguments are optional; a criterion is ignored when left as None/empty.
    ``cities``, ``deals`` and ``property_types`` match any of the given values.
    ``features`` requires the listing to contain all of the given features.
    """
    results = []
    for item in listings:
        if cities and item.get("city") not in cities:
            continue
        if deals and item.get("deal") not in deals:
            continue
        if property_types and item.get("property_type") not in property_types:
            continue
        if rooms_range is not None:
            rooms = int(item.get("rooms", 0))
            if rooms < rooms_range[0] or rooms > rooms_range[1]:
                continue
        if price_range is not None:
            price = int(item.get("price", 0))
            if price < price_range[0] or price > price_range[1]:
                continue
        if max_price is not None and int(item.get("price", 0)) > max_price:
            continue
        if features:
            item_features = set(item.get("features", []) or [])
            if not set(features).issubset(item_features):
                continue
        if not matches_query(item, query):
            continue
        results.append(item)
    return results


def parse_query(text, listings):
    """Parse a free-text (Hebrew) query into structured filter criteria."""
    criteria = {}

    if any(word in text for word in _RENT_WORDS):
        criteria["deal"] = "rent"
    elif any(word in text for word in _SALE_WORDS):
        criteria["deal"] = "sale"

    cities = {item.get("city") for item in listings if item.get("city")}
    for city in cities:
        if city and city in text:
            criteria["city"] = city
            break

    for ptype, label in TYPE_LABELS.items():
        if label and label in text:
            criteria["property_type"] = ptype
            break

    rooms_match = re.search(r"(\d+)\s*חדר", text)
    if rooms_match:
        criteria["rooms"] = int(rooms_match.group(1))

    price_match = re.search(r"עד\s*([\d,]+)", text)
    if price_match:
        criteria["max_price"] = int(price_match.group(1).replace(",", ""))

    matched_features = [feat for feat in feature_vocabulary(listings) if feat in text]
    if matched_features:
        criteria["features"] = matched_features

    return criteria


def filter_by_criteria(listings, criteria):
    """Apply criteria produced by :func:`parse_query` to the listings."""
    return filter_listings(
        listings,
        cities=[criteria["city"]] if "city" in criteria else None,
        deals=[criteria["deal"]] if "deal" in criteria else None,
        property_types=[criteria["property_type"]] if "property_type" in criteria else None,
        rooms_range=(criteria["rooms"], criteria["rooms"]) if "rooms" in criteria else None,
        max_price=criteria.get("max_price"),
        features=criteria.get("features"),
    )


def describe_criteria(criteria):
    """Human-readable Hebrew description of parsed criteria."""
    parts = []
    if "city" in criteria:
        parts.append(f"עיר: {criteria['city']}")
    if "deal" in criteria:
        parts.append(DEAL_LABELS.get(criteria["deal"], criteria["deal"]))
    if "property_type" in criteria:
        parts.append(TYPE_LABELS.get(criteria["property_type"], criteria["property_type"]))
    if "rooms" in criteria:
        parts.append(f"{criteria['rooms']} חדרים")
    if "max_price" in criteria:
        parts.append(f"עד ₪{criteria['max_price']:,}")
    if "features" in criteria:
        parts.append("מאפיינים: " + ", ".join(criteria["features"]))
    return " · ".join(parts)
