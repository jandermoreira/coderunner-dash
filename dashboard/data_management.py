"""
Data management
==============================
Handles cache persistence and asynchronous sync orchestration.
"""

import asyncio
import os
import dill
import streamlit as st
from scraper.moodle_scraper import MoodleScraper
from models.quiz_models import *

def has_local_cache(quiz_id):
    cache_path = f"quiz_{quiz_id}_cache.pkl"
    return os.path.exists(cache_path)

def reset_local_cache(quiz_id):
    """Removes the local dill cache."""
    cache_path = f"quiz_{quiz_id}_cache.pkl"
    if os.path.exists(cache_path):
        os.remove(cache_path)
        return f"Cache for Quiz {quiz_id} removed."
    return "No cache file found."

def load_local_cache(quiz_id):
    """Loads student data and URL history from local storage."""
    cache_path = f"quiz_{quiz_id}_cache.pkl"
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            cache = dill.load(f)
            if isinstance(cache, dict) and "data" in cache:
                st.session_state.raw_data = cache["data"]
                st.session_state.steps_urls = cache.get("steps_urls", set())
            else:
                st.session_state.raw_data = cache
                st.session_state.steps_urls = set()
            st.session_state.last_sync = "From cache"
        st.success("Data successfully loaded from local cache.")
    else:
        st.error("Cache file not found.")

def sync_with_moodle(user, password, quiz_id):
    """Triggers the incremental sync process."""
    with st.status("Syncing with Moodle...", expanded=False) as status:
        fetched_data, updated_steps_urls = asyncio.run(run_scraper_async(user, password, quiz_id, status))

        if isinstance(fetched_data, list):
            st.session_state.raw_data = fetched_data
            st.session_state.steps_urls = updated_steps_urls

            cache_to_save = {
                "data": fetched_data,
                "steps_urls": updated_steps_urls
            }
            with open(f"quiz_{quiz_id}_cache.pkl", "wb") as f:
                dill.dump(cache_to_save, f)
            st.rerun()
        else:
            status.update(label="Sync failed or no data found.", state="error")

async def run_scraper_async(user, password, quiz_id, status_box):
    cached_steps = st.session_state.get("steps_urls", set())
    existing_data = st.session_state.get("raw_data", None)


    scraper = MoodleScraper(user, password, cached_steps)
    try:
        data, urls = await scraper.run(quiz_id, status_box, existing_data=existing_data)
        return data, urls
    finally:
        await scraper.close()