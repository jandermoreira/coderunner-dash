"""
Behavioral Engine Test Battery
==============================

Unit tests to validate the 4-layer pedagogical logic.
Scenarios:
1. Technical Noise (High compilation errors)
2. Plateau (Stagnant score)
3. Consistent Progress (Steady improvement)
4. Trial & Error (Rapid submissions without logic)
5. Planning (Slow start with high accuracy)
"""

import unittest
from datetime import datetime, timedelta
from models.quiz_models import (
    QuestionData, SubmissionStep, TestCase,
    ProgressState, StrategyProfile, InterventionType
)
from analytics.behavior_engine import derive_pedagogical_decision

class TestBehavioralLogic(unittest.TestCase):

    def create_mock_step(self, seconds_from_start: int, score: float, is_error: bool = False):
        """Helper to create a submission step at a specific time."""
        return SubmissionStep(
            timestamp=datetime(2026, 1, 1, 10, 0) + timedelta(seconds=seconds_from_start),
            score=score,
            test_results=[TestCase(passed=not is_error, is_compilation_error=is_error)]
        )

    def test_technical_noise_detection(self):
        """Scenario: Student is struggling with syntax, sending 4 failing attempts quickly."""
        q = QuestionData(total_submissions=4, final_score=0.0)
        q.steps = [
            self.create_mock_step(10, 0.0, is_error=True),
            self.create_mock_step(20, 0.0, is_error=True),
            self.create_mock_step(30, 0.0, is_error=True),
            self.create_mock_step(40, 0.0, is_error=True),
        ]

        decision = derive_pedagogical_decision(q)
        self.assertTrue(decision.is_technical_noise)
        self.assertEqual(decision.intervention, InterventionType.TECHNICAL)

    def test_plateau_detection(self):
        """Scenario: Student stuck at 60% for several attempts."""
        q = QuestionData(total_submissions=5, final_score=60.0)
        q.steps = [
            self.create_mock_step(60, 20.0),
            self.create_mock_step(120, 60.0),
            self.create_mock_step(300, 60.0),
            self.create_mock_step(400, 60.0),
            self.create_mock_step(500, 60.0),
        ]

        decision = derive_pedagogical_decision(q)
        self.assertEqual(decision.progress, ProgressState.PLATEAU)
        self.assertEqual(decision.intervention, InterventionType.INTERVENE_NOW)

    def test_consistent_progress(self):
        """Scenario: Student shows a healthy learning curve."""
        q = QuestionData(total_submissions=3, final_score=100.0)
        q.steps = [
            self.create_mock_step(100, 30.0),
            self.create_mock_step(300, 70.0),
            self.create_mock_step(600, 100.0),
        ]

        decision = derive_pedagogical_decision(q)
        self.assertEqual(decision.progress, ProgressState.CONSISTENT)
        self.assertEqual(decision.intervention, InterventionType.NONE)

    def test_trial_and_error_strategy(self):
        """Scenario: Many attempts in very short intervals (tinkering)."""
        # Define start time
        start_time = datetime(2026, 1, 1, 10, 0)

        # Initialize QuestionData with the required timestamp
        q = QuestionData(
            total_submissions=6,
            final_score=20.0,
            quiz_start_timestamp=start_time
        )

        q.steps = [
            self.create_mock_step(10, 0.0), # 10s after start
            self.create_mock_step(20, 10.0),
            self.create_mock_step(30, 10.0),
            self.create_mock_step(40, 15.0),
            self.create_mock_step(50, 15.0),
            self.create_mock_step(60, 20.0),
        ]

        decision = derive_pedagogical_decision(q)

        # Validation
        self.assertEqual(decision.strategy, StrategyProfile.TRIAL_AND_ERROR)
        self.assertEqual(decision.intervention, InterventionType.INTERVENE_NOW)

    def test_planning_strategy(self):
        """Scenario: Long wait before first sub, then high score (Reflective)."""
        q = QuestionData(total_submissions=1, final_score=100.0)
        q.quiz_start_timestamp = datetime(2026, 1, 1, 10, 0)
        q.steps = [
            self.create_mock_step(600, 100.0), # 10 minutes wait
        ]

        decision = derive_pedagogical_decision(q)
        self.assertEqual(decision.strategy, StrategyProfile.PLANNING)

if __name__ == '__main__':
    unittest.main()