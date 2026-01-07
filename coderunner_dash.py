"""
Streamlit Dashboard for CodeRunner Quiz Monitoring
==================================================

This is the main entry point for the CodeRunner Dash application. It provides a
web-based dashboard to visualize student performance on Moodle CodeRunner quizzes.

The dashboard allows users to:
    - Authenticate with Moodle credentials
    - Fetch quiz data for a given quiz ID
    - View aggregated metrics and visualizations
    - Identify common failure patterns
"""
import pickle

TESTING = True

import os
import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
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

    # --- AUTO REFRESH LOGIC ---
    st.divider()
    st.subheader("Auto Update")
    refresh_minutes = st.slider("Interval (minutes)", min_value=2, max_value=10, value=5)

    # --- TESTING ---
    if TESTING:
        st.divider()
        if st.button("📂 Load Local Cache"):
            if os.path.exists("tests/quiz_cache.pkl"):
                with open("tests/quiz_cache.pkl", "rb") as f:
                    st.session_state.raw_data = pickle.load(f)
                    st.session_state.last_sync = "Local Cache"
                st.success("Loaded from disk!")
                st.rerun()
            else:
                st.error("Cache file not found.")

    refresh_count = st_autorefresh(interval=refresh_minutes * 60 * 1000, key="moodle_auto_sync")

    if 'last_auto_refresh' not in st.session_state:
        st.session_state.last_auto_refresh = 0

    if refresh_count > st.session_state.last_auto_refresh:
        st.session_state.last_auto_refresh = refresh_count
        st.session_state.raw_data = "loading"

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
        st.bar_chart(df.filter(like="(%)").mean(axis=1).value_counts().sort_index())
    with c2:
        st.subheader("Top Roadblocks")
        if not errors.empty:
            st.bar_chart(errors.head(10))

    st.divider()
    st.header("🔍 Detailed Test Case Status")

    # Obtemos o número de questões a partir do primeiro aluno
    if st.session_state.raw_data:
        num_questions = len(st.session_state.raw_data[0].questions)

        for q_idx in range(num_questions):
            q_label = f"Question {q_idx + 1}"

            with st.expander(f"Status: {q_label}", expanded=True):
                test_data = {}
                max_tests = 0

                # Primeiro, descobrimos o maior número de casos de teste nesta questão
                # entre todos os alunos para evitar o ValueError
                for user in st.session_state.raw_data:
                    max_tests = max(max_tests, len(user.questions[q_idx].test_results))

                for user in st.session_state.raw_data:
                    q_data = user.questions[q_idx]
                    icons = []

                    for i in range(max_tests):
                        # Se o aluno tem esse caso de teste, usamos o ícone correspondente
                        if i < len(q_data.test_results):
                            icons.append("🟢" if q_data.test_results[i].passed else "🔴")
                        else:
                            # Se o aluno não tem esse teste (ex: não submeteu), usamos um símbolo neutro
                            icons.append("⚪")

                    test_data[user.username] = icons

                if test_data and max_tests > 0:
                    test_df = pd.DataFrame(test_data)
                    test_df.index = [f"Test Case {i+1}" for i in range(len(test_df))]

                    st.dataframe(
                        test_df,
                        width=True
                    )
                else:
                    st.info(f"No submission data available for {q_label}")

else:
    st.info("Fill credentials and click 'Sync Now'.")