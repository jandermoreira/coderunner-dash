"""
Data Models for Quiz Analytics
==============================

This module defines the data structures used to represent quiz results throughout
the scraping and analysis pipeline. All models are implemented as dataclasses.
"""

from dataclasses import dataclass, field
from typing import List, Any


@dataclass
class TestCase:
    passed: bool
    is_compilation_error: bool = False
    is_runtime_error: bool = False


@dataclass
class QuestionData:
    total_submissions: int
    final_score: float
    test_results: List[TestCase] = field(default_factory=list)
    has_tinkering: bool = False
    quiz_start_timestamp: str = None
    technical_noise_ratio: float = 0.0
    strategy_label: str = "Unknown"
    intervention_priority: str = "Low"


@dataclass
class UserQuizData:
    username: str
    questions: List[QuestionData] = field(default_factory=list)
    quiz_start_timestamp: Any = None
    quiz_end_timestamp: Any = None
