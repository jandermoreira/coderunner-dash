import pickle
from models.quiz_models import UserQuizData, QuestionData, TestCase

def save_data(data, filename="quiz_cache.pkl"):
    with open(filename, "wb") as f:
        pickle.dump(data, f)

# Mock data to test different behaviors, including Tinkering
mock_data = [
    UserQuizData(
        username="Student_Stable",
        questions=[
            # Normal student: 1 attempt, 100% score
            QuestionData(
                total_submissions=1,
                final_score=100.0,
                test_results=[TestCase(passed=True), TestCase(passed=True)],
                has_tinkering=False
            )
        ]
    ),
    UserQuizData(
        username="Student_Tinkering_Q1",
        questions=[
            # Tinkering case: High number of submissions (>= 4)
            # This should trigger the flag in your parser.py logic
            QuestionData(
                total_submissions=6,
                final_score=20.0,
                test_results=[TestCase(passed=True), TestCase(passed=False)],
                has_tinkering=True
            ),
            # Stable on the second question
            QuestionData(
                total_submissions=1,
                final_score=100.0,
                test_results=[TestCase(passed=True)],
                has_tinkering=False
            )
        ]
    ),
    UserQuizData(
        username="Student_Many_Attempts_No_Tinkering",
        questions=[
            # Edge case: High submissions but manual flag is False
            # (e.g., student is making slow, meaningful progress)
            QuestionData(
                total_submissions=10,
                final_score=100.0,
                test_results=[TestCase(passed=True)],
                has_tinkering=False
            )
        ]
    )
]

if __name__ == "__main__":
    save_data(mock_data)
    print("Test cases for Tinkering saved to quiz_cache.pkl")