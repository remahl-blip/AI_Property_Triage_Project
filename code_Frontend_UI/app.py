import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Property Triage - Layers 3 & 4",
    page_icon="🏢",
    layout="wide",
)

st.title("🏢 Property Triage System")
st.write("**Layer 3:** Image metadata analysis → **Layer 4:** Compliance triage and SLA routing")
st.info("Runs locally with Docker. No API keys required.")

ANALYSE_URL = "http://image_analyser:8002/analyse"
HISTORY_URL = "http://property_triage:8003/history"

st.header("📸 Submit inspection")
uploaded_file = st.file_uploader("Upload image (jpg/png)", type=["jpg", "jpeg", "png"])
condition_description = st.text_input(
    "Condition description (recommended)",
    placeholder="e.g. severe water leak near the kitchen sink",
)

if uploaded_file and st.button("Run Layer 3 + 4 Analysis", type="primary"):
    with st.spinner("Analysing and triaging..."):
        try:
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            data = {"condition_description": condition_description}
            response = requests.post(ANALYSE_URL, files=files, data=data, timeout=15)

            if response.status_code != 200:
                st.error(f"Layer 3 returned status {response.status_code}")
            else:
                result = response.json()
                st.success("Pipeline completed")

                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Layer 3 - Image Analysis")
                    img = result["image_analysis"]
                    st.write(f"**Room:** {img['detected_room']}")
                    st.write(f"**Notes:** {img['analysis_notes']}")
                    st.write(f"**Description sent to triage:** {img['condition_description']}")

                with col2:
                    st.subheader("Layer 4 - Triage Decision")
                    triage = result["triage_decision"]
                    if "error" in triage:
                        st.error(triage["error"])
                    else:
                        st.write(f"**Priority:** {triage['priority']}")
                        st.write(f"**Category:** {triage['category']}")
                        st.write(f"**Summary:** {triage['summary']}")
                        report = triage["audit_report"]
                        st.metric("SLA Deadline", report["sla_deadline"])
                        st.write(f"**Ticket:** `{report['ticket_id']}`")
                        st.write(f"**Action:** {report['required_action']}")
        except Exception as exc:
            st.error(f"Could not reach services: {exc}")
            st.caption("Run: docker compose up --build")

st.markdown("---")
st.header("📋 Triage history (PostgreSQL)")
try:
    history_response = requests.get(HISTORY_URL, timeout=5)
    if history_response.status_code == 200:
        history = history_response.json()
        if history:
            df = pd.DataFrame(history)
            df.columns = [
                "Ticket ID", "Timestamp", "Room", "Category",
                "Priority", "Regulation", "Compliance", "SLA",
            ]
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No tickets yet. Run an analysis above.")
    else:
        st.warning(f"History unavailable (status {history_response.status_code})")
except Exception:
    st.info("History service is starting... refresh in a few seconds.")
