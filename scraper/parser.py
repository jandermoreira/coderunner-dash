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

def parse_moodle_datetime(text: str) -> datetime:
    """
    Parses Moodle PT-BR date strings into datetime objects.
    Example: "terça, 9 dez 2025, 08:10"
    """
    months_map = {
        "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
        "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12
    }
    try:
        # Regex matches: Day, Month (3 letters), Year, Hour, Minute
        match = re.search(r'(\d{1,2})\s+(\w{3})\s+(\d{4}),\s+(\d{1,2}):(\d{2})', text)
        if match:
            day, month_abbr, year, hour, minute = match.groups()
            month = months_map.get(month_abbr.lower(), 1)
            return datetime(int(year), month, int(day), int(hour), int(minute))
    except (AttributeError, ValueError):
        pass
    return None

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

    # 3. Submission History and Quiz Start extraction
    submission_times = []
    quiz_start_timestamp = None

    hist_table = div.select_one("div.history table.generaltable")
    if hist_table and hist_table.tbody:
        rows = hist_table.tbody.find_all("tr")

        # The last row represents the "Started on" event
        if rows:
            start_cells = rows[-1].find_all("td")
            if len(start_cells) >= 2:
                t_match = re.search(r'(\d{1,2}:\d{2})', start_cells[1].get_text())
                d_match = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', start_cells[1].get_text())
                if t_match and d_match:
                    quiz_start_timestamp = f"{d_match.group(1)} {d_match.group(2)} {d_match.group(3)} {t_match.group(1)}"

        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2 and "Enviar" in cells[0].get_text():
                time_match = re.search(r'(\d{1,2}:\d{2})', cells[1].get_text())
                date_match = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', cells[1].get_text())
                if time_match and date_match:
                    time_str = f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)} {time_match.group(1)}"
                    submission_times.append(time_str)

    tinkering_detected = len(submission_times) >= 4

    return QuestionData(
        total_submissions=max(len(submission_times), 1),
        final_score=round((p_score / t_score) * 100, 1) if t_score > 0 else 0.0,
        test_results=test_results,
        has_tinkering=tinkering_detected,
        quiz_start_timestamp=quiz_start_timestamp
    )

def parse_student_page(html: str, username: str) -> UserQuizData:
    soup = BeautifulSoup(html, "html.parser")
    q_divs = soup.select("div.que.coderunner")

    user = UserQuizData(username=username)

    summary_table = soup.select_one("table.quizreviewsummary")
    quiz_start_date = None
    quiz_end_date = None

    if summary_table:
        rows = summary_table.find_all("tr")
        for row in rows:
            header = row.find("th")
            data = row.find("td")
            if header and data:
                header_text = header.get_text(strip=True)
                if "Iniciado em" in header_text:
                    quiz_start_date = parse_moodle_datetime(data.get_text(strip=True))
                elif "Concluída em" in header_text:
                    quiz_end_date = parse_moodle_datetime(data.get_text(strip=True))
    user.quiz_start_date = quiz_start_date
    user.quiz_end_date = quiz_end_date

    for div in q_divs:
        user.questions.append(parse_question_div(div))

    return user