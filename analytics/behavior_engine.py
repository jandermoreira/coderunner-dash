"""
Behavioral and Pedagogical Engine
=================================

Processes technical metrics from submission history to derive behavioral
signals and pedagogical states.

Following the 4-layer logic:
1. Technical Sanitation (Noise detection)
2. Technical Metrics (Intervals, Stability, Plateau duration)
3. Behavioral Signals (Strategy & Progress profiling)
4. Pedagogical Decisions (Intervention recommendation)
"""

from typing import List
from models.quiz_models import (
    QuestionData, SubmissionStep, PedagogicalDecision,
    ProgressState, StrategyProfile, InterventionType
)

def calculate_avg_interval(steps: List[SubmissionStep]) -> float:
    """
    Calculates the average time (in seconds) between consecutive submissions.
    Returns 0.0 if there are fewer than two submissions.
    """
    if len(steps) < 2:
        return 0.0

    intervals = []
    for i in range(1, len(steps)):
        delta = (steps[i].timestamp - steps[i-1].timestamp).total_seconds()
        intervals.append(delta)

    return sum(intervals) / len(intervals)


def derive_pedagogical_decision(question: QuestionData) -> PedagogicalDecision:
    """
    The core logic pipeline. Transforms raw submission logs into
    actionable pedagogical decisions for the teacher.
    """
    steps = question.steps
    decision = PedagogicalDecision()

    if not steps:
        return decision

    # --- LAYER 1: Technical Sanitation ---
    # Goal: Identify if the data is "clean" enough for pedagogical analysis.
    compilation_errors = sum(
        1 for s in steps if any(t.is_compilation_error for t in s.test_results)
    )
    noise_ratio = compilation_errors / len(steps)

    # Logic: High ratio of compilation errors in a significant number of attempts.
    if noise_ratio > 0.6 and len(steps) > 3:
        decision.is_technical_noise = True
        decision.intervention = InterventionType.TECHNICAL
        decision.justification = "High technical noise: frequent compilation errors (syntax struggle)."
        return decision

    # --- LAYER 2: Technical Metrics Derivation ---
    current_score = question.final_score
    recent_scores = [s.score for s in steps[-3:]] # Look at the last 3 attempts
    avg_interval = calculate_avg_interval(steps)

    # Calculate Time to First Submission (Required for Strategy Profiling)
    start_time = question.quiz_start_timestamp
    time_to_first = (steps[0].timestamp - start_time).total_seconds() if start_time else 0

    # --- LAYER 3: Behavioral Signals ---

    # 3.1 Progress State Determination
    if len(steps) >= 3 and len(set(recent_scores)) == 1 and current_score < 100:
        decision.progress = ProgressState.PLATEAU
    elif current_score > 0 and all(recent_scores[i] <= recent_scores[i+1] for i in range(len(recent_scores)-1)):
        decision.progress = ProgressState.CONSISTENT
    else:
        decision.progress = ProgressState.UNSTABLE

    # 3.2 Strategy Profiling
    # Planning: Long reflection before 1st sub with immediate success.
    if time_to_first > 300 and steps[0].score > 0:
        decision.strategy = StrategyProfile.PLANNING

    # Trial and Error: High frequency of attempts with low logic change.
    elif len(steps) > 5 and avg_interval < 45:
        decision.strategy = StrategyProfile.TRIAL_AND_ERROR

    # Brute Force: High volume of attempts regardless of interval.
    elif len(steps) > 8:
        decision.strategy = StrategyProfile.BRUTE_FORCE

    # Refinement: Low number of attempts to reach the goal.
    elif current_score > 0 and len(steps) < 4:
        decision.strategy = StrategyProfile.REFINEMENT
    else:
        decision.strategy = StrategyProfile.UNKNOWN

    # --- LAYER 4: Pedagogical Decision (Final Action) ---
    # Logic: Prioritize interventions based on combined signals.

    if decision.progress == ProgressState.PLATEAU:
        decision.intervention = InterventionType.INTERVENE_NOW
        decision.justification = "Student is stuck in a plateau. Conceptual barrier detected."

    elif decision.strategy == StrategyProfile.TRIAL_AND_ERROR:
        decision.intervention = InterventionType.INTERVENE_NOW
        decision.justification = "Impulsive 'Tinkering' pattern. Explain the logic before coding."

    elif decision.progress == ProgressState.UNSTABLE:
        decision.intervention = InterventionType.MONITOR
        decision.justification = "Score is fluctuating significantly. Monitor the next 2 attempts."

    else:
        decision.intervention = InterventionType.NONE
        decision.justification = "Student is progressing normally or has completed the task."

    return decision