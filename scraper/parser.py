"""
HTML Parser Module for Moodle Quiz Pages
=========================================

This module parses Moodle HTML to extract CodeRunner submission data.
It is designed to support incremental updates by first extracting step metadata
(IDs/Timestamps) to allow the scraper to filter out already-processed steps.
"""

import re
from datetime import datetime
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup
from models.quiz_models import TestCase, SubmissionStep, QuestionData, UserQuizData

def parse_moodle_datetime(text: str) -> Optional[datetime]:
    """
    Parses Moodle PT-BR date strings into datetime objects.
    Example: "terça, 9 dez 2025, 08:10" or "9 dez 2025, 08:10"
    """
    months_map = {
        "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
        "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12
    }
    try:
        # Regex matches: Day, Month (3 letters), Year, Hour, Minute
        match = re.search(r'(\d{1,2})\s+(\w{3})\s+(\d{4}),?\s+(\d{1,2}):(\d{2})', text)
        if match:
            day, month_abbr, year, hour, minute = match.groups()
            month = months_map.get(month_abbr.lower(), 1)
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

    Returns a list of metadata dicts used for cache checking:
    [
        {
            "step_id": 12345,       # Unique ID for deduplication
            "url": "...",           # URL to fetch full details
            "timestamp": datetime   # When it happened
        },
        ...
    ]
    """
    steps_metadata = []

    # Locate the history table within the question div
    hist_table = question_div.select_one("div.history table.generaltable")

    if hist_table and hist_table.tbody:
        rows = hist_table.tbody.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            # Check action column for submission links (e.g., "Enviar", "Submetido")
            action_cell = cells[0]
            link = action_cell.find("a", href=True)

            # We only care about rows that link to a specific step state
            if link and "reviewquestion.php" in link['href']:
                step_url = link['href']
                step_id = extract_step_id(step_url)

                # Timestamp is usually in the second column
                ts_text = cells[1].get_text(strip=True)
                timestamp = parse_moodle_datetime(ts_text)

                if step_id and timestamp:
                    steps_metadata.append({
                        "step_id": step_id,
                        "url": step_url,
                        "timestamp": timestamp
                    })

    # Sort by timestamp to ensure chronological order
    steps_metadata.sort(key=lambda x: x["timestamp"])
    return steps_metadata

def parse_step_detail(html: str, timestamp: datetime) -> SubmissionStep:
    """
    Parses a specific 'reviewquestion.php' page (a single step).
    Handles both standard test results and compilation errors.
    """
    soup = BeautifulSoup(html, "html.parser")

    # We focus on the specific question content wrapper
    # Usually class 'que coderunner'
    q_div = soup.select_one("div.que.coderunner") or soup

    # 1. Score Extraction
    score = 0.0
    grading = q_div.select_one("div.gradingdetails")
    if grading:
        try:
            # Looks for "Mark 1.00 out of 1.00" or "Nota 1,00 de 1,00"
            text = grading.get_text(strip=True)
            # Strategy: Find the part before "de" or "out of"
            # Regex designed to catch localized number formats
            match = re.search(r'([\d.,]+)\s*(?:/|de|out of)', text)
            if match:
                score_str = match.group(1).replace(',', '.')
                score = float(score_str)
        except Exception:
            pass # Keep score 0.0 on failure

    # 2. Test Cases Extraction
    test_results = []

    # Attempt A: Standard Test Results Table
    test_table = q_div.select_one("table.coderunner-test-results")

    if test_table and test_table.tbody:
        for row in test_table.tbody.find_all("tr"):
            cols = row.find_all("td")
            if not cols: continue

            # Check icon class for pass/fail
            icon = row.find("i") or row.find("img") # Moodle sometimes uses img
            passed = False
            if icon:
                classes = icon.get("class", [])
                passed = "fa-check" in classes or "icon-check" in str(classes)

            # Identify Runtime Errors in the output column (usually 3rd or 4th)
            is_runtime = False
            if not passed:
                row_text = row.get_text().lower()
                if "exception" in row_text or "error" in row_text:
                    is_runtime = True

            test_results.append(TestCase(
                passed=passed,
                is_runtime_error=is_runtime
            ))

    # Attempt B: Compilation/Syntax Error
    # If no table exists, look for error containers
    elif q_div.select_one(".coderunner-test-results.failure") or \
            q_div.select_one(".coderunner-compilation-output"):

        # Create a single "failed" test case representing the syntax error
        test_results.append(TestCase(
            passed=False,
            is_compilation_error=True
        ))

    return SubmissionStep(
        timestamp=timestamp,
        score=score,
        test_results=test_results
    )

def parse_student_page(html: str, username: str) -> UserQuizData:
    """
    Parses the main review page to initialize the UserQuizData structure.
    Does NOT download steps; merely prepares the container.
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
                elif "conclu" in text or "finished" in text:
                    user_data.quiz_end_timestamp = parse_moodle_datetime(val)

    # 2. Identify Questions (but don't parse deep details yet)
    # We find the question containers to initialize the list
    q_divs = soup.select("div.que.coderunner")
    for div in q_divs:
        # Initialize basic question data
        q_data = QuestionData(
            total_submissions=0, # Will be updated after step processing
            final_score=0.0      # Will be updated after step processing
        )
        user_data.questions.append(q_data)

    return user_data