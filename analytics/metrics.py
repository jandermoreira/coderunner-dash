"""
Analytics and Metrics Calculation Module
=========================================
Processes UserQuizData containing SubmissionSteps to compute:
1. Performance per question (%)
2. Regression counts (using internal step history)
3. Technical Noise (ratio of compilation errors)
4. Tinkering behavior
"""

import collections
import pandas as pd
from typing import List, Dict, Any
from models.quiz_models import UserQuizData

def count_regressions_with_forgiveness(test_history: List[bool]) -> int:
    """
    Counts transitions from Passed (True) to Failed (False).
    Forgiveness: Returns 0 if the last 3 attempts were successful.
    """
    if len(test_history) < 2:
        return 0

    # Rule: If the student fixed it and kept it fixed, ignore past instability
    if all(test_history[-3:]) and len(test_history) >= 3:
        return 0

    regressions = 0
    for i in range(1, len(test_history)):
        if test_history[i - 1] is True and test_history[i] is False:
            regressions += 1
    return regressions


def calculate_analytics(current_results: List[UserQuizData]):
    """
    Main entry point for UI data generation.
    Now uses the internal 'steps' of each question for timeline analysis.
    """
    flat_data = []
    failure_patterns = collections.defaultdict(int)

    for user in current_results:
        entry = {
            "Student": user.username,
            "Total Score": sum(q.final_score for q in user.questions) / len(user.questions) if user.questions else 0
        }

        for q_idx, question in enumerate(user.questions):
            q_label = f"Q{q_idx + 1}"
            entry[f"{q_label} (%)"] = question.final_score

            # --- 1. Internal Regression Analysis ---
            total_q_regressions = 0

            if question.steps:
                latest_step = question.steps[-1]
                num_tests = len(latest_step.test_results)

                for t_idx in range(num_tests):
                    # Build the timeline for THIS specific test across all steps
                    test_timeline = []
                    for step in question.steps:
                        if t_idx < len(step.test_results):
                            test_timeline.append(step.test_results[t_idx].passed)

                    total_q_regressions += count_regressions_with_forgiveness(test_timeline)

            entry[f"{q_label} Regressions"] = total_q_regressions

            # --- 2. Technical Noise ---
            comp_errors = sum(1 for s in question.steps if s.has_compilation_error)

            entry[f"{q_label} Noise"] = round(comp_errors / len(question.steps), 2) if question.steps else 0

            # --- 3. Tinkering Detection ---
            entry[f"{q_label} has_tinkering"] = len(question.steps) >= 5

            # --- 4. Global Failure Patterns (for the bar chart) ---
            latest_step = question.steps[-1] if question.steps else None
            if latest_step:
                for t_idx, test in enumerate(latest_step.test_results):
                    if not test.passed:
                        failure_patterns[f"{q_label}-T{t_idx + 1}"] += 1

        # Calculate Intervention Priority
        entry["Priority"] = "Low"
        for q_idx in range(len(user.questions)):
            reg = entry.get(f"Q{q_idx+1} Regressions", 0)
            score = entry.get(f"Q{q_idx+1} (%)", 100)
            if reg > 2 or (score < 100 and entry.get(f"Q{q_idx+1} Noise", 0) > 0.5):
                entry["Priority"] = "High"
                break

        flat_data.append(entry)

    df = pd.DataFrame(flat_data)
    series_failures = pd.Series(failure_patterns).sort_values(ascending=False) if failure_patterns else pd.Series()

    return df, series_failures