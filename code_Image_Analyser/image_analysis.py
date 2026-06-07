import io
import statistics
from typing import BinaryIO

from PIL import Image, ImageFilter, ImageStat

CONFIDENCE_THRESHOLD = 0.55

ROOM_HINTS = {
    "kitchen": ("kitchen", "מטבח", "sink", "stove"),
    "bathroom": ("bathroom", "שירותים", "אמבטיה", "shower", "toilet"),
    "bedroom": ("bedroom", "חדר שינה", "bed"),
    "living room": ("living", "סלון", "lounge", "sofa"),
    "hallway": ("hallway", "מסדרון", "corridor"),
    "exterior": ("exterior", "outside", "facade", "חוץ", "garden", "גינה"),
}

ISSUE_HINTS = {
    "leak": ("leak", "נזילה", "drip", "water damage", "wet"),
    "flood": ("flood", "הצפה", "flooding"),
    "mold": ("mold", "עובש", "mildew"),
    "crack": ("crack", "סדק", "fracture"),
    "fire": ("fire", "smoke", "gas", "wires"),
    "broken": ("broken", "שבור", "damage", "damaged"),
}


def _infer_room_from_text(*texts: str) -> tuple[str, float]:
    combined = " ".join(texts).lower()
    best_room = "unknown"
    best_score = 0.0
    for room, hints in ROOM_HINTS.items():
        hits = sum(1 for hint in hints if hint in combined)
        if hits > best_score:
            best_score = hits
            best_room = room
    confidence = min(0.35 + 0.15 * best_score, 0.85) if best_score else 0.2
    return best_room, confidence


def _infer_issues(*texts: str) -> tuple[list[str], list[str], float]:
    combined = " ".join(texts).lower()
    issues = []
    keywords = []
    for label, hints in ISSUE_HINTS.items():
        if any(hint in combined for hint in hints):
            issues.append(f"{label} detected")
            keywords.append(label)
    if issues:
        return issues, keywords, 0.75
    return ["routine maintenance inspection"], ["inspection"], 0.35


def _pixel_features(image: Image.Image) -> dict:
    rgb = image.convert("RGB")
    gray = rgb.convert("L")
    small = gray.resize((128, 128))
    stat = ImageStat.Stat(small)
    brightness = stat.mean[0] / 255.0
    contrast = (stat.stddev[0] / 128.0) if stat.stddev else 0.0
    edges = small.filter(ImageFilter.FIND_EDGES)
    edge_stat = ImageStat.Stat(edges)
    edge_density = (edge_stat.mean[0] / 255.0) if edge_stat.mean else 0.0
    pixels = list(small.getdata())
    dark_ratio = sum(1 for p in pixels if p < 60) / len(pixels)
    bright_ratio = sum(1 for p in pixels if p > 200) / len(pixels)
    return {
        "brightness": brightness,
        "contrast": contrast,
        "edge_density": edge_density,
        "dark_ratio": dark_ratio,
        "bright_ratio": bright_ratio,
    }


def _room_from_pixels(features: dict) -> tuple[str, float]:
    brightness = features["brightness"]
    edge_density = features["edge_density"]
    dark_ratio = features["dark_ratio"]

    if brightness < 0.35 and edge_density > 0.12:
        return "bathroom", 0.45
    if dark_ratio > 0.25 and edge_density < 0.08:
        return "bedroom", 0.42
    if brightness > 0.65 and edge_density > 0.1:
        return "kitchen", 0.48
    if brightness > 0.55 and edge_density < 0.09:
        return "living room", 0.4
    if dark_ratio < 0.1 and brightness > 0.5:
        return "exterior", 0.38
    return "unknown", 0.25


