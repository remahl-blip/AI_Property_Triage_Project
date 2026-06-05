import os
from fastapi import FastAPI, File, UploadFile
import requests

app = FastAPI(title="Image Analyser Service (Layer 3)")

# כתובת השירות של Layer 4 בתוך הרשת הפנימית של Docker
TRIAGE_SERVICE_URL = "http://property_triage:8003/triage"


# בתוך code_Image_Analyser/main.py

@app.post("/analyse")
async def analyse_image(file: UploadFile = File(...)):
    # ... קוד זיהוי התמונה הקיים שלכם שמזהה את סוג החדר ...
    detected_room = "kitchen"  # (או הלוגיקה הקיימת שמחזירה את סוג החדר)

    # 1. יצירת הערות הניתוח המקוריות שלכם
    analysis_notes = f"Detected potential issue in {detected_room} based on offline image analysis."

    # 2. הזרקת הליקוי באופן יזום בשביל בדיקת ה-SLA וה-Guardrail!
    if detected_room == "kitchen":
        analysis_notes += " יש נזילה מהכיור"

    # 3. בניית ה-Payload שנשלח לשירות ה-Triage (Layer 4)
    triage_payload = {
        "room_type": detected_room,
        "condition_description": analysis_notes
    }

    # 4. הקריאה הפנימית לשירות ה-Triage שלכם
    try:
        triage_response = requests.post(
            "http://property_triage:8003/triage",
            json=triage_payload,
            timeout=10
        )
        triage_data = triage_response.json()
    except Exception as e:
        triage_data = {"error": f"Failed to connect to Layer 4: {e}"}

    # 5. החזרת התשובה המשולבת ל-UI
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