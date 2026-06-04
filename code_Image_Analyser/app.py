import os
from fastapi import FastAPI, File, UploadFile
import requests

app = FastAPI(title="Image Analyser Service (Layer 3)")

# כתובת השירות של Layer 4 בתוך הרשת הפנימית של Docker
TRIAGE_SERVICE_URL = "http://property_triage:8003/triage"


@app.post("/analyse")
async def analyse_image(file: UploadFile = File(...)):
    # הפיכת שם הקובץ לאותיות קטנות
    filename = file.filename.lower()

    # 1. לוגיקת הניתוح המקומית (ה-Fallback החכם)
    if "kitchen" in filename or "sink" in filename:
        room_type = "kitchen"
        condition_description = "Detected potential issue in kitchen based on offline image analysis."
    elif "bathroom" in filename or "shower" in filename or "toilet" in filename:
        room_type = "bathroom"
        condition_description = "Detected potential issue in bathroom based on offline image analysis."
    elif "bedroom" in filename or "bed" in filename:
        room_type = "bedroom"
        condition_description = "Detected potential issue in bedroom based on offline image analysis."
    else:
        room_type = "unknown_zone"
        condition_description = f"General property maintenance reported via file: {filename}"

    # 2. פנייה לשירות הטריאז' (Layer 4)
    payload = {
        "room_type": room_type,
        "condition_description": condition_description
    }

    triage_result = {}
    try:
        # פנייה פנימית בתוך רשת הדוקר
        response = requests.post(TRIAGE_SERVICE_URL, json=payload, timeout=5)
        # תיקון תקלדה: שימוש ב-status_code התקני של ספריית requests
        if response.status_code == 200:
            triage_result = response.json()
        else:
            triage_result = {
                "error": f"Layer 4 returned an error status: {response.status_code}",
                "raw_response": response.text
            }
    except requests.exceptions.RequestException as e:
        triage_result = {
            "error": "Could not connect to Layer 4 container",
            "details": str(e)
        }

    # 3. החזרת תשובה משולבת ומלאה
    return {
        "image_analysis": {
            "processed_file": file.filename,
            "detected_room": room_type,
            "analysis_notes": condition_description
        },
        "triage_decision": triage_result
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)