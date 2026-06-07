import json
from pathlib import Path

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
LISTINGS_PATH = Path(__file__).with_name("listings.json")


@st.cache_data
def load_listings():
    try:
        with open(LISTINGS_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        st.error(f"Could not load listings.json: {exc}")
        return []


triage_tab, search_tab = st.tabs(["🛠️ Triage pipeline", "🏠 חיפוש דירות"])

with triage_tab:
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


with search_tab:
    st.header("🏠 חיפוש דירות")
    listings = load_listings()

    if not listings:
        st.warning("אין נתוני דירות זמינים (listings.json ריק או חסר).")
    else:
        df = pd.DataFrame(listings)

        DEAL_LABELS = {"sale": "מכירה", "rent": "השכרה"}
        TYPE_LABELS = {
            "apartment": "דירה",
            "villa": "וילה",
            "penthouse": "פנטהאוז",
            "studio": "סטודיו",
            "duplex": "דופלקס",
            "cottage": "קוטג'",
        }

        with st.sidebar:
            st.subheader("🔎 סינון דירות")

            query = st.text_input("חיפוש חופשי", placeholder="עיר, שכונה, מאפיין...")

            cities = sorted(df["city"].dropna().unique().tolist())
            selected_cities = st.multiselect("עיר", cities)

            deals = sorted(df["deal"].dropna().unique().tolist())
            selected_deals = st.multiselect(
                "סוג עסקה",
                deals,
                format_func=lambda d: DEAL_LABELS.get(d, d),
            )

            types = sorted(df["property_type"].dropna().unique().tolist())
            selected_types = st.multiselect(
                "סוג נכס",
                types,
                format_func=lambda t: TYPE_LABELS.get(t, t),
            )

            room_min = int(df["rooms"].min())
            room_max = int(df["rooms"].max())
            if room_min < room_max:
                rooms_range = st.slider(
                    "חדרים", room_min, room_max, (room_min, room_max)
                )
            else:
                rooms_range = (room_min, room_max)

            price_min = int(df["price"].min())
            price_max = int(df["price"].max())
            if price_min < price_max:
                price_range = st.slider(
                    "מחיר (₪)", price_min, price_max, (price_min, price_max), step=10000
                )
            else:
                price_range = (price_min, price_max)

        mask = pd.Series(True, index=df.index)

        if selected_cities:
            mask &= df["city"].isin(selected_cities)
        if selected_deals:
            mask &= df["deal"].isin(selected_deals)
        if selected_types:
            mask &= df["property_type"].isin(selected_types)

        mask &= df["rooms"].between(rooms_range[0], rooms_range[1])
        mask &= df["price"].between(price_range[0], price_range[1])

        if query:
            q = query.strip()

            def matches(row):
                haystack = " ".join([
                    str(row.get("title", "")),
                    str(row.get("city", "")),
                    str(row.get("neighborhood", "")),
                    str(row.get("description", "")),
                    " ".join(row.get("features", []) or []),
                ])
                return q in haystack

            mask &= df.apply(matches, axis=1)

        results = df[mask]

        st.caption(f"נמצאו {len(results)} דירות מתוך {len(df)}")

        if results.empty:
            st.info("לא נמצאו דירות התואמות את הסינון.")
        else:
            for _, row in results.iterrows():
                deal_label = DEAL_LABELS.get(row["deal"], row["deal"])
                type_label = TYPE_LABELS.get(row["property_type"], row["property_type"])
                with st.container(border=True):
                    top, side = st.columns([3, 1])
                    with top:
                        st.subheader(row["title"])
                        st.write(
                            f"📍 {row['city']} · {row.get('neighborhood', '')} "
                            f"| {type_label} | {deal_label}"
                        )
                        st.write(row.get("description", ""))
                        features = row.get("features") or []
                        if features:
                            st.write(" ".join(f"`{f}`" for f in features))
                    with side:
                        st.metric("מחיר", f"₪{int(row['price']):,}")
                        st.write(f"🛏️ {int(row['rooms'])} חדרים")
                        st.write(f"📐 {int(row['size_sqm'])} מ\"ר")

            st.markdown("---")
            st.subheader("📊 טבלת תוצאות")
            table = results.copy()
            table["deal"] = table["deal"].map(lambda d: DEAL_LABELS.get(d, d))
            table["property_type"] = table["property_type"].map(
                lambda t: TYPE_LABELS.get(t, t)
            )
            table["features"] = table["features"].map(
                lambda fs: ", ".join(fs) if isinstance(fs, list) else fs
            )
            display_cols = {
                "id": "מזהה",
                "title": "כותרת",
                "city": "עיר",
                "neighborhood": "שכונה",
                "property_type": "סוג נכס",
                "deal": "עסקה",
                "rooms": "חדרים",
                "size_sqm": 'מ"ר',
                "price": "מחיר",
                "features": "מאפיינים",
            }
            available = [c for c in display_cols if c in table.columns]
            st.dataframe(
                table[available].rename(columns=display_cols),
                use_container_width=True,
                hide_index=True,
            )
