"""
Analytics and Metrics Calculation Module
=========================================

This module processes raw quiz data into structured analytics for visualization.
It transforms a list of UserQuizData objects into pandas DataFrames and computes
aggregate failure patterns across all students.
"""

import collections
import pandas as pd
from typing import List
from models.quiz_models import UserQuizData


def calculate_analytics(results: List[UserQuizData]):
    flat_data = []
    failure_patterns = collections.defaultdict(int)

    for user in results:
        entry = {"Student": user.username}
        for i, q in enumerate(user.questions):
            entry[f"Q{i+1} (%)"] = q.final_score
            entry[f"Q{i+1} Attempts"] = q.total_submissions

            for t_idx, test in enumerate(q.test_results):
                if not test.passed:
                    failure_patterns[f"Q{i+1}-T{t_idx+1}"] += 1

        flat_data.append(entry)

    return (
        pd.DataFrame(flat_data),
        pd.Series(failure_patterns).sort_values(ascending=False)
    )
