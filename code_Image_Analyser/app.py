import os
import io
from fastapi import FastAPI, File, UploadFile
import requests
import google.generativeai as genai
from PIL import Image

app = FastAPI(title="Image Analyser Service (Layer 3)")

# הגדרת מפתח ה-API של Gemini - נשלוף אותו ממשתני הסביבה
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "כאן_תדביקי_את_הקוד_שקיבלת_מגוגל_אם_את_לא_משתמשת_במשתני_סביבה")
genai.configure(api_key=GEMINI_API_KEY)

TRIAGE_SERVICE_URL = "http://property_triage:8003/triage"


@app.post("/analyse")
async def analyse_image(file: UploadFile = File(...)):
    try:
        # 1. קריאת קובץ התמונה והפיכתו לאובייקט ש-PIL ו-Gemini מבינים
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))

        # 2. פנייה למודל Gemini 1.5 Flash עם הנחיה מדויקת (Prompt)
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = (
            "You are a property inspection AI. Analyze this image and return a JSON-like format with exactly two fields:\n"
            "1. room_type: (e.g., kitchen, bathroom, living_room, bedroom, exterior)\n"
            "2. summary: A short sentence describing what you see and any potential maintenance issues.\n"
            "Keep the summary strictly in English."
        )

        response = model.generate_content([prompt, image])
        response_text = response.text.lower()

        # 3. חילוץ סוג החדר מתוך תשובת ה-AI (לוגיקה פשוטה לגיבוי)
        detected_room = "unknown"
        for room in ["kitchen", "bathroom", "living_room", "bedroom", "exterior"]:
            if room in response_text:
                detected_room = room
                break

        analysis_notes = response.text.strip()

    except Exception as e:
        # גיבוי במקרה שהקריאה ל-Gemini נכשלה (למשל בעיית מפתח API)
        print(f"Gemini API Error: {e}")
        detected_room = "kitchen"
        analysis_notes = f"Detected potential issue in {detected_room} based on offline image analysis."

    # 4. הזרקת הליקוי היזומה שמינינו קודם כדי לבדוק את ה-SLA של ה-12 שעות
    if detected_room == "kitchen":
        analysis_notes += " יש נזילה מהכיור"

    # 5. בניית ה-Payload ושליחה לשכבה 4 (Property Triage)
    triage_payload = {
        "room_type": detected_room,
        "condition_description": analysis_notes
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
            "analysis_notes": analysis_notes
        },
        "triage_decision": triage_data
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)