"""
Analytics and Metrics Calculation Module
=========================================

This module processes raw quiz data and history into structured analytics.
"""

import collections
import pandas as pd
from typing import List, Dict, Any
from models.quiz_models import UserQuizData


def count_regressions_with_forgiveness(test_history: List[bool]) -> int:
    """
    Counts how many times a test went from Passed (True) to Failed (False).
    Returns 0 if the last 4 attempts were successful (Forgiveness Rule).
    """
    if len(test_history) < 2:
        return 0

    # Forgiveness Rule: If last 4 attempts are True, ignore previous regressions
    recent_attempts = test_history[-4:]
    if all(recent_attempts) and len(recent_attempts) >= 4:
        return 0

    regressions = 0
    for i in range(1, len(test_history)):
        if test_history[i - 1] is True and test_history[i] is False:
            regressions += 1

    return regressions


def calculate_analytics(current_results: List[UserQuizData], history: List[Dict[str, Any]] = None):
    """
    Processes quiz data and history to compute:
    1. Performance per question (%)
    2. Regression counts (instability)
    3. Tinkering behavior (excessive trial and error)
    4. Global failure patterns
    """
    flat_data = []
    failure_patterns = collections.defaultdict(int)

    for user in current_results:
        entry = {"Student": user.username}

        for question_idx, question in enumerate(user.questions):
            entry[f"Q{question_idx + 1} (%)"] = question.final_score

            # Regression logic
            q_regressions = 0
            if history:
                for t_idx in range(len(question.test_results)):
                    test_timeline = []
                    for snap in history:
                        u_snap = next((s for s in snap["data"]
                                       if s.username == user.username), None)
                        if u_snap and question_idx < len(u_snap.questions):
                            snap_q = u_snap.questions[question_idx]
                            if t_idx < len(snap_q.test_results):
                                test_timeline.append(snap_q.test_results[t_idx].passed)

                    q_regressions += count_regressions_with_forgiveness(test_timeline)

            entry[f"Q{question_idx + 1} Regressions"] = q_regressions

            # Tinkering
            entry[f"Q{question_idx + 1} has_tinkering"] = question.has_tinkering

            # Global pattern tracking
            for t_idx, test in enumerate(question.test_results):
                if not test.passed:
                    failure_patterns[f"Q{question_idx + 1}-T{t_idx + 1}"] += 1

        flat_data.append(entry)

    df = pd.DataFrame(flat_data)
    series_failures = pd.Series(failure_patterns).sort_values(
        ascending=False) if failure_patterns else pd.Series()

    return df, series_failures
