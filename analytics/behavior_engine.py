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


def calculate_avg_interval(steps: List[SubmissionStep], window: int = 3) -> float:
    """
    Calculates the average interval between submissions in minutes,
    considering only the last `window` steps.
    Returns 0.0 if there are fewer than two submissions.
    """
    if len(steps) < 2:
        return 0.0

    recent_steps = steps[-window:]
    if len(recent_steps) < 2:
        return 0.0

    intervals = []
    for i in range(1, len(recent_steps)):
        delta_minutes = (
                                recent_steps[i].timestamp - recent_steps[i - 1].timestamp
                        ).total_seconds() / 60
        intervals.append(delta_minutes)

    return sum(intervals) / len(intervals)


def derive_pedagogical_decision(question: QuestionData) -> PedagogicalDecision:
    """
    Core logic pipeline adapted for timestamps with minute-level granularity.
    """
    steps = question.steps
    decision = PedagogicalDecision()

    if not steps:
        decision.intervention = InterventionType.MONITOR
        decision.justification = "⚠️ No submissions yet."
        return decision

    # --- LAYER 1: Technical Sanitation ---
    RECENT_WINDOW = 3
    recent_steps = steps[-RECENT_WINDOW:]
    recent_compilation_errors = sum(
        1 for step in recent_steps
        if any(test.is_compilation_error for test in step.test_results)
    )

    if recent_compilation_errors >= 2:
        decision.is_technical_noise = True
        decision.intervention = InterventionType.TECHNICAL
        decision.justification = (
            "High technical noise in recent submissions: compilation errors blocking execution."
        )
        return decision

    # --- LAYER 2: Technical Metrics (in minutes) ---
    current_score = question.final_score
    recent_scores = [s.score for s in steps[-3:]]

    avg_interval = calculate_avg_interval(steps, window=3)

    start_time = question.quiz_start_timestamp
    time_to_first = (
        (steps[0].timestamp - start_time).total_seconds() / 60
        if start_time else 0
    )

    # --- LAYER 3: Behavioral Signals ---

    # 3.1 Progress State
    if len(steps) >= 3 and len(set(recent_scores)) == 1 and current_score < 100:
        decision.progress = ProgressState.PLATEAU

    elif (current_score > 0 and \
          all(recent_scores[i] <= recent_scores[i + 1] for i in range(len(recent_scores) - 1))):
        decision.progress = ProgressState.CONSISTENT

    else:
        decision.progress = ProgressState.UNSTABLE

    # 3.2 Strategy Profiling (minutes-based)

    # Planning: reflection ≥ 5 minutes before first submission with immediate success
    if time_to_first >= 5 and steps[0].score > 0:
        decision.strategy = StrategyProfile.PLANNING

    # Trial and Error: many attempts in the same minute window
    elif len(steps) > 5 and avg_interval < 1:
        decision.strategy = StrategyProfile.TRIAL_AND_ERROR

    # Brute Force: very high number of attempts
    elif len(steps) > 8:
        decision.strategy = StrategyProfile.BRUTE_FORCE

    # Refinement: few attempts to reach a positive score
    elif current_score > 0 and len(steps) < 4:
        decision.strategy = StrategyProfile.REFINEMENT

    else:
        decision.strategy = StrategyProfile.UNKNOWN

    # --- LAYER 4: Pedagogical Decision ---

    if decision.progress == ProgressState.PLATEAU:
        decision.intervention = InterventionType.INTERVENE_NOW
        decision.justification = "⛔ Stuck in a plateau. Conceptual barrier detected."

    elif decision.strategy == StrategyProfile.TRIAL_AND_ERROR:
        decision.intervention = InterventionType.INTERVENE_NOW
        decision.justification = "⚡ Impulsive 'tinkering' pattern. Explain the logic before coding."

    elif decision.progress == ProgressState.UNSTABLE:
        decision.intervention = InterventionType.MONITOR
        decision.justification = "🔄 Score is fluctuating significantly. Monitor the next attempts."

    else:
        decision.intervention = InterventionType.NONE
        decision.justification = "✅ Normal progress."

    return decision
