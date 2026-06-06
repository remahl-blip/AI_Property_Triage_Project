import streamlit as st
import requests

st.set_page_config(
    page_title="Property Compliance & Triage Operations AI",
    page_icon="🏢",
    layout="wide"
)

st.title("🏢 Property Compliance & Triage AI Platform")
st.write("Real-time inspection analysis, automated guardrails, compliance tracking, and Agentic AI operations.")

# הגדרת כתובות ה-API של השירותים השונים בתוך רשת ה-Docker
ANALYSE_URL = "http://image_analyser:8002/analyse"
AGENT_URL = "http://property_agent:8004/chat"
HISTORY_URL = "http://property_triage:8003/history"

# חלוקת הממשק לשתי לשוניות (Tabs)
tab1, tab2 = st.tabs(["📸 Image Compliance Analysis", "💬 Operations AI Copilot"])

# -------------------------------------------------------------------
# לשונית 1: ניתוח תמונות וקומפליינס (הממשק המקורי)
# -------------------------------------------------------------------
with tab1:
    st.header("📸 Property Visual Inspection")
    st.subheader("Upload an inspection photo to evaluate safety and maintenance SLA")

    uploaded_file = st.file_uploader("Choose an inspection image...", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded Inspection Image", use_container_width=True)

        if st.button("🔥 Run Compliance & Triage Analysis", type="primary"):
            with st.spinner("Processing image and evaluating regulations..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    response = requests.post(ANALYSE_URL, files=files, timeout=15)

                    if response.status_code == 200:
                        result = response.json()

                        st.success("Analysis Completed Successfully!")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.subheader("Visual AI Insights (Layer 3)")
                            st.write(f"**Detected Room:** {result['image_analysis']['detected_room'].upper()}")
                            st.info(result['image_analysis']['analysis_notes'])

                        with col2:
                            st.subheader("Compliance & Triage Verdict (Layer 4)")
                            triage = result['triage_decision']
                            if "error" in triage:
                                st.error(triage["error"])
                            else:
                                st.write(f"**Priority:** {triage['priority']}")
                                st.write(f"**Compliance:** {triage['audit_report']['compliance_status']}")
                                st.write(f"**Required Action:** {triage['audit_report']['required_action']}")
                                st.metric(label="SLA Deadline", value=triage['audit_report']['sla_deadline'])
                                st.write(f"*Ticket Generated:* `{triage['audit_report']['ticket_id']}`")
                    else:
                        st.error(f"Error: Received status code {response.status_code} from Layer 3.")
                except Exception as e:
                    st.error(f"Failed to connect to backend services: {e}")

# -------------------------------------------------------------------
# לשונית 2: סוכן חכם אינטראקטיבי (LangGraph Copilot)
# -------------------------------------------------------------------
with tab2:
    st.header("💬 Property Operations Copilot")
    st.subheader("Talk to the intelligent Agent to search historical tickets or log issues manually")

    # אתחול היסטוריית הצ'אט ב-Session State של Streamlit
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # תצוגת היסטוריית השיחה
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # קבלת הודעה חדשה מהמשתמש
    if user_message := st.chat_input("Ask me about tickets, active issues, or log a new issue..."):
        # הצגת הודעת המשתמש במסך
        with st.chat_message("user"):
            st.write(user_message)

        # הוספה להיסטוריית ה-Session
        st.session_state.chat_history.append({"role": "user", "content": user_message})

        with st.spinner("Agent is thinking & running tools..."):
            try:
                # שליחת השאילתה וההיסטוריה לשירות ה-Agent (Layer 5)
                payload = {
                    "message": user_message,
                    "history": st.session_state.chat_history[:-1]
                }
                response = requests.post(AGENT_URL, json=payload, timeout=15)

                if response.status_code == 200:
                    reply = response.json()["reply"]

                    # הצגת הודעת הסוכן במסך
                    with st.chat_message("assistant"):
                        st.write(reply)

                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                else:
                    st.error(f"Agent service error: Status code {response.status_code}")
            except Exception as e:
                st.error(f"Failed to connect to LangGraph Agent: {e}")

# -------------------------------------------------------------------
# אזור ה-Dashboard: הצגת היסטוריית דיווחים מטבלת PostgreSQL
# -------------------------------------------------------------------
st.markdown("---")
st.header("📋 Audit History Dashboard")
st.subheader("All historical property compliance reports saved in PostgreSQL")

try:
    response = requests.get(HISTORY_URL, timeout=5)
    if response.status_code == 200:
        history_data = response.json()

        if history_data:
            import pandas as pd

            df = pd.DataFrame(history_data)
            df.columns = [
                "Ticket ID", "Timestamp", "Room Type", "Category",
                "Priority", "Regulation Code", "Compliance Status", "SLA Deadline"
            ]
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No reports found in the database yet. Run your first analysis above!")
    else:
        st.error(f"Could not load history from Layer 4. Status code: {response.status_code}")
except Exception as e:
    st.info("🔄 Dashboard is loading... Waiting for background services to sync.")