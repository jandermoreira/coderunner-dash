"""
Data management
==============================
Handles cache persistence and asynchronous sync orchestration.
"""

import asyncio
import os
import dill
import streamlit as st
from time import sleep
from dataclasses import asdict
from scraper.moodle_scraper import MoodleScraper
from models.quiz_models import (
    UserQuizData, QuestionData, SubmissionStep, TestCase,
    ProgressState, StrategyProfile, InterventionType, PedagogicalDecision
)

def reconstruct_objects(raw_list):
    """
    Converts a list of dictionaries back into UserQuizData objects.
    """
    reconstructed = []
    if not raw_list:
        return []

    for u_data in raw_list:
        if isinstance(u_data, UserQuizData):
            reconstructed.append(u_data)
            continue

        # Reconstruct Questions
        questions = []
        for q_data in u_data.get('questions', []):

            # Reconstruct Steps
            steps = []
            for s_data in q_data.get('steps', []):

                # Reconstruct TestCases
                tests = []
                for t_data in s_data.get('test_results', []):
                    tests.append(TestCase(**t_data))

                # Create SubmissionStep
                s_copy = s_data.copy()
                s_copy['test_results'] = tests
                steps.append(SubmissionStep(**s_copy))

            # Reconstruct Decision (Pedagogical State)
            decision_data = q_data.get('decision', {})
            decision = PedagogicalDecision() # Default
            if decision_data:
                # Handle Enums conversion safely
                try:
                    decision = PedagogicalDecision(
                        is_technical_noise=decision_data.get('is_technical_noise', False),
                        progress=ProgressState(decision_data.get('progress', 'none')),
                        strategy=StrategyProfile(decision_data.get('strategy', 'unknown')),
                        intervention=InterventionType(decision_data.get('intervention', 'do_not_intervene')),
                        justification=decision_data.get('justification', "")
                    )
                except Exception:
                    pass # Keep default if enum fails

            # Create QuestionData
            q_copy = q_data.copy()
            q_copy['steps'] = steps
            q_copy['decision'] = decision
            questions.append(QuestionData(**q_copy))

        # Create UserQuizData
        u_copy = u_data.copy()
        u_copy['questions'] = questions
        reconstructed.append(UserQuizData(**u_copy))

    return reconstructed

# --- CACHE MANAGEMENT ---

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
        try:
            with open(cache_path, "rb") as f:
                cache = dill.load(f)

                # Handle dictionary structure
                if isinstance(cache, dict) and "data" in cache:
                    raw_data = cache["data"]
                    steps_urls = cache.get("steps_urls", set())
                else:
                    raw_data = cache
                    steps_urls = set()

                final_data = reconstruct_objects(raw_data)
                return final_data, steps_urls

        except Exception as e:
            st.error(f"Cache load error: {e}")
            return None, set()
    else:
        return None

def sync_with_moodle(user, password, quiz_id):
    """Triggers the incremental sync process."""
    with st.status("Syncing with Moodle...", expanded=False) as status:
        try:
            fetched_data, updated_steps_urls = asyncio.run(run_scraper_async(user, password, quiz_id, status))

            if isinstance(fetched_data, list):
                st.session_state.raw_data = fetched_data
                st.session_state.steps_urls = updated_steps_urls

                # Convert Objects to Dicts before saving.
                serialized_data = [asdict(u) for u in fetched_data]

                cache_to_save = {
                    "data": serialized_data,
                    "steps_urls": updated_steps_urls
                }

                try:
                    with open(f"quiz_{quiz_id}_cache.pkl", "wb") as f:
                        dill.dump(cache_to_save, f)

                    status.update(label="Sync complete!", state="complete", expanded=False)
                    sleep(3)

                except Exception as e:
                    status.update(label="Failed to save cache!", state="error", expanded=True)
                    st.error(f"Save Error: {e}")
                    sleep(10)

            else:
                status.update(label="Sync failed or no data found.", state="error", expanded=True)
                sleep(10)

        except Exception as e:
            status.update(label="Critical error during sync", state="error", expanded=True)
            st.error(f"Details: {e}")
            sleep(12)


async def run_scraper_async(user, password, quiz_id, status_box):
    cached_steps = st.session_state.get("steps_urls", set())
    existing_data = st.session_state.get("raw_data", None)


    scraper = MoodleScraper(user, password, cached_steps)
    try:
        data, urls = await scraper.run(quiz_id, status_box, existing_data=existing_data)
        return data, urls
    finally:
        await scraper.close()