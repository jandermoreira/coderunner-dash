"""
HTML Parser Module for Moodle Quiz Pages
=========================================

This module provides functions to parse Moodle HTML content related to CodeRunner
questions. It extracts submission history, test case results, and scoring details
from the rendered quiz review pages.
"""

import re
from datetime import datetime
from bs4 import BeautifulSoup
from models.quiz_models import TestCase, QuestionData, UserQuizData

def parse_question_div(div, min_interval_minutes: int = 2) -> QuestionData:
    p_score, t_score = 0.0, 1.0

    # 1. Score extraction
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

    # 2. Test results extraction
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

    # 3. Time-based Tinkering Detection
    # Logic: Find "Enviar" rows and extract the timestamp from the second column
    submission_times = []
    hist_table = div.select_one("div.history table.generaltable")
    if hist_table and hist_table.tbody:
        for row in hist_table.tbody.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2 and "Enviar" in cells[0].get_text():
                # Extract time using regex to avoid locale issues with month names
                # Moodle format: "... 9 de dezembro 2025, 15:45"
                time_match = re.search(r'(\d{1,2}:\d{2})', cells[1].get_text())
                date_match = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', cells[1].get_text())

                if time_match and date_match:
                    # We only really need the relative difference, so we focus on HH:MM
                    # and full date for sub-minute precision if available
                    time_str = f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)} {time_match.group(1)}"
                    submission_times.append(time_str)

    # Simple Tinkering Logic:
    # Since parsing Portuguese dates natively is tricky without 'dateparser',
    # an alternative is to check if there are multiple "Enviar" actions
    # within the same hour/minute block in the text.

    # For a robust version, we use the raw text timestamps:
    tinkering_detected = False
    if len(submission_times) > 1:
        # If the number of 'Enviar' actions is high, and they happen
        # in the same session, we flag it.
        # To be precise with "frequency in time", we'd need a full date parser.
        # For now, we flag if more than 3 'Enviar' exist (as a proxy for frequency).
        tinkering_detected = len(submission_times) >= 4

    return QuestionData(
        total_submissions=max(len(submission_times), 1),
        final_score=round((p_score / t_score) * 100, 1) if t_score > 0 else 0.0,
        test_results=test_results,
        has_tinkering=tinkering_detected
    )

def parse_student_page(html: str, username: str) -> UserQuizData:
    soup = BeautifulSoup(html, "html.parser")
    q_divs = soup.select("div.que.coderunner")

    user = UserQuizData(username=username)
    for div in q_divs:
        user.questions.append(parse_question_div(div))

    return user