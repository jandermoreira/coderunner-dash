"""
HTML Parser Module for Moodle Quiz Pages
=========================================

This module provides functions to parse Moodle HTML content related to CodeRunner
questions. It extracts submission history, test case results, and scoring details
from the rendered quiz review pages.
"""

from bs4 import BeautifulSoup
from models.quiz_models import TestCase, QuestionData, UserQuizData


def parse_question_div(div) -> QuestionData:
    p_score, t_score = 0.0, 1.0

    grading = div.select_one("div.gradingdetails")
    if grading:
        try:
            score_text = grading.get_text(strip=True).split()[-1]
            if "/" in score_text:
                p, t = score_text.split("/")
                p_score = float(p.replace(",", "."))
                t_score = float(t.replace(".", "").replace(",", "."))
        except Exception:
            pass

    test_results = []
    test_table = div.select_one("table.coderunner-test-results")
    if test_table and test_table.tbody:
        for row in test_table.tbody.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) >= 4:
                icon = cols[0].find("i")
                test_results.append(
                    TestCase(passed="fa-check" in (icon.get("class", []) if icon else []))
                )

    sub_count = 0
    hist_table = div.select_one("div.history table.generaltable")
    if hist_table and hist_table.tbody:
        for row in hist_table.tbody.find_all("tr"):
            if "Enviar:" in row.get_text():
                sub_count += 1

    return QuestionData(
        total_submissions=max(sub_count, 1),
        final_score=round((p_score / t_score) * 100, 1) if t_score > 0 else 0.0,
        test_results=test_results
    )


def parse_student_page(html: str, username: str) -> UserQuizData:
    soup = BeautifulSoup(html, "html.parser")
    q_divs = soup.select("div.que.coderunner")

    user = UserQuizData(username=username)
    for div in q_divs:
        user.questions.append(parse_question_div(div))

    return user
