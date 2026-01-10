"""
UI
==============================

This module handles UI.
"""
import asyncio
import os
import pickle
from datetime import datetime

import streamlit as st

import pandas as pd
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

from scraper.moodle_scraper import MoodleScraper


def get_history_path(quiz_id):
    return f"history_{quiz_id}.pkl"


def save_history_snapshot(quiz_id, data):
    """Appends current data as a timestamped snapshot in the history file."""
    path = get_history_path(quiz_id)
    history = []

    if os.path.exists(path):
        with open(path, "rb") as f:
            history = pickle.load(f)

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
            st.session_state.last_sync = "Cached data"
        st.success("Data loaded from local cache!")
        st.rerun()
    else:
        st.error("Cache file not found.")


def sync_with_moodle(user, password, quiz_id):
    with st.status("Connecting and extracting data from Moodle...", expanded=True) as status:
        fetched_data = asyncio.run(run_scraper_async(user, password, quiz_id, status))

        if fetched_data:
            st.session_state.raw_data = fetched_data
            st.session_state.last_sync = datetime.now().strftime('%H:%M:%S')

            with open("quiz_cache.pkl", "wb") as f:
                pickle.dump(fetched_data, f)

            save_history_snapshot(quiz_id, fetched_data)
            st.rerun()
        else:
            st.session_state.raw_data = None
            status.update(label="No data found.", state="error")


async def run_scraper_async(user, password, quiz_id, status_box):
    scraper = MoodleScraper(user, password)
    try:
        return await scraper.run(quiz_id, status_box)
    finally:
        await scraper.close()
