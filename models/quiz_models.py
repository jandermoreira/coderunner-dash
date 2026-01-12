"""
Data Models for Quiz Analytics
==============================

This module defines the structured data models for representing quiz results.
The architecture follows a hierarchical approach:
UserQuizData -> QuestionData -> SubmissionStep -> TestCase.

This structure allows for granular tracking of student progress over time,
enabling precise regression analysis and strategy identification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Union


@dataclass
class TestCase:
    """
    Represents the result of a single test case within a CodeRunner question.
    """
    passed: bool
    is_compilation_error: bool = False
    is_runtime_error: bool = False


@dataclass
class SubmissionStep:
    """
    Represents a single submission (a 'step' in Moodle) for a specific question.

    Attributes:
        timestamp: The exact date and time when the submission occurred.
        score: The partial score achieved in this specific attempt (0.0 to 100.0).
        test_results: A list of TestCase results for this specific attempt.
    """
    timestamp: datetime
    score: float
    test_results: List[TestCase] = field(default_factory=list)


@dataclass
class QuestionData:
    """
    Container for all data related to a single question in a quiz.

    This model stores both the aggregate final state and the full history
    of attempts (steps) made by the student.
    """
    # Summary Metrics
    total_submissions: int
    final_score: float

    # Current State (Reference to the latest successful or last submission)
    test_results: List[TestCase] = field(default_factory=list)

    # Chronological History
    steps: List[SubmissionStep] = field(default_factory=list)

    # Analytics and Behavioral Metadata
    has_tinkering: bool = False
    quiz_start_timestamp: Optional[datetime] = None
    technical_noise_ratio: float = 0.0  # Ratio of errors vs logical attempts
    strategy_label: str = "Unknown"    # e.g., "Steady Progress", "Struggling"
    intervention_priority: str = "Low" # Low, Medium, High


@dataclass
class UserQuizData:
    """
    Top-level container representing a student's entire performance in a quiz.
    """
    username: str
    questions: List[QuestionData] = field(default_factory=list)
    quiz_start_timestamp: Optional[datetime] = None
    quiz_end_timestamp: Optional[datetime] = None

    @property
    def overall_progress(self) -> float:
        """Calculates the average score across all questions."""
        if not self.questions:
            return 0.0
        total = sum(q.final_score for q in self.questions)
        return round(total / len(self.questions), 1)