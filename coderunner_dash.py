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
# DATA & HISTORY MANAGEMENT
# ==========================================

def get_history_path(quiz_id):
    return f"history_{quiz_id}.pkl"

def save_history_snapshot(quiz_id, data):
    """Appends current data as a timestamped snapshot in the history file."""
    path = get_history_path(quiz_id)
    history = []

    if os.path.exists(path):
        with open(path, "rb") as f:
            history = pickle.load(f)

    # Avoid saving identical snapshots if no changes occurred
    snapshot = {"timestamp": datetime.now(), "data": data}
    history.append(snapshot)

    with open(path, "wb") as f:
        pickle.dump(history, f)

def reset_history(quiz_id):
    """Deletes the history file for the specific quiz."""
    path = get_history_path(quiz_id)
    if os.path.exists(path):
        os.remove(path)
        st.success(f"History for Quiz {quiz_id} deleted.")
    else:
        st.error("No history file found to delete.")

def load_local_cache():
    cache_path = "quiz_cache.pkl"
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            st.session_state.raw_data = pickle.load(f)
            st.session_state.last_sync = f"Cache: {datetime.now().strftime('%H:%M:%S')}"
        st.success("Data loaded from local cache!")
        st.rerun()
    else:
        st.error("Cache file not found.")

def sync_with_moodle(user, password, quiz_id):
    with st.status("Connecting and extracting data from Moodle...", expanded=True) as status:
        scraper = MoodleScraper(user, password)
        fetched_data = scraper.run(quiz_id, status)
        scraper.close()

        if fetched_data:
            st.session_state.raw_data = fetched_data
            st.session_state.last_sync = datetime.now().strftime('%H:%M:%S')

            # Save Current Cache
            with open("quiz_cache.pkl", "wb") as f:
                pickle.dump(fetched_data, f)

            # Save History Snapshot
            save_history_snapshot(quiz_id, fetched_data)

            st.rerun()
        else:
            st.session_state.raw_data = None
            status.update(label="No data found.", state="error")

# ==========================================
# UI COMPONENTS
# ==========================================

def render_sidebar():
    with st.sidebar:
        st.header("Settings")
        user = st.text_input("Moodle User", value=os.getenv("MOODLE_USER", ""))
        pw = st.text_input("Password", type="password", value=os.getenv("MOODLE_PASS", ""))
        qid = st.text_input("Quiz ID", value=os.getenv("MOODLE_QUIZ_ID", "958257"))

        st.divider()
        st.subheader("Data Management")
        if st.button("📂 Load Last Sync"):
            load_local_cache()

        # --- RESET HISTORY WITH CONFIRMATION ---
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

        st.divider()
        st.subheader("Update Settings")
        enable_auto_sync = st.checkbox("Enable Auto-sync", value=True)
        interval = st.slider("Interval (minutes)", 2, 10, 5, disabled=not enable_auto_sync)

        if enable_auto_sync:
            refresh_count = st_autorefresh(interval=interval * 60 * 1000, key="moodle_auto_sync")
            if refresh_count > st.session_state.last_auto_refresh:
                st.session_state.last_auto_refresh = refresh_count
                st.session_state.raw_data = "loading"

        if st.button("🚀 Sync Now"):
            st.session_state.raw_data = "loading"
            st.rerun()

    return user, pw, qid

def render_detailed_test_grid(raw_data):
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
                icons = [("🟢" if q_data.test_results[idx].passed else "🔴") if idx < len(q_data.test_results) else "⚪"
                         for idx in range(max_test_count)]
                results_map[student.username] = icons

            if results_map and max_test_count > 0:
                grid_df = pd.DataFrame(results_map)
                grid_df.index = [f"Test {t+1}" for t in range(max_test_count)]
                st.dataframe(grid_df, width="stretch")

# ==========================================
# MAIN LOOP
# ==========================================

def run_dashboard():
    initialize_session_state()
    st.title("📊 CodeRunner Monitoring System")

    username, password, quiz_id = render_sidebar()

    if st.session_state.raw_data == "loading":
        sync_with_moodle(username, password, quiz_id)

    if isinstance(st.session_state.raw_data, list) and st.session_state.raw_data:
        stats_df, common_errors = calculate_analytics(st.session_state.raw_data)

        # Render metrics and charts (Keeping names from previous steps)
        # render_top_metrics(stats_df)
        # render_summary_charts(stats_df, common_errors)

        render_detailed_test_grid(st.session_state.raw_data)

        st.divider()
        st.subheader("Progress Matrix (Overall %)")
        st.dataframe(
            stats_df.set_index("Student").filter(like="(%)")
            .style.background_gradient(cmap="RdYlGn", vmin=0, vmax=100),
            width="stretch"
        )
    else:
        st.info("Please enter credentials in the sidebar and click 'Sync Now'.")

if __name__ == "__main__":
    run_dashboard()