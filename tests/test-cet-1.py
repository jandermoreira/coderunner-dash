# test_process_description_quick.py

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List
from statistics import mean

from models.quiz_models import (
    UserQuizData,
    QuestionData,
    SubmissionStep,
    TestCase,
)

from analytics.pipeline import run_pedagogical_pipeline


# ==================================================
# Camada descritiva mínima
# ==================================================

@dataclass
class ProcessDescription:
    attempt_pattern: str
    pacing_pattern: str
    stability_pattern: str
    progress_shape: str
    notes: List[str]


def describe_process(question) -> ProcessDescription:
    steps = question.steps
    notes = []

    # -----------------------------
    # attempt_pattern
    # -----------------------------
    if len(steps) <= 3:
        attempt_pattern = "few_attempts"
    elif len(steps) >= 6:
        attempt_pattern = "many_attempts"
        notes.append("várias tentativas")
    else:
        attempt_pattern = "moderate_attempts"

    # -----------------------------
    # pacing_pattern
    # -----------------------------
    if len(steps) < 2:
        pacing_pattern = "unknown_paced"
    else:
        intervals = [
            (steps[i].timestamp - steps[i - 1].timestamp).total_seconds() / 60
            for i in range(1, len(steps))
        ]
        avg_interval = mean(intervals)

        if avg_interval < 2:
            pacing_pattern = "fast_paced"
            notes.append("tentativas em curto intervalo")
        elif avg_interval > 5:
            pacing_pattern = "slow_paced"
        else:
            pacing_pattern = "moderate_paced"

    # -----------------------------
    # stability_pattern
    # -----------------------------
    passed_counts = []
    for step in steps:
        if step.test_results:
            passed_counts.append(sum(1 for t in step.test_results if t.passed))

    if not passed_counts:
        stability_pattern = "no_executable_attempts"
    else:
        deltas = [
            passed_counts[i] - passed_counts[i - 1]
            for i in range(1, len(passed_counts))
        ]

        if all(d >= 0 for d in deltas):
            stability_pattern = "stable_from_start"
        elif any(d < 0 for d in deltas):
            stability_pattern = "early_instability_resolved"
            notes.append("instabilidade intermediária resolvida")
        else:
            stability_pattern = "unstable"

    # -----------------------------
    # progress_shape
    # -----------------------------
    scores = [s.score for s in steps if not s.has_compilation_error]

    if not scores:
        progress_shape = "no_progress"
    else:
        first_nonzero = next((i for i, s in enumerate(scores) if s > 0), None)

        if first_nonzero is None:
            progress_shape = "flat"
        elif first_nonzero >= len(scores) - 2:
            progress_shape = "late_resolution"
            notes.append("progresso concentrado no final")
        elif all(scores[i] <= scores[i + 1] for i in range(len(scores) - 1)):
            progress_shape = "monotonic_growth"
        else:
            progress_shape = "stepwise_growth"

    return ProcessDescription(
        attempt_pattern=attempt_pattern,
        pacing_pattern=pacing_pattern,
        stability_pattern=stability_pattern,
        progress_shape=progress_shape,
        notes=notes,
    )


# ==================================================
# Função utilitária de execução
# ==================================================

def run_and_describe(student):
    enriched = run_pedagogical_pipeline([student])
    question = enriched[0].questions[0]
    return describe_process(question), question.decision


# ==================================================
# Construção dos casos
# ==================================================

