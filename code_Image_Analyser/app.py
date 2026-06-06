import json
import os
from fastapi import FastAPI, File, Form, UploadFile
import requests

app = FastAPI(title="Image Analyser Service (Layer 3)")

TRIAGE_SERVICE_URL = os.getenv("TRIAGE_SERVICE_URL", "http://property_triage:8003/triage")

ROOM_HINTS = {
    "kitchen": ("kitchen", "מטבח"),
    "bathroom": ("bathroom", "שירותים", "אמבטיה", "shower"),
    "bedroom": ("bedroom", "חדר שינה"),
    "living room": ("living", "סלון", "lounge"),
    "hallway": ("hallway", "מסדרון", "corridor"),
    "exterior": ("exterior", "outside", "facade", "חוץ"),
}

ISSUE_HINTS = {
    "leak": ("leak", "נזילה", "drip", "water damage"),
    "flood": ("flood", "הצפה", "flooding"),
    "mold": ("mold", "עובש", "mildew"),
    "crack": ("crack", "סדק", "fracture"),
    "fire": ("fire", "smoke", "gas", "חשמל", "wires"),
    "broken": ("broken", "שבור", "damage", "damaged"),
}


def infer_room_type(*texts: str) -> str:
    combined = " ".join(texts).lower()
    for room, hints in ROOM_HINTS.items():
        if any(hint in combined for hint in hints):
            return room
    return "unknown"


def infer_issues(*texts: str) -> tuple[list[str], list[str]]:
    combined = " ".join(texts).lower()
    issues = []
    keywords = []
    for label, hints in ISSUE_HINTS.items():
        if any(hint in combined for hint in hints):
            issues.append(f"{label} detected")
            keywords.append(label)
    if not issues:
        issues.append("routine maintenance inspection")
        keywords.append("inspection")
    return issues, keywords


def analyse_metadata(filename: str, description: str = "") -> dict:
    room = infer_room_type(filename, description)
    issues, keywords = infer_issues(filename, description)
    return {
        "room_type": room,
        "detected_issues": "; ".join(issues),
        "keywords": keywords,
        "analysis_notes": (
            f"Layer 3 analysis from image metadata and description. "
            f"Filename: {filename or 'uploaded_image'}"
        ),
    }


@app.post("/analyse")
async def analyse_image(
    file: UploadFile = File(...),
    condition_description: str = Form(default=""),
):
    filename = file.filename or "inspection.jpg"
    await file.read()

    analysis = analyse_metadata(filename, condition_description)
    detected_room = analysis["room_type"]
    keywords_str = " ".join(analysis["keywords"])
    final_description = f"{analysis['detected_issues']} | Keywords: {keywords_str}"
    if condition_description.strip():
        final_description = f"{condition_description.strip()} | {final_description}"

    triage_payload = {
        "room_type": detected_room,
        "condition_description": final_description,
    }

    try:
        triage_response = requests.post(TRIAGE_SERVICE_URL, json=triage_payload, timeout=10)
        triage_data = (
            triage_response.json()
            if triage_response.status_code == 200
            else {"error": f"Layer 4 error: {triage_response.status_code}"}
        )
    except Exception as exc:
        triage_data = {"error": f"Failed to connect to Layer 4: {exc}"}

    return {
        "image_analysis": {
            "processed_file": filename,
            "detected_room": detected_room,
            "analysis_notes": analysis["analysis_notes"],
            "condition_description": final_description,
        },
        "triage_decision": triage_data,
    }


@app.get("/health")
def health():
    return {"status": "ok", "layer": 3}
