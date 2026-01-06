import os
import streamlit as st
from datetime import datetime

from scraper.moodle_scraper import MoodleScraper
from analytics.metrics import calculate_analytics

# ==========================================
# STREAMLIT CONFIG
# ==========================================

st.set_page_config(page_title="CodeRunner Dash", layout="wide")

if 'raw_data' not in st.session_state:
    st.session_state.raw_data = None

if 'last_sync' not in st.session_state:
    st.session_state.last_sync = None

# ==========================================
# UI
# ==========================================

st.title("📊 CodeRunner Monitoring System")

with st.sidebar:
    st.header("Settings")
    u_val = st.text_input("User", value=os.getenv("MOODLE_USER", ""))
    p_val = st.text_input("Pass", type="password", value=os.getenv("MOODLE_PASS", ""))
    q_val = st.text_input("Quiz ID", value=os.getenv("MOODLE_QUIZ_ID", "958257"))

    if st.button("🚀 Sync Now"):
        st.session_state.raw_data = "loading"

# ==========================================
# FETCH
# ==========================================

if st.session_state.raw_data == "loading":
    with st.status("Syncing with Moodle...", expanded=True) as status:
        scr = MoodleScraper(u_val, p_val)
        data = scr.run(q_val, status)
        scr.close()

        if data:
            st.session_state.raw_data = data
            st.session_state.last_sync = datetime.now().strftime('%H:%M:%S')
            st.rerun()
        else:
            st.session_state.raw_data = None
            status.update(label="No data found.", state="error")

# ==========================================
# DISPLAY
# ==========================================

if isinstance(st.session_state.raw_data, list):
    df, errors = calculate_analytics(st.session_state.raw_data)

    m1, m2, m3 = st.columns(3)
    m1.metric("Students", len(df))
    m2.metric("Total Submissions", int(df.filter(like="Attempts").sum().sum()))
    m3.metric("Last Sync", st.session_state.last_sync)

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Success Distribution")
        st.bar_chart(
            df.filter(like="(%)")
            .mean(axis=1)
            .value_counts()
            .sort_index()
        )

    with c2:
        st.subheader("Top Roadblocks")
        if not errors.empty:
            st.bar_chart(errors.head(10))
        else:
            st.success("Everything passing!")

    st.subheader("Progress Matrix")
    st.dataframe(
        df.set_index("Student")
        .filter(like="(%)")
        .style.background_gradient(
            cmap="RdYlGn",
            vmin=0,
            vmax=100
        ),
        width=True
    )

else:
    st.info("Fill credentials and click 'Sync Now'.")
