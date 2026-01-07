import pickle
from models.quiz_models import UserQuizData, QuestionData, TestCase


def save_data(data, filename="quiz_cache.pkl"):
    with open(filename, "wb") as f:
        pickle.dump(data, f)


mock_data = [
    UserQuizData(
        username="Group 1",
        questions=[
            QuestionData(
                total_submissions=2, final_score=100.0,
                test_results=[TestCase(passed=True), TestCase(passed=True)]
            ),
            QuestionData(
                total_submissions=1, final_score=50.0,
                test_results=[TestCase(passed=True), TestCase(passed=False)])
        ]
    ),
    UserQuizData(
        username="Group 2",
        questions=[
            QuestionData(
                total_submissions=5, final_score=0.0,
                test_results=[TestCase(passed=False), TestCase(passed=True),
                              TestCase(passed=True), TestCase(passed=False)]
            ),
            QuestionData(
                total_submissions=1, final_score=100.0,
                test_results=[TestCase(passed=True), TestCase(passed=True)]
            )
        ]
    )
]

if __name__ == "__main__":
    save_data(mock_data)
    print("Dados salvos em quiz_cache.pkl")