def _condition_from_signals(features: dict, issues: list[str], text_conf: float) -> tuple[int, float]:
    damage_score = 0.0
    if any("leak" in i or "flood" in i or "mold" in i for i in issues):
        damage_score += 0.45
    if any("crack" in i or "broken" in i or "fire" in i for i in issues):
        damage_score += 0.35
    if features["dark_ratio"] > 0.3:
        damage_score += 0.15
    if features["edge_density"] > 0.18:
        damage_score += 0.1
    if features["contrast"] > 0.35:
        damage_score += 0.08

    damage_score = min(damage_score + (0.1 if text_conf > 0.6 else 0), 1.0)
    # 1 = poor condition, 5 = excellent
    condition_score = max(1, min(5, round(5 - damage_score * 4)))
    confidence = min(0.35 + damage_score * 0.4 + text_conf * 0.25, 0.92)
    if "inspection" in issues[0]:
        confidence = min(confidence, 0.5)
    return condition_score, confidence


def analyse_metadata_only(filename: str = "upload.jpg", description: str = "") -> dict:
    text_room, text_room_conf = _infer_room_from_text(filename, description)
    issues, keywords, issue_conf = _infer_issues(filename, description)
    condition_score, condition_conf = _condition_from_signals(
        {
            "brightness": 0.5,
            "contrast": 0.2,
            "edge_density": 0.1,
            "dark_ratio": 0.1,
            "bright_ratio": 0.1,
        },
        issues,
        issue_conf,
    )
    confidence = round((text_room_conf + condition_conf) / 2, 3)
    uncertain = confidence < CONFIDENCE_THRESHOLD
    room_type = text_room if text_room != "unknown" else "unknown"
    if uncertain:
        room_type = f"{room_type} (uncertain)" if room_type != "unknown" else "unknown (uncertain)"
    return {
        "room_type": room_type,
        "condition_score": condition_score,
        "confidence": confidence,
        "uncertain": uncertain,
        "detected_issues": "; ".join(issues),
        "keywords": keywords,
        "analysis_notes": "Metadata-only analysis (no image pixels supplied).",
        "pixel_features": {},
    }


def analyse_image_bytes(
    image_bytes: bytes,
    filename: str = "upload.jpg",
    description: str = "",
) -> dict:
    try:
        from pytorch_inference import predict_room

        pt = predict_room(image_bytes)
        if pt and not pt.get("uncertain"):
            issues, keywords, _ = _infer_issues(filename, description)
            return {
                **pt,
                "detected_issues": "; ".join(issues),
                "keywords": keywords,
                "analysis_notes": "PyTorch ResNet-18 room classification.",
                "pixel_features": {},
            }
    except Exception:
        pass

    text_room, text_room_conf = _infer_room_from_text(filename, description)
    issues, keywords, issue_conf = _infer_issues(filename, description)

    pixel_room = "unknown"
    pixel_room_conf = 0.0
    features = {
        "brightness": 0.5,
        "contrast": 0.2,
        "edge_density": 0.1,
        "dark_ratio": 0.1,
        "bright_ratio": 0.1,
    }
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.verify()
        with Image.open(io.BytesIO(image_bytes)) as img:
            features = _pixel_features(img)
            pixel_room, pixel_room_conf = _room_from_pixels(features)
    except Exception:
        pixel_room_conf = 0.1

    if text_room != "unknown" and text_room_conf >= pixel_room_conf:
        room_type = text_room
        room_confidence = text_room_conf
        room_source = "text_metadata"
    elif pixel_room != "unknown":
        room_type = pixel_room
        room_confidence = pixel_room_conf
        room_source = "pixel_heuristics"
    else:
        room_type = "unknown"
        room_confidence = 0.2
        room_source = "uncertain"

    condition_score, condition_conf = _condition_from_signals(features, issues, issue_conf)
    confidence = round((room_confidence + condition_conf) / 2, 3)
    uncertain = confidence < CONFIDENCE_THRESHOLD

    return {
        "room_type": room_type if not uncertain else f"{room_type} (uncertain)",
        "condition_score": condition_score,
        "confidence": confidence,
        "uncertain": uncertain,
        "detected_issues": "; ".join(issues),
        "keywords": keywords,
        "analysis_notes": (
            f"Pixel analysis: brightness={features['brightness']:.2f}, "
            f"edge_density={features['edge_density']:.2f}, "
            f"contrast={features['contrast']:.2f}. "
            f"Room inferred via {room_source}."
        ),
        "pixel_features": {k: round(v, 3) for k, v in features.items()},
    }
