"""
Data management
==============================
"""

import asyncio
import os
import pickle
from datetime import datetime
import streamlit as st
from scraper.moodle_scraper import MoodleScraper

def reset_local_cache(quiz_id):
    cache_path = f"quiz_{quiz_id}_cache.pkl"
    if os.path.exists(cache_path):
        os.remove(cache_path)
        return True, f"History for Quiz {quiz_id} deleted."
    return False, "No history file found."

def load_local_cache(quiz_id):
    cache_path = f"quiz_{quiz_id}_cache.pkl"
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            cache = pickle.load(f)
            if isinstance(cache, dict) and "data" in cache:
                st.session_state.raw_data = cache["data"]
                st.session_state.steps_urls = cache.get("steps_urls", set())
            else:
                st.session_state.raw_data = cache
                st.session_state.steps_urls = set()
            st.session_state.last_sync = "Cached data"
        st.success("Data loaded from local cache!")
    else:
        st.error("Cache file not found.")

def sync_with_moodle(user, password, quiz_id):
    with st.status("Connecting and extracting data...", expanded=True) as status:
        fetched_data = asyncio.run(run_scraper_async(user, password, quiz_id, status))

        if fetched_data:
            st.session_state.raw_data = fetched_data
            st.session_state.last_sync = datetime.now().strftime('%H:%M:%S')

            cache_to_save = {
                "data": fetched_data,
                "steps_urls": st.session_state.get("steps_urls", set())
            }
            with open(f"quiz_{quiz_id}_cache.pkl", "wb") as f:
                pickle.dump(cache_to_save, f)
            st.rerun()
        else:
            status.update(label="Sync failed.", state="error")

async def run_scraper_async(user, password, quiz_id, status_box):
    # Ensure we get the latest data from session state to pass to the scraper
    cached_steps = st.session_state.get("steps_urls", set())
    existing_data = st.session_state.get("raw_data", None)

    scraper = MoodleScraper(user, password, cached_steps)
    try:
        result = await scraper.run(quiz_id, status_box, existing_data=existing_data)
        st.session_state.steps_urls = scraper.steps_urls
        return result
    finally:
        await scraper.close()