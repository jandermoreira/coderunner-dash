"""
Analytics Pipeline Orchestrator
===============================

This module acts as the central coordinator for the data enrichment process.
It takes raw UserQuizData objects (populated by the parser) and runs them
through the Behavioral Engine to generate pedagogical insights.
"""

from typing import List
from models.quiz_models import UserQuizData
from analytics.behavior_engine import derive_pedagogical_decision

def run_pedagogical_pipeline(raw_quiz_data: List[UserQuizData]) -> List[UserQuizData]:
    """
    Enriches raw student data with pedagogical states and intervention logic.

    This is the mandatory intermediate step between data fetching and
    UI rendering. It ensures that every question for every student has
    a calculated 'decision' field based on the 4-layer logic.

    Args:
        raw_quiz_data: A list of UserQuizData objects containing raw logs.

    Returns:
        The same list of objects, but with the 'decision' field populated
        in each QuestionData instance.
    """
    if not raw_quiz_data:
        return []

    for student_data in raw_quiz_data:
        # Propagate quiz-level metadata to questions if needed
        # (e.g., start time is used to calculate time-to-first-submission)
        for question in student_data.questions:
            question.quiz_start_timestamp = student_data.quiz_start_timestamp

            # --- The Core Enrichment Step ---
            # This calls the Layer 1-4 logic defined in Step 2
            question.decision = derive_pedagogical_decision(question)

    return raw_quiz_data

def get_intervention_priority_list(enriched_data: List[UserQuizData]) -> List[UserQuizData]:
    """
    Sorts or filters students based on the severity of the recommended intervention.
    Useful for the 'Intervene Now' section of the dashboard.
    """
    # Logic to prioritize students with INTERVENE_NOW status across any question
    return sorted(
        enriched_data,
        key=lambda s: any(
            q.decision.intervention.value == "intervene_now"
            for q in s.questions
        ),
        reverse=True
    )