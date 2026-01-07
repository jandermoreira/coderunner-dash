"""
CodeRunner Monitoring Dashboard
===============================
Streamlit interface for visualizing student performance on Moodle CodeRunner quizzes.
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
# ENVIRONMENT & STATE
# ==========================================

def initialize_session_state():
    """Initializes page config and session variables."""
    st.set_page_config(page_title="CodeRunner Dash", layout="wide")

    if 'raw_data' not in st.session_state:
        st.session_state.raw_data = None
    if 'last_sync' not in st.session_state:
        st.session_state.last_sync = None
    if 'last_auto_refresh' not in st.session_state:
        st.session_state.last_auto_refresh = 0


# ==========================================
# DATA MANAGEMENT
# ==========================================

def load_local_cache():
    """Loads serialized quiz data from a local pickle file."""
    cache_path = "tests/quiz_cache.pkl"
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            st.session_state.raw_data = pickle.load(f)
            st.session_state.last_sync = "Mock data"
        st.success("Data loaded from local cache!")
        st.rerun()
    else:
        st.error(f"Cache file not found at '{cache_path}'.")


def sync_with_moodle(user, password, quiz_id):
    """Executes the scraper to fetch fresh data from Moodle."""
    with st.status("Connecting and extracting data from Moodle...", expanded=True) as status:
        scraper = MoodleScraper(user, password)
        fetched_data = scraper.run(quiz_id, status)
        scraper.close()

        if fetched_data:
            st.session_state.raw_data = fetched_data
            st.session_state.last_sync = datetime.now().strftime('%H:%M:%S')

            save_history_snapshot(quiz_id, fetched_data)

            st.rerun()
        else:
            st.session_state.raw_data = None
            status.update(label="No data found.", state="error")


def save_history_snapshot(quiz_id, new_data):
    """Appends a new snapshot with a timestamp to the quiz history file."""
    history_path = f"history_{quiz_id}.pkl"

    if os.path.exists(history_path):
        with open(history_path, "rb") as f:
            history = pickle.load(f)
    else:
        history = []

    snapshot = {
        "timestamp": datetime.now(),
        "data": new_data
    }
    history.append(snapshot)

    with open(history_path, "wb") as f:
        pickle.dump(history, f)


def reset_history(quiz_id):
    """Deletes the history file for the specific quiz."""
    path = get_history_path(quiz_id)
    if os.path.exists(path):
        os.remove(path)
        st.success(f"History for Quiz {quiz_id} deleted.")
    else:
        st.error("No history file found to delete.")


# ==========================================
# UI COMPONENTS
# ==========================================

def render_sidebar():
    """Renders control widgets and settings in the sidebar."""
    with st.sidebar:
        st.header("Settings")
        user = st.text_input("Moodle User", value=os.getenv("MOODLE_USER", ""))
        pw = st.text_input("Password", type="password", value=os.getenv("MOODLE_PASS", ""))
        qid = st.text_input("Quiz ID", value=os.getenv("MOODLE_QUIZ_ID", "958257"))

        st.divider()
        st.subheader("Local Data")
        if st.button("📂 Load Local Cache"):
            load_local_cache()

        st.divider()
        st.subheader("Update Settings")

        # New feature: Toggle auto-sync
        enable_auto_sync = st.checkbox("Enable Auto-sync", value=True)
        interval = st.slider("Interval (minutes)", min_value=2, max_value=10, value=5,
                             disabled=not enable_auto_sync)

        if enable_auto_sync:
            refresh_count = st_autorefresh(interval=interval * 60 * 1000, key="moodle_auto_sync")

            if refresh_count > st.session_state.last_auto_refresh:
                st.session_state.last_auto_refresh = refresh_count
                st.session_state.raw_data = "loading"

        if st.button("🚀 Sync Now"):
            st.session_state.raw_data = "loading"
            st.rerun()

        with st.expander("⚠️ Danger Zone"):
            st.write("Resetting history will delete all saved snapshots for this Quiz ID.")
            if st.button("🗑️ Reset History"):
                st.session_state.confirm_reset = True

            if st.session_state.get('confirm_reset'):
                st.warning("Are you sure?")
                col_yes, col_no = st.columns(2)
                if col_yes.button("Yes, delete"):
                    reset_history(qid)
                    st.session_state.confirm_reset = False
                    st.rerun()
                if col_no.button("Cancel"):
                    st.session_state.confirm_reset = False
                    st.rerun()

    return user, pw, qid


def render_top_metrics(analytics_df):
    """Displays high-level metric cards."""
    col1, col2, col3 = st.columns(3)
    col1.metric("Students", len(analytics_df))
    col2.metric("Total Submissions", int(analytics_df.filter(like="Attempts").sum().sum()))
    col3.metric("Last Sync", st.session_state.last_sync)


def render_summary_charts(analytics_df, errors_series):
    """Renders success distribution and common failure charts."""
    left_col, right_col = st.columns(2)
    with left_col:
        st.subheader("Success Distribution")
        st.bar_chart(analytics_df.filter(like="(%)").mean(axis=1).value_counts().sort_index())

    with right_col:
        st.subheader("Top Roadblocks (Errors)")
        if not errors_series.empty:
            st.bar_chart(errors_series.head(10))
        else:
            st.success("All tests passing!")


def render_detailed_test_grid(raw_data):
    """Creates the 🟢/🔴/⚪ icon matrix for each question's test cases."""
    st.divider()
    st.header("🔍 Detailed Test Case Status")

    num_questions = len(raw_data[0].questions)

    for i in range(num_questions):
        question_label = f"Question {i + 1}"

        with st.expander(f"View Status: {question_label}", expanded=True):
            results_map = {}
            max_test_count = max(len(student.questions[i].test_results) for student in raw_data)

            for student in raw_data:
                q_data = student.questions[i]
                status_icons = []
                for test_idx in range(max_test_count):
                    if test_idx < len(q_data.test_results):
                        status_icons.append("🟢" if q_data.test_results[test_idx].passed else "🔴")
                    else:
                        status_icons.append("⚪")
                results_map[student.username] = status_icons

            if results_map and max_test_count > 0:
                grid_df = pd.DataFrame(results_map)
                grid_df.index = [f"Test {t + 1}" for t in range(max_test_count)]
                st.dataframe(grid_df, width="stretch")


# ==========================================
# MAIN EXECUTION LOOP
# ==========================================

def run_dashboard():
    initialize_session_state()
    st.title("📊 CodeRunner Monitoring System")

    username, password, quiz_id = render_sidebar()

    if st.session_state.raw_data == "loading":
        sync_with_moodle(username, password, quiz_id)

    if isinstance(st.session_state.raw_data, list) and st.session_state.raw_data:
        stats_df, common_errors = calculate_analytics(st.session_state.raw_data)

        render_top_metrics(stats_df)
        render_summary_charts(stats_df, common_errors)
        render_detailed_test_grid(st.session_state.raw_data)

        st.divider()
        st.subheader("Progress Matrix (Overall %)")
        st.dataframe(
            stats_df.set_index("Student")
            .filter(like="(%)")
            .style.background_gradient(cmap="RdYlGn", vmin=0, vmax=100),
            width="stretch"
        )
    else:
        st.info("Please enter credentials in the sidebar and click 'Sync Now' or load from cache.")


if __name__ == "__main__":
    run_dashboard()
