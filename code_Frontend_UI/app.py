import streamlit as st
import requests

# הגדרות עמוד ראשיות
st.set_page_config(page_title="AI Property Triage Dashboard", page_icon="🏢", layout="wide")

IMAGE_ANALYSER_URL = "http://image_analyser:8002/analyse"

st.title("🏢 AI Property Triage & Compliance Dashboard")
st.markdown("Upload a property inspection image to run real-time AI analysis and compliance routing.")

st.sidebar.header("System Status")
st.sidebar.success("Layer 3: Connected")
st.sidebar.success("Layer 4: Connected")
st.sidebar.info("Logs: Active (CSV Shared Volume)")

# אזור העלאת הקובץ
uploaded_file = st.file_uploader("Choose an inspection image...", type=["jpg", "jpeg", "png", "jfif"])

if uploaded_file is not None:
    # הצגת התמונה שנבחרה על המסך
    st.image(uploaded_file, caption="Uploaded Inspection Image", width=400)

    # -------------------------------------------------------------
    # הוספת תיבת הקלט החדשה עבור ה-Input Guardrail ו-Layer 4
    # -------------------------------------------------------------
    condition_description = st.text_input(
        "תיאור הליקוי / Condition Description",
        value="יש נזילה מהכיור"  # ברירת מחדל מוכנה לבדיקה מהירה
    )

    # כפתור ההרצה הקיים שלך (יופעל כעת יחד עם התיאור שהוזן)
    if st.button("Run AI Triage Analysis", type="primary"):
        with st.spinner("Processing image and evaluating compliance regulations..."):
            try:
                # הכנת הקובץ והנתונים הנוספים (תיאור הליקוי) למשלוח ב-POST API
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}

                # שולחים את תיאור הליקוי כפרמטר (data) יחד עם קובץ התמונה
                data_payload = {"condition_description": condition_description}

                response = requests.post(IMAGE_ANALYSER_URL, files=files, data=data_payload, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    st.success("Analysis Completed Successfully!")

                    # חלוקת המסך ל-2 טורים להצגת הנתונים
                    col1, col2 = st.columns(2)

                    with col1:
                        st.subheader("📸 Image Analysis (Layer 3)")
                        st.json(data.get("image_analysis", {}))

                    with col2:
                        st.subheader("⚖️ Compliance & Triage (Layer 4)")
                        triage = data.get("triage_decision", {})

                        if "error" in triage:
                            st.error(f"Layer 4 Error: {triage['error']}")
                        else:
                            priority = triage.get("priority", "Medium")

                            # עיצוב צבעוני דינמי לפי רמת הדחיפות
                            if priority == "Emergency":
                                st.error(f"🚨 PRIORITY: {priority}")
                            elif priority == "High":
                                st.warning(f"⚠️ PRIORITY: {priority}")
                            else:
                                st.info(f"ℹ️ PRIORITY: {priority}")

                            st.write(f"**Category:** {triage.get('category')}")
                            st.write(f"**Summary:** {triage.get('summary')}")

                            # הצגת דוח ה-Audit המלא בצורה בטוחה ומפוצלת
                            report = triage.get("audit_report", {})
                            st.markdown("### 📄 Audit Ticket Details")

                            ticket_id = report.get('ticket_id', 'N/A')
                            timestamp = report.get('timestamp', 'N/A')
                            reg_code = report.get('regulation_code', 'N/A')
                            status = report.get('compliance_status', 'N/A')
                            sla = report.get('sla_deadline', 'N/A')
                            action = report.get('required_action', 'N/A')

                            st.markdown(f"- **Ticket ID:** `{ticket_id}`")
                            st.markdown(f"- **Timestamp:** {timestamp}")
                            st.markdown(f"- **Regulation Code:** `{reg_code}`")
                            st.markdown(f"- **Compliance Status:** {status}")
                            st.markdown(f"- **SLA Deadline:** **{sla}**")
                            st.markdown(f"- **Action Required:** *{action}*")

                # טיפול במצב שבו ה-Guardrail מחזיר שגיאה מהשרת (כמו שגיאה 400 קלט לא תקין)
                elif response.status_code == 400:
                    error_detail = response.json().get("detail", "Blocked by Guardrail")
                    st.error(f"🛡️ Guardrail Alert: {error_detail}")
                else:
                    st.error(f"Server returned status code {response.status_code}")

            except requests.exceptions.RequestException as e:
                st.error(f"Could not connect to the backend services: {e}")

# -------------------------------------------------------------------
# אזור ה-Dashboard: הצגת היסטוריית דיווחים מטבלת PostgreSQL
# -------------------------------------------------------------------
st.markdown("---")
st.header("📋 Audit History Dashboard")
st.subheader("All historical property compliance reports saved in PostgreSQL")

HISTORY_URL = "http://property_triage:8003/history"

try:
    response = requests.get(HISTORY_URL, timeout=5)
    if response.status_code == 200:
        history_data = response.json()

        if history_data:
            import pandas as pd

            df = pd.DataFrame(history_data)

            # שינוי שמות העמודות לתצוגה יפה
            df.columns = [
                "Ticket ID", "Timestamp", "Room Type", "Category",
                "Priority", "Regulation Code", "Compliance Status", "SLA Deadline"
            ]

            st.dataframe(df, use_container_width=True)
        else:
            st.info("No reports found in the database yet. Run your first analysis above!")
    else:
        # תיקון: שימוש נכון ב-st.error בלי פרמטרים שגויים
        st.error(f"Could not load history from Layer 4. Status code: {response.status_code}")
except Exception as e:
    # הודעה ידידותית בזמן שהדוקר מסתנכרן ברקע
    st.info("🔄 Dashboard is loading... Waiting for background services to sync.")