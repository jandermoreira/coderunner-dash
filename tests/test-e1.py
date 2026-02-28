# Trajetória descritiva
#
# nenhuma dificuldade técnica (compila sempre)
#
# muitas submissões
#
# intervalos curtos (1 min)
#
# progresso pequeno e irregular
#
# testes passam e falham alternadamente
#
# só resolve no final, após várias tentativas

from datetime import datetime, timedelta

from models.quiz_models import (
    UserQuizData,
    QuestionData,
    SubmissionStep,
    TestCase
)

from analytics.pipeline import run_pedagogical_pipeline
from analytics.metrics import calculate_analytics


# --------------------------------------------------
# 1) Timestamps base
# --------------------------------------------------
t0 = datetime(2026, 1, 1, 14, 0, 0)

# --------------------------------------------------
# 2) SubmissionSteps (trajetória E1)
# --------------------------------------------------
steps = [
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=1),
        url="",
        score=20,
        has_compilation_error=False,
        has_runtime_error=False,
        test_results=[
            TestCase(True), TestCase(False), TestCase(False), TestCase(False), TestCase(False)
        ],
    ),
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=2),
        url="",
        score=20,
        has_compilation_error=False,
        has_runtime_error=False,
        test_results=[
            TestCase(False), TestCase(True), TestCase(False), TestCase(False), TestCase(False)
        ],
    ),
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=3),
        url="",
        score=40,
        has_compilation_error=False,
        has_runtime_error=False,
        test_results=[
            TestCase(True), TestCase(True), TestCase(False), TestCase(False), TestCase(False)
        ],
    ),
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=4),
        url="",
        score=40,
        has_compilation_error=False,
        has_runtime_error=False,
        test_results=[
            TestCase(True), TestCase(False), TestCase(True), TestCase(False), TestCase(False)
        ],
    ),
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=5),
        url="",
        score=60,
        has_compilation_error=False,
        has_runtime_error=False,
        test_results=[
            TestCase(True), TestCase(True), TestCase(True), TestCase(False), TestCase(False)
        ],
    ),
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=6),
        url="",
        score=60,
        has_compilation_error=False,
        has_runtime_error=False,
        test_results=[
            TestCase(True), TestCase(False), TestCase(True), TestCase(True), TestCase(False)
        ],
    ),
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=7),
        url="",
        score=80,
        has_compilation_error=False,
        has_runtime_error=False,
        test_results=[
            TestCase(True), TestCase(True), TestCase(True), TestCase(True), TestCase(False)
        ],
    ),
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=8),
        url="",
        score=100,
        has_compilation_error=False,
        has_runtime_error=False,
        test_results=[
            TestCase(True), TestCase(True), TestCase(True), TestCase(True), TestCase(True)
        ],
    ),
]

# --------------------------------------------------
# 3) QuestionData
# --------------------------------------------------
question = QuestionData(
    total_submissions=len(steps),
    final_score=100,
    steps=steps,
)

# --------------------------------------------------
# 4) UserQuizData
# --------------------------------------------------
student = UserQuizData(
    username="student_E1",
    questions=[question],
    quiz_start_timestamp=t0,
    quiz_end_timestamp=t0 + timedelta(minutes=10),
)

# --------------------------------------------------
# 5) Executar pipeline pedagógico
# --------------------------------------------------
enriched_data = run_pedagogical_pipeline([student])

# --------------------------------------------------
# 6) Calcular métricas analíticas
# --------------------------------------------------
df, failures = calculate_analytics(enriched_data)

# --------------------------------------------------
# 7) Inspeção dos resultados
# --------------------------------------------------
decision = enriched_data[0].questions[0].decision

print("=== Decisão pedagógica ===")
print("Progress:", decision.progress)
print("Strategy:", decision.strategy)
print("Intervention:", decision.intervention)
print("Is technical noise:", decision.is_technical_noise)
print("Justification:", decision.justification)

print("\n=== Métricas ===")
print(df)

print("\n=== Padrões de falha ===")
print(failures)
