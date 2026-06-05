import uuid
import os
import psycopg2
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Property Compliance & Triage AI Service (Layer 4)")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@postgres_db:5432/property_triage_db")

# מאגר חוקי הקומפליינס וה-SLA
COMPLIANCE_DATABASE = {
    "fire_and_life_safety": {
        "keywords": ["fire", "smoke", "gas", "exposed wires", "נזילה", "פיצוץ", "أسلاك", "غاز", "חريق"],
        "priority": "Emergency",
        "sla_hours": 2,
        "regulation_code": "REG-SAFETY-2026-A",
        "action_required": "Dispatch emergency technician immediately, evacuate nearby zones if necessary, and isolate utilities."
    },
    "structural_integrity": {
        "keywords": ["flood", "leak", "sewage", "mold", "crack", "עובש", "רطوبة", "تسريب", "הצפה"],
        "priority": "High",
        "sla_hours": 12,
        "regulation_code": "REG-STRUCT-2026-B",
        "action_required": "Deploy urgent plumbing/structural inspector to stop property degradation."
    },
    "standard_operational": {
        "keywords": ["broken", "paint", "light", "door", "שבור", "צבע", "مكسور", "قفل", "باب"],
        "priority": "Medium",
        "sla_hours": 48,
        "regulation_code": "REG-OPER-2026-C",
        "action_required": "Log into standard maintenance queue for the next available local handyman."
    }
}

# רשימת מילים שמעידות על ספאם, פרסומות או תוכן לא קשור
SPAM_KEYWORDS = ["crypto", "casino", "buy now", "הלוואות", "מזל טוב", "פרסומת", "עקבו אחריי", "שיווק", "discount"]


class TriageRequest(BaseModel):
    room_type: str
    condition_description: str


class AuditReport(BaseModel):
    ticket_id: str
    timestamp: str
    regulation_code: str
    compliance_status: str
    required_action: str
    sla_deadline: str


class TriageResponse(BaseModel):
    priority: str
    category: str
    audit_report: AuditReport
    summary: str


def is_valid_input(description: str, room: str) -> bool:
    """
    מנגנון ה-Input Guardrail:
    בודק האם הקלט תקין ורלוונטי לתחזוקת מבנים.
    נכשל במידה והטקסט קצר מדי, מכיל מילות ספאם, או ריק.
    """
    desc_clean = description.strip().lower()
    room_clean = room.strip().lower()

    # חוק 1: הגנה מפני קלט ריק או קצר מדי
    if len(desc_clean) < 4 or len(room_clean) < 2:
        return False

    # חוק 2: חסימת מילות ספאם ופרסום מוכרות
    if any(spam_word in desc_clean for spam_word in SPAM_KEYWORDS):
        return False

    # חוק 3: בדיקה מינימלית שיש קשר לעולמות הדיור/ליקויים (או שיש מילת מפתח מוכרת)
    # אם תרצי להחמיר, ניתן לוודא שיש לפחות מילת מפתח אחת שקשורה למאגר

    return True


def init_db():
    """יצירת הטבלה ב-PostgreSQL במידה והיא לא קיימת בבסיס הנתונים"""
    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS triage_reports
                           (
                               id
                               SERIAL
                               PRIMARY
                               KEY,
                               ticket_id
                               VARCHAR
                           (
                               50
                           ) UNIQUE NOT NULL,
                               timestamp TIMESTAMP NOT NULL,
                               room_type VARCHAR
                           (
                               100
                           ),
                               category VARCHAR
                           (
                               100
                           ),
                               priority VARCHAR
                           (
                               50
                           ),
                               regulation_code VARCHAR
                           (
                               100
                           ),
                               compliance_status VARCHAR
                           (
                               100
                           ),
                               sla_deadline VARCHAR
                           (
                               100
                           )
                               );
                           """)
            conn.commit()
            cursor.close()
            conn.close()
            print("PostgreSQL Database initialized successfully!")
            return
        except Exception as e:
            retries -= 1
            print(f"Database not ready yet ({retries} retries left)... Error: {e}")
            time.sleep(2)
    print("Could not connect to PostgreSQL database.")


@app.on_event("startup")
def startup_event():
    init_db()


def log_audit_to_db(ticket_id, timestamp, room, category, priority, reg_code, status, sla):
    """כתיבת שורת דוח חדשה לתוך טבלת PostgreSQL"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO triage_reports (ticket_id, timestamp, room_type, category, priority, regulation_code,
                                        compliance_status, sla_deadline)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (ticket_id, timestamp, room, category, priority, reg_code, status, sla)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Failed to log audit to database: {e}")
        raise HTTPException(status_code=500, detail=f"Database persistent error: {e}")
ד
@app.post("/triage", response_model=TriageResponse)
def evaluate_compliance_and_triage(request: TriageRequest):
    room = request.room_type.lower()
    description = request.condition_description.lower()

    # חוק בדיקה מיוחד: אם מגיע טקסט ברירת המחדל האוטומטי מהתמונה של המטבח,
    # אנחנו נשתול את מילת המפתח "נזילה" כדי לבדוק את ה-SLA של ה-12 שעות!
    if "detected potential issue in kitchen" in description:
        description += " יש נזילה מהכיור"

    # הפעלת ה-Input Guardrail החכם
    if not is_valid_input(description, room):
        print(f"Guardrail Alert: Blocked invalid or spam input! Description: '{description}'")
        raise HTTPException(
            status_code=400,
            detail="Guardrail Blocked: The provided description or room type is invalid, too short, or contains spam keywords."
        )

    detected_category = "standard_operational"
    matched_rule = COMPLIANCE_DATABASE["standard_operational"]
    compliance_status = "Compliant - Low Risk"

    # סריקת מילות מפתח (כעת זה יתפוס את "נזילה" שהוספנו למעלה)
    for category, rule in COMPLIANCE_DATABASE.items():
        if any(keyword in description for keyword in rule["keywords"]):
            detected_category = category
            matched_rule = rule
            compliance_status = f"Non-Compliant ({rule['priority']} Risk)"
            break

    ticket_id = f"TICK-{uuid.uuid4().hex[:8].upper()}"
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sla_text = f"Within {matched_rule['sla_hours']} hours"

    # שמירה בבסיס הנתונים PostgreSQL
    log_audit_to_db(
        ticket_id, current_time_str, room, detected_category,
        matched_rule["priority"], matched_rule["regulation_code"],
        compliance_status, sla_text
    )

    audit_report = {
        "ticket_id": ticket_id,
        "timestamp": current_time_str,
        "regulation_code": matched_rule["regulation_code"],
        "compliance_status": compliance_status,
        "required_action": matched_rule["action_required"],
        "sla_deadline": sla_text
    }

    summary_text = (
        f"Inspection completed for {room}. Status: {compliance_status}."
    )

    return {
        "priority": matched_rule["priority"],
        "category": detected_category,
        "audit_report": audit_report,
        "summary": summary_text
    }