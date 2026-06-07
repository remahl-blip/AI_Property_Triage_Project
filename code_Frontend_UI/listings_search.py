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


def neighborhood_vocabulary(listings):
    """Return the set of all neighborhoods that appear across the listings."""
    return {item["neighborhood"] for item in listings if item.get("neighborhood")}


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
                    min_price=None, features=None, query=None, neighborhoods=None):
    """Filter listings by any combination of criteria.

    All arguments are optional; a criterion is ignored when left as None/empty.
    ``cities``, ``deals``, ``property_types`` and ``neighborhoods`` match any of
    the given values. ``features`` requires the listing to contain all of the
    given features. ``rooms_range``/``price_range`` are inclusive ``(min, max)``
    tuples, while ``min_price``/``max_price`` apply one-sided bounds.
    """
    results = []
    for item in listings:
        if cities and item.get("city") not in cities:
            continue
        if neighborhoods and item.get("neighborhood") not in neighborhoods:
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
        if min_price is not None and int(item.get("price", 0)) < min_price:
            continue
        if features:
            item_features = set(item.get("features", []) or [])
            if not set(features).issubset(item_features):
                continue
        if not matches_query(item, query):
            continue
        results.append(item)
    return results


def _to_int(raw):
    return int(raw.replace(",", "").strip())


def parse_query(text, listings):
    """Parse a free-text (Hebrew) query into structured filter criteria."""
    criteria = {}

    if any(word in text for word in _RENT_WORDS):
        criteria["deal"] = "rent"
    elif any(word in text for word in _SALE_WORDS):
        criteria["deal"] = "sale"

    for city in {item.get("city") for item in listings if item.get("city")}:
        if city and city in text:
            criteria["city"] = city
            break

    for neighborhood in neighborhood_vocabulary(listings):
        if neighborhood in text:
            criteria["neighborhood"] = neighborhood
            break

    for ptype, label in TYPE_LABELS.items():
        if label and label in text:
            criteria["property_type"] = ptype
            break

    rooms_min_match = (
        re.search(r"(\d+)\s*\+\s*חדר", text)
        or re.search(r"לפחות\s*(\d+)\s*חדר", text)
        or re.search(r"מ-?\s*(\d+)\s*חדר", text)
    )
    if rooms_min_match:
        criteria["rooms_min"] = int(rooms_min_match.group(1))
    else:
        rooms_match = re.search(r"(\d+)\s*חדר", text)
        if rooms_match:
            criteria["rooms"] = int(rooms_match.group(1))

    range_match = re.search(r"בין\s*([\d,]+)\s*ל(?:בין)?\s*-?\s*([\d,]+)", text)
    if range_match:
        low, high = _to_int(range_match.group(1)), _to_int(range_match.group(2))
        criteria["min_price"], criteria["max_price"] = min(low, high), max(low, high)
    else:
        max_match = re.search(r"עד\s*([\d,]+)", text)
        if max_match:
            criteria["max_price"] = _to_int(max_match.group(1))
        min_match = re.search(r"מעל\s*([\d,]+)", text) or re.search(r"החל\s*מ-?\s*([\d,]+)", text)
        if min_match:
            criteria["min_price"] = _to_int(min_match.group(1))

    matched_features = [feat for feat in feature_vocabulary(listings) if feat in text]
    if matched_features:
        criteria["features"] = matched_features

    return criteria


def filter_by_criteria(listings, criteria):
    """Apply criteria produced by :func:`parse_query` to the listings."""
    rooms_range = None
    if "rooms" in criteria:
        rooms_range = (criteria["rooms"], criteria["rooms"])
    elif "rooms_min" in criteria:
        rooms_range = (criteria["rooms_min"], float("inf"))

    return filter_listings(
        listings,
        cities=[criteria["city"]] if "city" in criteria else None,
        neighborhoods=[criteria["neighborhood"]] if "neighborhood" in criteria else None,
        deals=[criteria["deal"]] if "deal" in criteria else None,
        property_types=[criteria["property_type"]] if "property_type" in criteria else None,
        rooms_range=rooms_range,
        max_price=criteria.get("max_price"),
        min_price=criteria.get("min_price"),
        features=criteria.get("features"),
    )


def describe_criteria(criteria):
    """Human-readable Hebrew description of parsed criteria."""
    parts = []
    if "city" in criteria:
        parts.append(f"עיר: {criteria['city']}")
    if "neighborhood" in criteria:
        parts.append(f"שכונה: {criteria['neighborhood']}")
    if "deal" in criteria:
        parts.append(DEAL_LABELS.get(criteria["deal"], criteria["deal"]))
    if "property_type" in criteria:
        parts.append(TYPE_LABELS.get(criteria["property_type"], criteria["property_type"]))
    if "rooms" in criteria:
        parts.append(f"{criteria['rooms']} חדרים")
    if "rooms_min" in criteria:
        parts.append(f"{criteria['rooms_min']}+ חדרים")
    if "min_price" in criteria and "max_price" in criteria:
        parts.append(f"₪{criteria['min_price']:,}–₪{criteria['max_price']:,}")
    elif "max_price" in criteria:
        parts.append(f"עד ₪{criteria['max_price']:,}")
    elif "min_price" in criteria:
        parts.append(f"מעל ₪{criteria['min_price']:,}")
    if "features" in criteria:
        parts.append("מאפיינים: " + ", ".join(criteria["features"]))
    return " · ".join(parts)
