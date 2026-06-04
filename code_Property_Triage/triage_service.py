import uuid
import os
import csv
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Property Compliance & Triage AI Service (Layer 4)")

# נתיב לקובץ הלוגים בתוך הקונטיינר (נחבר אותו לתיקייה אמיתית במחשב בשלב הבא)
LOG_FILE_PATH = "/app/logs/compliance_audit_log.csv"

COMPLIANCE_DATABASE = {
    "fire_and_life_safety": {
        "keywords": ["fire", "smoke", "gas", "exposed wires", "נזילה", "פיצוץ", "أسلاك", "غاز", "حريق"],
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


def init_audit_log():
    """יצירת קובץ ה-CSV עם כותרות אם הוא עדיין לא קיים"""
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    if not os.path.exists(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(
                ["Ticket ID", "Timestamp", "Room Type", "Category", "Priority", "Regulation Code", "Status", "SLA"])


def log_audit_to_csv(ticket_id, timestamp, room, category, priority, reg_code, status, sla):
    """כתיבת שורת דוח חדשה לקובץ ה-CSV"""
    with open(LOG_FILE_PATH, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([ticket_id, timestamp, room, category, priority, reg_code, status, sla])


# אתחול הקובץ בעת עליית השרת
init_audit_log()


@app.post("/triage", response_model=TriageResponse)
def evaluate_compliance_and_triage(request: TriageRequest):
    room = request.room_type.lower()
    description = request.condition_description.lower()

    detected_category = "standard_operational"
    matched_rule = COMPLIANCE_DATABASE["standard_operational"]
    compliance_status = "Compliant - Low Risk"

    for category, rule in COMPLIANCE_DATABASE.items():
        if any(keyword in description for keyword in rule["keywords"]):
            detected_category = category
            matched_rule = rule
            compliance_status = f"Non-Compliant ({rule['priority']} Risk)"
            break

    ticket_id = f"TICK-{uuid.uuid4().hex[:8].upper()}"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sla_text = f"Within {matched_rule['sla_hours']} hours"

    # פקודת השמירה החדשה לקובץ!
    log_audit_to_csv(
        ticket_id, current_time, room, detected_category,
        matched_rule["priority"], matched_rule["regulation_code"],
        compliance_status, sla_text
    )

    audit_report = {
        "ticket_id": ticket_id,
        "timestamp": current_time,
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