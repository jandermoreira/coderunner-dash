"""
Streamlit Dashboard for CodeRunner Quiz Monitoring
==================================================

This is the main entry point for the CodeRunner Dash application. It provides a
web-based dashboard to visualize student performance on Moodle CodeRunner quizzes.
"""

import os
import streamlit as st
import pandas as pd
import pickle
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
# UI - SIDEBAR
# ==========================================

st.title("📊 CodeRunner Monitoring System")

with st.sidebar:
    st.header("Settings")
    u_val = st.text_input("User", value=os.getenv("MOODLE_USER", ""))
    p_val = st.text_input("Pass", type="password", value=os.getenv("MOODLE_PASS", ""))
    q_val = st.text_input("Quiz ID", value=os.getenv("MOODLE_QUIZ_ID", "958257"))

    st.divider()

    # --- MOCK / CACHE LOGIC ---
    st.subheader("Local Data")
    if st.button("📂 Load Local Cache"):
        pickle_file = "tests/quiz_cache.pkl"
        if os.path.exists(pickle_file):
            with open(pickle_file, "rb") as f:
                st.session_state.raw_data = pickle.load(f)
                st.session_state.last_sync = f"Cache: {datetime.now().strftime('%H:%M:%S')}"
            st.success("Loaded from disk!")
            st.rerun()
        else:
            st.error("Cache file not found.")

    # --- AUTO REFRESH LOGIC ---
    st.divider()
    st.subheader("Auto Update")
    refresh_minutes = st.slider("Interval (minutes)", min_value=2, max_value=10, value=5)

    refresh_count = st_autorefresh(interval=refresh_minutes * 60 * 1000, key="moodle_auto_sync")

    if 'last_auto_refresh' not in st.session_state:
        st.session_state.last_auto_refresh = 0

    if refresh_count > st.session_state.last_auto_refresh:
        st.session_state.last_auto_refresh = refresh_count
        st.session_state.raw_data = "loading"

    if st.button("🚀 Sync Now"):
        st.session_state.raw_data = "loading"

# ==========================================
# DATA FETCHING
# ==========================================

if st.session_state.raw_data == "loading":
    with st.status("Syncing with Moodle...", expanded=True) as status:
        scr = MoodleScraper(u_val, p_val)
        data = scr.run(q_val, status)
        scr.close()

        if data:
            st.session_state.raw_data = data
            st.session_state.last_sync = datetime.now().strftime('%H:%M:%S')

            # Opcional: Salvar cache automaticamente após sync real
            with open("quiz_cache.pkl", "wb") as f:
                pickle.dump(data, f)

            st.rerun()
        else:
            st.session_state.raw_data = None
            status.update(label="No data found.", state="error")

# ==========================================
# DISPLAY LOGIC
# ==========================================

if isinstance(st.session_state.raw_data, list) and len(st.session_state.raw_data) > 0:
    # Processamento para métricas gerais (Lógica Original)
    df, errors = calculate_analytics(st.session_state.raw_data)

    # --- TOP METRICS ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Students", len(df))
    m2.metric("Total Submissions", int(df.filter(like="Attempts").sum().sum()))
    m3.metric("Last Sync", st.session_state.last_sync)

    # --- CHARTS ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Success Distribution")
        st.bar_chart(df.filter(like="(%)").mean(axis=1).value_counts().sort_index())

    with c2:
        st.subheader("Top Roadblocks")
        if not errors.empty:
            st.bar_chart(errors.head(10))
        else:
            st.success("Everything passing!")

    # --- NEW: TEST CASE GRID (DETAILED STATUS) ---
    st.divider()
    st.header("🔍 Detailed Test Case Status")

    # Determinamos o número de questões a partir do primeiro aluno com dados
    num_questions = len(st.session_state.raw_data[0].questions)

    for q_idx in range(num_questions):
        q_label = f"Question {q_idx + 1}"

        with st.expander(f"Status: {q_label}", expanded=True):
            test_results_map = {}

            # 1. Encontrar o máximo de casos de teste para esta questão (normalização)
            max_tests = 0
            for user in st.session_state.raw_data:
                max_tests = max(max_tests, len(user.questions[q_idx].test_results))

            # 2. Construir matriz de ícones
            for user in st.session_state.raw_data:
                q_data = user.questions[q_idx]
                icons = []

                for i in range(max_tests):
                    if i < len(q_data.test_results):
                        # Caso de teste existe
                        icons.append("🟢" if q_data.test_results[i].passed else "🔴")
                    else:
                        # Aluno não chegou a esse caso de teste (ex: não submeteu)
                        icons.append("⚪")

                test_results_map[user.username] = icons

            if test_results_map and max_tests > 0:
                # Transposto: Casos de Teste (Linhas) x Alunos (Colunas)
                test_df = pd.DataFrame(test_results_map)
                test_df.index = [f"Test {i+1}" for i in range(max_tests)]
                st.dataframe(test_df, use_container_width=True)
            else:
                st.info(f"No test results recorded for {q_label}")

    # --- OVERALL PROGRESS MATRIX ---
    st.divider()
    st.subheader("Progress Matrix (Overall %)")
    st.dataframe(
        df.set_index("Student")
        .filter(like="(%)")
        .style.background_gradient(cmap="RdYlGn", vmin=0, vmax=100),
        use_container_width=True
    )

else:
    st.info("Fill credentials and click 'Sync Now' or load local cache.")