def build_C1():
    t0 = datetime(2026, 1, 1, 10, 0, 0)
    steps = [
        SubmissionStep(t0 + timedelta(minutes=3), "", 40, False, False,
                       [TestCase(True), TestCase(True), TestCase(False), TestCase(False), TestCase(False)]),
        SubmissionStep(t0 + timedelta(minutes=6), "", 60, False, False,
                       [TestCase(True), TestCase(True), TestCase(True), TestCase(False), TestCase(False)]),
        SubmissionStep(t0 + timedelta(minutes=9), "", 80, False, False,
                       [TestCase(True), TestCase(True), TestCase(True), TestCase(True), TestCase(False)]),
        SubmissionStep(t0 + timedelta(minutes=12), "", 100, False, False,
                       [TestCase(True)] * 5),
    ]
    q = QuestionData(len(steps), 100, steps=steps)
    return UserQuizData("student_C1", [q], t0, t0 + timedelta(minutes=15))


def build_T1():
    t0 = datetime(2026, 1, 1, 11, 0, 0)
    steps = [
        SubmissionStep(t0 + timedelta(minutes=1), "", 0, True, False, []),
        SubmissionStep(t0 + timedelta(minutes=2), "", 0, True, False, []),
        SubmissionStep(t0 + timedelta(minutes=3), "", 0, True, False, []),
        SubmissionStep(t0 + timedelta(minutes=6), "", 40, False, False,
                       [TestCase(True), TestCase(True), TestCase(False), TestCase(False), TestCase(False)]),
        SubmissionStep(t0 + timedelta(minutes=9), "", 70, False, False,
                       [TestCase(True), TestCase(True), TestCase(True), TestCase(True), TestCase(False)]),
        SubmissionStep(t0 + timedelta(minutes=12), "", 100, False, False,
                       [TestCase(True)] * 5),
    ]
    q = QuestionData(len(steps), 100, steps=steps)
    return UserQuizData("student_T1", [q], t0, t0 + timedelta(minutes=15))


def build_E1():
    t0 = datetime(2026, 1, 1, 14, 0, 0)
    steps = [
        SubmissionStep(t0 + timedelta(minutes=i+1), "", score, False, False, tests)
        for i, (score, tests) in enumerate([
            (20, [TestCase(True), TestCase(False), TestCase(False), TestCase(False), TestCase(False)]),
            (20, [TestCase(False), TestCase(True), TestCase(False), TestCase(False), TestCase(False)]),
            (40, [TestCase(True), TestCase(True), TestCase(False), TestCase(False), TestCase(False)]),
            (40, [TestCase(True), TestCase(False), TestCase(True), TestCase(False), TestCase(False)]),
            (60, [TestCase(True), TestCase(True), TestCase(True), TestCase(False), TestCase(False)]),
            (60, [TestCase(True), TestCase(False), TestCase(True), TestCase(True), TestCase(False)]),
            (80, [TestCase(True), TestCase(True), TestCase(True), TestCase(True), TestCase(False)]),
            (100, [TestCase(True)] * 5),
        ])
    ]
    q = QuestionData(len(steps), 100, steps=steps)
    return UserQuizData("student_E1", [q], t0, t0 + timedelta(minutes=10))


# ==================================================
# Execução dos testes rápidos
# ==================================================

students = {
    "C1": build_C1(),
    "T1": build_T1(),
    "E1": build_E1(),
}

for label, student in students.items():
    desc, decision = run_and_describe(student)

    # Decisão nunca deve mudar
    assert decision.intervention.name == "NONE", f"{label}: intervenção inesperada"

    if label == "C1":
        assert desc.attempt_pattern == "moderate_attempts"
        assert desc.pacing_pattern == "moderate_paced"
        assert desc.stability_pattern == "stable_from_start"
        assert desc.progress_shape == "monotonic_growth"

    if label == "T1":
        assert desc.attempt_pattern == "many_attempts"
        assert desc.progress_shape == "monotonic_growth"

    if label == "E1":
        assert desc.attempt_pattern == "many_attempts"
        assert desc.pacing_pattern == "fast_paced"
        assert desc.stability_pattern == "early_instability_resolved"
        assert desc.progress_shape in {"stepwise_growth", "late_resolution"}

    print(f"{label} OK -> {desc}")

print("\nTodos os testes rápidos passaram com sucesso.")
