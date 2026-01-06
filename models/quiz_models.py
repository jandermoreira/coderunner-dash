from dataclasses import dataclass, field
from typing import List


@dataclass
class TestCase:
    passed: bool


@dataclass
class QuestionData:
    total_submissions: int
    final_score: float
    test_results: List[TestCase] = field(default_factory=list)


@dataclass
class UserQuizData:
    username: str
    questions: List[QuestionData] = field(default_factory=list)
