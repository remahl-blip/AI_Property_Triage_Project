import os

import io
import json
from fastapi import FastAPI, File, UploadFile
import requests
import google.generativeai as genai
from PIL import Image

app = FastAPI(title="Image Analyser Service (Layer 3)")

# הגדרת מפתח ה-API של Gemini מתוך משתני הסביבה
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

TRIAGE_SERVICE_URL = "http://property_triage:8003/triage"


@app.post("/analyse")
async def analyse_image(file: UploadFile = File(...)):
    try:
        # 1. קריאת קובץ התמונה והפיכתו לאובייקט ש-PIL מבין
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))

        # 2. פנייה למודל Gemini 1.5 Flash לקבלת JSON מובנה
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = (
            "You are an expert property inspection and compliance AI.\n"
            "Analyze this image carefully and detect the room type and any visible maintenance issues, property damage, "
            "or safety hazards like water leaks, mold, structural cracks, exposed wires, or broken items.\n\n"
            "Provide your response strictly in a valid JSON format with the following keys. Do not include markdown code block syntax:\n"
            "{\n"
            '  "room_type": "kitchen",\n'
            '  "detected_issues": "detailed description of issues in English",\n'
            '  "keywords": ["leak", "crack", "mold", "נזילה", "עובש"]\n'
            "}"
        )

        response = model.generate_content([prompt, image])

        # ניקוי תגיות קוד פוטנציאליות מהתשובה של המודל
        clean_text = response.text.replace("```json", "").replace("```", "").strip()

        # המרת תשובת השרת לאובייקט דיקשנרי של פייתון
        ai_data = json.loads(clean_text)

        detected_room = ai_data.get("room_type", "unknown")
        detected_issues = ai_data.get("detected_issues", "")
        keywords_list = ai_data.get("keywords", [])

        # חיבור מילות המפתח יחד עם התיאור עבור שירות ה-Triage
        keywords_str = " ".join(keywords_list)
        final_description = f"{detected_issues} | Keywords: {keywords_str}"

    except Exception as e:
        print(f"Gemini API or Parsing Error: {e}")
        detected_room = "unknown"
        final_description = "Failed to parse real-time AI analysis. Check image visibility and API keys."

    # 3. בניית ה-Payload ושליחה לשכבה 4 (Property Triage)
    triage_payload = {
        "room_type": detected_room,
        "condition_description": final_description
    }

    try:
        triage_response = requests.post(TRIAGE_SERVICE_URL, json=triage_payload, timeout=10)
        triage_data = triage_response.json() if triage_response.status_code == 200 else {
            "error": f"Layer 4 error: {triage_response.status_code}"}
    except Exception as e:
        triage_data = {"error": f"Failed to connect to Layer 4: {e}"}

    return {
        "image_analysis": {
            "processed_file": file.filename,
            "detected_room": detected_room,
            "analysis_notes": final_description
        },
        "triage_decision": triage_data
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)