"""
Data Management Module
==============================
Handles local cache persistence using a "Sanitize-Hydrate" strategy to prevent
serialization errors (Pickle/Dill) caused by Streamlit's module hot-reloading.

Strategy:
1. Save: Convert Objects -> Dicts -> Primitive Types (Enums to strings).
2. Load: Convert Primitive Dicts -> Rich Objects (Re-instantiating classes).
"""

import asyncio
import os
import dill
import streamlit as st
from time import sleep
from dataclasses import asdict
from enum import Enum
from datetime import datetime
from scraper.moodle_scraper import MoodleScraper
from models.quiz_models import (
    UserQuizData, QuestionData, SubmissionStep, TestCase,
    ProgressState, StrategyProfile, InterventionType, PedagogicalDecision
)


def sanitize_data(obj):
    """
    Recursively converts non-primitive types (Enums, datetimes, sets) into
    primitive types (strings, lists) for safe serialization.
    """
    if isinstance(obj, dict):
        return {k: sanitize_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_data(v) for v in obj]
    elif isinstance(obj, set):
        return [sanitize_data(v) for v in obj]
    elif isinstance(obj, Enum):
        return obj.value  # Convert Enum to its string value
    elif isinstance(obj, datetime):
        return obj.isoformat()  # Convert datetime to ISO string
    return obj


def reconstruct_objects(raw_list):
    """
    Converts a list of primitive dictionaries back into rich UserQuizData objects.
    Ensures objects use the currently loaded class definitions in memory.
    """
    reconstructed = []
    if not raw_list:
        return []

    for u_data in raw_list:
        # Check if it's already an object (fallback for legacy cache)
        if isinstance(u_data, UserQuizData):
            reconstructed.append(u_data)
            continue

        # 1. Reconstruct Questions
        questions = []
        for q_data in u_data.get('questions', []):

            # 2. Reconstruct Steps
            steps = []
            for s_data in q_data.get('steps', []):
                # TestCases are simple dataclasses without Enums/dates usually
                tests = [TestCase(**t_data) for t_data in s_data.get('test_results', [])]

                # Handle Timestamp (String -> Datetime)
                ts = s_data.get('timestamp')
                dt = datetime.fromisoformat(ts) if isinstance(ts, str) else ts

                steps.append(SubmissionStep(
                    timestamp=dt,
                    url=s_data.get('url'),
                    score=s_data.get('score'),
                    test_results=tests
                ))

            # 3. Reconstruct Decision (Handling Enum Strings)
            d_data = q_data.get('decision', {})
            try:
                decision = PedagogicalDecision(
                    is_technical_noise=d_data.get('is_technical_noise', False),
                    progress=ProgressState(d_data.get('progress', 'none')),
                    strategy=StrategyProfile(d_data.get('strategy', 'unknown')),
                    intervention=InterventionType(d_data.get('intervention', 'do_not_intervene')),
                    justification=d_data.get('justification', "")
                )
            except (ValueError, TypeError):
                decision = PedagogicalDecision() # Fallback to defaults

            # 4. Create QuestionData
            q_start = q_data.get('quiz_start_timestamp')
            q_dt = datetime.fromisoformat(q_start) if isinstance(q_start, str) else q_start

            questions.append(QuestionData(
                total_submissions=q_data.get('total_submissions', 0),
                final_score=q_data.get('final_score', 0.0),
                quiz_start_timestamp=q_dt,
                steps=steps,
                decision=decision
            ))

        # 5. Create UserQuizData
        u_start = u_data.get('quiz_start_timestamp')
        u_end = u_data.get('quiz_end_timestamp')

        reconstructed.append(UserQuizData(
            username=u_data.get('username'),
            questions=questions,
            quiz_start_timestamp=datetime.fromisoformat(u_start) if u_start else None,
            quiz_end_timestamp=datetime.fromisoformat(u_end) if u_end else None
        ))

    return reconstructed


def has_local_cache(quiz_id):
    """Checks if a cache file exists for the given quiz ID."""
    cache_path = f"quiz_{quiz_id}_cache.pkl"
    return os.path.exists(cache_path)


def reset_local_cache(quiz_id):
    """Deletes the local cache file from disk."""
    cache_path = f"quiz_{quiz_id}_cache.pkl"
    if os.path.exists(cache_path):
        os.remove(cache_path)
        return f"Cache for Quiz {quiz_id} removed."
    return "No cache file found."


def load_local_cache(quiz_id):
    """
    Loads data from disk and hydrates it into Python objects.
    """
    cache_path = f"quiz_{quiz_id}_cache.pkl"
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                cache = dill.load(f)

                if isinstance(cache, dict) and "data" in cache:
                    raw_data = cache["data"]
                    steps_urls = set(cache.get("steps_urls", []))
                else:
                    raw_data = cache
                    steps_urls = set()

                # Hydrate: Convert primitive dicts back to class instances
                final_data = reconstruct_objects(raw_data)
                return final_data, steps_urls

        except Exception as e:
            st.error(f"Cache load error: {e}")
            return None, set()
    else:
        return None


def sync_with_moodle(user, password, quiz_id):
    """
    Orchestrates the scraping process, updates session state, and persists
    the result to a sanitized local cache.
    """
    with st.status("Syncing with Moodle...", expanded=False) as status:
        try:
            fetched_data, updated_steps_urls = asyncio.run(
                run_scraper_async(user, password, quiz_id, status))

            if isinstance(fetched_data, list):
                # Update volatile memory (Session State)
                st.session_state.raw_data = fetched_data
                st.session_state.steps_urls = updated_steps_urls

                # --- PREPARE FOR PERSISTENCE ---
                # 1. Convert objects to dicts
                # 2. Convert Enums/Dates to strings (sanitize)
                clean_data = sanitize_data([asdict(u) for u in fetched_data])

                cache_to_save = {
                    "data": clean_data,
                    "steps_urls": list(updated_steps_urls) # sets don't pickle well sometimes
                }

                try:
                    with open(f"quiz_{quiz_id}_cache.pkl", "wb") as f:
                        dill.dump(cache_to_save, f)

                    status.update(label="Sync complete!", state="complete", expanded=False)
                    sleep(0.5)

                except Exception as e:
                    # Auto-expand on save failure
                    status.update(label="Failed to save cache!", state="error", expanded=True)
                    st.error(f"Save Error: {e}")
                    sleep(10)

            else:
                status.update(label="Sync failed or no data found.", state="error", expanded=True)
                sleep(10)

        except Exception as e:
            # Auto-expand on critical scraper failure
            status.update(label="Critical error during sync", state="error", expanded=True)
            st.error(f"Details: {e}")
            sleep(12)


async def run_scraper_async(user, password, quiz_id, status_box):
    """Runs the asynchronous Moodle scraper."""
    cached_steps = st.session_state.get("steps_urls", set())
    existing_data = st.session_state.get("raw_data", None)

    scraper = MoodleScraper(user, password, cached_steps)
    try:
        data, urls = await scraper.run(quiz_id, status_box, existing_data=existing_data)
        return data, urls
    finally:
        await scraper.close()