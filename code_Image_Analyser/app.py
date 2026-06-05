import os
from fastapi import FastAPI, File, UploadFile
import requests

app = FastAPI(title="Image Analyser Service (Layer 3)")

TRIAGE_SERVICE_URL = "http://property_triage:8003/triage"

@app.post("/analyse")
async def analyse_image(file: UploadFile = File(...)):
    detected_room = "kitchen"

    # 1. יצירת הערות הניתוח המקוריות
    analysis_notes = f"Detected potential issue in {detected_room} based on offline image analysis."

    # 2. הזרקת הליקוי עבור בדיקת ה-SLA של ה-12 שעות וה-Guardrail
    if detected_room == "kitchen":
        analysis_notes += " יש נזילה מהכיור"

    # 3. בניית ה-Payload
    triage_payload = {
        "room_type": detected_room,
        "condition_description": analysis_notes
    }

    # 4. קריאה פנימית לשירות ה-Triage ברשת של דוקר
    try:
        triage_response = requests.post(
            TRIAGE_SERVICE_URL,
            json=triage_payload,
            timeout=10
        )
        if triage_response.status_code == 200:
            triage_data = triage_response.json()
        else:
            triage_data = {"error": f"Layer 4 returned status code {triage_response.status_code}"}
    except Exception as e:
        triage_data = {"error": f"Failed to connect to Layer 4: {e}"}

    return {
        "image_analysis": {
            "processed_file": file.filename,
            "detected_room": detected_room,
            "analysis_notes": analysis_notes
        },
        "triage_decision": triage_data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)