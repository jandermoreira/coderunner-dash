import os
import pickle
from datetime import datetime

import asyncio
import streamlit as st

from analytics.metrics import calculate_analytics
from scraper.moodle_scraper import MoodleScraper
from dashboard.ui import *


def initialize_session_state():
    """Initializes page config and session variables."""
    st.set_page_config(page_title="CodeRunner Dash", layout="wide")

    if 'raw_data' not in st.session_state:
        st.session_state.raw_data = None
    if 'last_sync' not in st.session_state:
        st.session_state.last_sync = None
    if 'last_auto_refresh' not in st.session_state:
        st.session_state.last_auto_refresh = 0


def run_dashboard():
    initialize_session_state()
    lock_page_scroll()

    username, password, quiz_id = render_sidebar()

    if st.session_state.raw_data == "loading":
        sync_with_moodle(username, password, quiz_id)

    if isinstance(st.session_state.raw_data, list) and st.session_state.raw_data:
        history_path = get_history_path(quiz_id)
        history_data = None
        if os.path.exists(history_path):
            with open(history_path, "rb") as f:
                history_data = pickle.load(f)

        stats_df, common_errors = calculate_analytics(st.session_state.raw_data,
                                                      history=history_data)

        # if not common_errors.empty:
        #     st.subheader("🚨 Most Common Failures")
        #     # Mostra os 5 testes que mais falham
        #     st.bar_chart(common_errors.head(5))
        # else:
        #     st.success("No common failures detected!")

        st.text("")
        render_top_indicators(stats_df)

        with st.container(height=610, width='stretch'):
            st.subheader("📈 Evolution")
            student_list = sorted(s.username for s in st.session_state.raw_data)
            render_student(quiz_id, student_list, stats_df)

            render_detailed_test_grid(st.session_state.raw_data)

            st.divider()
            st.subheader("Progress Matrix (Overall %)")
            matrix_df = stats_df.set_index("Student").filter(like="(%)")
            matrix_df = matrix_df[~matrix_df.index.duplicated(keep='first')]

            if not matrix_df.columns.is_unique:
                new_cols = []
                counts = {}
                for col in matrix_df.columns:
                    counts[col] = counts.get(col, 0) + 1
                    new_cols.append(f"{col}_{counts[col]}" if counts[col] > 1 else col)
                matrix_df.columns = new_cols

            st.dataframe(
                matrix_df.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=100),
                width="stretch"
            )
    else:
        st.info("Please enter credentials in the sidebar and click 'Sync Now'.")


if __name__ == "__main__":
    run_dashboard()
