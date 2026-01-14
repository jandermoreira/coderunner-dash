"""
Data Models for Quiz Analytics
==============================

This module defines the structured data models for representing quiz results.
Updated to support pedagogical states and behavioral strategy profiling.
The architecture follows a hierarchical approach:
UserQuizData -> QuestionData -> SubmissionStep -> TestCase.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from enum import Enum


class ProgressState(Enum):
    """Represents the pedagogical progress state (Layer 2)."""
    CONSISTENT = "consistent"
    UNSTABLE = "unstable"
    PLATEAU = "plateau"
    NONE = "none"


class StrategyProfile(Enum):
    """Represents the identified resolution strategy (Layer 3)."""
    PLANNING = "planning"
    TRIAL_AND_ERROR = "trial_and_error"
    BRUTE_FORCE = "brute_force"
    GUESSING = "guessing"
    REFINEMENT = "refinement"
    UNKNOWN = "unknown"


class InterventionType(Enum):
    """Represents the recommended action for the teacher (Layer 4)."""
    NONE = "do_not_intervene"
    MONITOR = "monitor"
    TECHNICAL = "technical_only"
    INTERVENE_NOW = "intervene_now"


@dataclass
class PedagogicalDecision:
    """
    Final output of the logic pipeline.
    This is what the UI primarily consumes.
    """
    is_technical_noise: bool = False
    progress: ProgressState = ProgressState.NONE
    strategy: StrategyProfile = StrategyProfile.UNKNOWN
    intervention: InterventionType = InterventionType.NONE
    justification: str = ""


@dataclass
class TestCase:
    """Result of a single test case within a CodeRunner question."""
    passed: bool
    is_compilation_error: bool = False
    is_runtime_error: bool = False


@dataclass
class SubmissionStep:
    """A single student attempt at a specific timestamp."""
    timestamp: datetime
    url: str
    score: float
    test_results: List[TestCase] = field(default_factory=list)


@dataclass
class QuestionData:
    """
    Container for a student's history and resolved states for one question.
    """
    total_submissions: int
    final_score: float
    quiz_start_timestamp: Optional[datetime] = None

    # Raw chronological history
    steps: List[SubmissionStep] = field(default_factory=list)

    # Derived Technical Metrics (Layer 2)
    plateau_duration_steps: int = 0
    test_stability_ratio: float = 1.0
    avg_interval_seconds: float = 0.0

    # Resolved Pedagogical State (Layers 3 & 4)
    # The UI will prioritize this object
    decision: PedagogicalDecision = field(default_factory=PedagogicalDecision)


@dataclass
class UserQuizData:
    """Top-level container for a student's entire quiz performance."""
    username: str
    questions: List[QuestionData] = field(default_factory=list)
    quiz_start_timestamp: Optional[datetime] = None
    quiz_end_timestamp: Optional[datetime] = None

    @property
    def overall_score(self) -> float:
        if not self.questions:
            return 0.0
        return sum(q.final_score for q in self.questions) / len(self.questions)