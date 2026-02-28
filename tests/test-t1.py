# Trajetória descritiva
#
# várias submissões iniciais com erro de compilação
#
# nenhuma execução possível nesses passos
#
# erro técnico desaparece
#
# progresso contínuo até acerto total
#
# sem regressões de teste

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
t0 = datetime(2026, 1, 1, 11, 0, 0)

# --------------------------------------------------
# 2) SubmissionSteps (trajetória T1)
# --------------------------------------------------
steps = [
    # --- Erro técnico concentrado no início ---
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=1),
        url="",
        score=0,
        has_compilation_error=True,
        has_runtime_error=False,
        test_results=[],
    ),
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=2),
        url="",
        score=0,
        has_compilation_error=True,
        has_runtime_error=False,
        test_results=[],
    ),
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=3),
        url="",
        score=0,
        has_compilation_error=True,
        has_runtime_error=False,
        test_results=[],
    ),

    # --- Código passa a compilar e começa o progresso ---
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=6),
        url="",
        score=40,
        has_compilation_error=False,
        has_runtime_error=False,
        test_results=[
            TestCase(True),
            TestCase(True),
            TestCase(False),
            TestCase(False),
            TestCase(False),
        ],
    ),
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=9),
        url="",
        score=70,
        has_compilation_error=False,
        has_runtime_error=False,
        test_results=[
            TestCase(True),
            TestCase(True),
            TestCase(True),
            TestCase(True),
            TestCase(False),
        ],
    ),
    SubmissionStep(
        timestamp=t0 + timedelta(minutes=12),
        url="",
        score=100,
        has_compilation_error=False,
        has_runtime_error=False,
        test_results=[
            TestCase(True),
            TestCase(True),
            TestCase(True),
            TestCase(True),
            TestCase(True),
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
    username="student_T1",
    questions=[question],
    quiz_start_timestamp=t0,
    quiz_end_timestamp=t0 + timedelta(minutes=15),
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
