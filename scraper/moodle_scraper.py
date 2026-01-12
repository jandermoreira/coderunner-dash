"""
MoodleScraper Module
====================
Orchestrates student data recovery with a focus on incremental history fetching.
All internal documentation and comments are in English as requested.
"""

import streamlit as st
import httpx
import asyncio
from bs4 import BeautifulSoup
from typing import List, Optional, Set

from models.quiz_models import UserQuizData, SubmissionStep
from scraper.parser import (
    parse_student_page,
    extract_available_steps,
    parse_step_detail
)

class MoodleScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.base_url = "https://ava.ufscar.br"
        # persistent client for connection pooling
        self.http_session = httpx.AsyncClient(
            headers={"User-Agent": "MoodleAnalyticsBot/1.0"},
            follow_redirects=True,
            timeout=60.0
        )

    async def login(self) -> bool:
        """Authenticates the session using Moodle's login form tokens."""
        try:
            login_endpoint = f"{self.base_url}/login/index.php"
            initial_page = await self.http_session.get(login_endpoint)
            login_soup = BeautifulSoup(initial_page.text, "html.parser")

            login_token = login_soup.find("input", {"name": "logintoken"})
            if not login_token:
                return False

            credentials_payload = {
                "username": self.username,
                "password": self.password,
                "logintoken": login_token["value"]
            }

            auth_response = await self.http_session.post(login_endpoint, data=credentials_payload)
            # Login is successful if we see the session key or logout link
            return "sesskey" in auth_response.text or "login/logout.php" in auth_response.text
        except Exception as auth_error:
            st.error(f"Authentication Error: {auth_error}")
            return False

    def _get_student_from_cache(self, student_name: str) -> Optional[UserQuizData]:
        """Checks session state for existing data to skip already downloaded steps."""
        if "raw_data" in st.session_state:
            for cached_student in st.session_state.raw_data:
                if hasattr(cached_student, 'username') and cached_student.username == student_name:
                    return cached_student
        return None

    async def fetch_student_full_history(self, student_name: str, review_url: str, ui_status) -> UserQuizData:
        """
        Deep dives into a student's attempt to retrieve every submission step.
        """
        try:
            # 1. Fetch the main review page to get the question layout
            review_response = await self.http_session.get(review_url)
            student_quiz_record = parse_student_page(review_response.text, student_name)

            cached_record = self._get_student_from_cache(student_name)
            review_soup = BeautifulSoup(review_response.text, "html.parser")
            question_blocks = review_soup.select("div.que.coderunner")

            for index, question_div in enumerate(question_blocks):
                if index >= len(student_quiz_record.questions):
                    break

                target_question = student_quiz_record.questions[index]
                # Discover steps metadata (IDs, URLs, timestamps) from the history table
                available_steps_meta = extract_available_steps(question_div)

                existing_steps: List[SubmissionStep] = []
                known_timestamps: Set = set()

                if cached_record and index < len(cached_record.questions):
                    existing_steps = cached_record.questions[index].steps
                    known_timestamps = {step.timestamp for step in existing_steps}

                # Download only the steps missing from our local history
                newly_discovered_steps = []
                for step_meta in available_steps_meta:
                    if step_meta["timestamp"] not in known_timestamps:
                        # Fetch specific step detail page
                        step_detail_response = await self.http_session.get(step_meta["url"])
                        parsed_step = parse_step_detail(step_detail_response.text, step_meta["timestamp"])
                        if parsed_step:
                            newly_discovered_steps.append(parsed_step)

                # Consolidate and sort chronologically
                total_history = existing_steps + newly_discovered_steps
                target_question.steps = sorted(total_history, key=lambda s: s.timestamp)

                # Sync final question status with the most recent step
                if target_question.steps:
                    most_recent_step = target_question.steps[-1]
                    target_question.final_score = most_recent_step.score
                    target_question.test_results = most_recent_step.test_results
                    target_question.total_submissions = len(target_question.steps)

            if ui_status:
                ui_status.write(f"🟢 {student_name}: History Synchronized")
            return student_quiz_record

        except Exception as student_fetch_error:
            if ui_status:
                ui_status.write(f"🔴 {student_name}: Fetch failed ({student_fetch_error})")
            return UserQuizData(username=student_name)

    async def run(self, quiz_id: str, status_container=None) -> List[UserQuizData]:
        """Orchestrates the discovery of students and triggers their history fetch."""
        # Simplified URL to avoid filter-based empty states
        report_overview_url = f"{self.base_url}/mod/quiz/report.php?id={quiz_id}&mode=overview"
        report_page_response = await self.http_session.get(report_overview_url)
        report_soup = BeautifulSoup(report_page_response.text, "html.parser")

        student_table = report_soup.select_one("table#attempts, table.generaltable")
        if not student_table:
            return []

        all_fetch_tasks = []
        table_rows = student_table.select("tbody tr")

        for row in table_rows:
            row_cells = row.find_all("td")
            if len(row_cells) < 3:
                continue

            # Robust search for the "Review attempt" link across all columns
            active_review_url = None
            student_display_name = "Unknown"

            for cell in row_cells:
                link_tag = cell.find("a", href=lambda h: h and "review.php" in h)
                if link_tag:
                    active_review_url = link_tag["href"]
                    # Clean the student name from the link text or cell content
                    student_display_name = cell.get_text(strip=True).replace("Revisão de tentativa", "").strip()
                    break

            if active_review_url:
                # Ensure the URL is absolute for httpx
                if not active_review_url.startswith("http"):
                    active_review_url = f"{self.base_url}/mod/quiz/{active_review_url}"

                all_fetch_tasks.append(
                    self.fetch_student_full_history(
                        student_display_name,
                        active_review_url,
                        status_container
                    )
                )

        if not all_fetch_tasks:
            return []

        # Concurrently fetch all student details
        results = await asyncio.gather(*all_fetch_tasks)
        return list(results)

    async def close(self):
        """Cleanly closes the underlying HTTP transport."""
        await self.http_session.aclose()