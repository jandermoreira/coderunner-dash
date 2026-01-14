"""
HTML Parser Module for Moodle Quiz Pages
=========================================

This module parses Moodle HTML to extract CodeRunner submission data.
Updated to handle Moodle Theme Moove, localized headers and numeric dates.
"""

import re
from datetime import datetime
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup
from models.quiz_models import TestCase, SubmissionStep, QuestionData, UserQuizData

def parse_moodle_datetime(text: str) -> Optional[datetime]:
    """
    Parses Moodle PT-BR date strings into datetime objects.
    Supports both:
    1. Extended: "terça, 9 dez 2025, 08:10" or "9 dez 2025, 08:10"
    2. Numeric:  "09/12/2025 08:10" (Common in history tables)
    """
    months_map = {
        "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
        "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12
    }

    text = text.strip().lower()

    try:
        # 1. Try Numeric Format: dd/mm/yyyy HH:MM
        match_num = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})', text)
        if match_num:
            day, month, year, hour, minute = map(int, match_num.groups())
            return datetime(year, month, day, hour, minute)

        # 2. Try Extended Format: [Dayname,] Day Month(abbr) Year, Hour:Minute
        match_ext = re.search(r'(\d{1,2})\s+(\w{3})\s+(\d{4}),?\s+(\d{1,2}):(\d{2})', text)
        if match_ext:
            day, month_abbr, year, hour, minute = match_ext.groups()
            month = months_map.get(month_abbr, 1)
            return datetime(int(year), month, int(day), int(hour), int(minute))

    except (AttributeError, ValueError):
        pass

    return None

def extract_step_id(url: str) -> Optional[int]:
    """Extracts the unique 'step' parameter from a Moodle URL."""
    if not url:
        return None
    match = re.search(r'step=(\d+)', url)
    return int(match.group(1)) if match else None

def extract_available_steps(question_div: Any) -> List[Dict[str, Any]]:
    """
    Scans the history table of a question to find all submission steps.
    """
    steps_metadata = []

    # Locate the history table within the question div
    # Robust selector: tries strict hierarchy first, then falls back to just the table class
    hist_table = question_div.select_one("div.history table.generaltable") or \
                 question_div.select_one("table.generaltable")

    if hist_table and hist_table.tbody:
        rows = hist_table.tbody.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            # Column 0: Link to the step (Step number or "Review")
            action_cell = cells[0]
            link = action_cell.find("a", href=True)

            # We only care about rows that link to a specific step details page
            if link and "reviewquestion.php" in link['href']:
                step_url = link['href']
                step_id = extract_step_id(step_url)

                # Column 1: Timestamp
                ts_text = cells[1].get_text(strip=True)
                timestamp = parse_moodle_datetime(ts_text)

                if step_id is not None and timestamp:
                    steps_metadata.append({
                        "step_id": step_id,
                        "url": step_url,
                        "timestamp": timestamp
                    })

    # Sort by timestamp to ensure chronological order
    steps_metadata.sort(key=lambda x: x["timestamp"])
    return steps_metadata

def parse_step_detail(html: str, timestamp: datetime, url: str) -> SubmissionStep:
    """
    Parses a specific 'reviewquestion.php' page (a single step).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Focus on question wrapper if possible
    q_div = soup.select_one("div.que.coderunner") or soup

    # 1. Score Extraction
    score = 0.0
    grading = q_div.select_one("div.gradingdetails")
    if grading:
        try:
            text = grading.get_text(strip=True)
            # Regex to catch: "Mark 1.00 out of", "Nota 1,00 de", "Atingiu 0.50 de"
            match = re.search(r'([\d.,]+)\s*(?:/|de|out of|de um)', text)
            if match:
                score_str = match.group(1).replace(',', '.')
                score = float(score_str)
        except Exception:
            pass

    # 2. Test Cases Extraction
    test_results = []

    # Strategy: Find table by specific class, OR search for table with expected headers
    test_table = q_div.select_one("table.coderunner-test-results")

    if not test_table:
        # Fallback: Find any table with "Input" or "Teste" headers
        for tbl in q_div.find_all("table"):
            headers = [th.get_text(strip=True).lower() for th in tbl.find_all("th")]
            if any(x in headers for x in ["input", "teste", "test", "esperado"]):
                test_table = tbl
                break

    if test_table and test_table.tbody:
        for row in test_table.tbody.find_all("tr"):
            # Ensure it's not a header row inside body
            if not row.find("td"): continue

            # --- Pass/Fail Detection ---
            passed = False
            # Find icon: search for <i> or <img> with specific classes
            icon = row.select_one(".icon, .fa")

            if icon:
                classes = " ".join(icon.get("class", [])).lower()
                if "check" in classes or "pass" in classes:
                    passed = True

            # --- Error Detection ---
            is_runtime = False
            is_compilation = False

            if not passed:
                row_text = row.get_text().lower()
                if "***run error***" in row_text or "exception" in row_text or "traceback" in row_text:
                    is_runtime = True
                elif "syntaxerror" in row_text or "compilation error" in row_text:
                    is_compilation = True

            test_results.append(TestCase(
                passed=passed,
                is_runtime_error=is_runtime,
                is_compilation_error=is_compilation
            ))

    # 3. Global Error Handling (No table present)
    elif q_div.select_one(".coderunner-test-results.failure") or \
         q_div.select_one(".coderunner-compilation-output") or \
         "syntaxerror" in q_div.get_text().lower():

        test_results.append(TestCase(
            passed=False,
            is_compilation_error=True
        ))

    return SubmissionStep(
        timestamp=timestamp,
        url=url,
        score=score,
        test_results=test_results
    )

def parse_student_page(html: str, username: str) -> UserQuizData:
    """
    Parses the main review page to initialize the UserQuizData structure.
    """
    soup = BeautifulSoup(html, "html.parser")
    user_data = UserQuizData(username=username)

    # 1. Parse Global Quiz Timestamps
    summary_table = soup.select_one("table.quizreviewsummary")
    if summary_table:
        for row in summary_table.find_all("tr"):
            header = row.find("th")
            data = row.find("td")
            if header and data:
                text = header.get_text().lower()
                val = data.get_text(strip=True)
                if "iniciado" in text or "started" in text:
                    user_data.quiz_start_timestamp = parse_moodle_datetime(val)
                if "conclu" in text or "finished" in text:
                    user_data.quiz_end_timestamp = parse_moodle_datetime(val)

    # 2. Identify Questions
    # Captures all questions visible on the main page
    q_divs = soup.select("div.que")
    for div in q_divs:
        # Filter for CodeRunner questions (or others if needed in future)
        if "coderunner" in div.get("class", []):
            q_data = QuestionData(
                total_submissions=0,
                final_score=0.0
            )
            user_data.questions.append(q_data)

    return user_data