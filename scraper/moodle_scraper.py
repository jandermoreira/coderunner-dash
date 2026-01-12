"""
MoodleScraper Module
Manages authentication and incremental data extraction.
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
        self.http_session = httpx.AsyncClient(
            headers={"User-Agent": "MoodleAnalyticsBot/1.0"},
            follow_redirects=True,
            timeout=60.0
        )

    async def login(self) -> bool:
        """Asynchronous authentication using Moodle login tokens."""
        try:
            login_endpoint = f"{self.base_url}/login/index.php"
            response = await self.http_session.get(login_endpoint)
            soup = BeautifulSoup(response.text, "html.parser")

            token = soup.find("input", {"name": "logintoken"})
            if not token:
                return False

            payload = {
                "username": self.username,
                "password": self.password,
                "logintoken": token["value"]
            }

            auth_response = await self.http_session.post(login_endpoint, data=payload)
            # Validates login by checking for session key or logout link presence
            return "sesskey" in auth_response.text or "login/logout.php" in auth_response.text
        except Exception as error:
            st.error(f"Authentication Error: {error}")
            return False

    async def fetch_student_full_history(self, student_name: str, review_url: str,
                                         ui_status) -> UserQuizData:
        """Extracts the full submission history for a single student."""
        try:
            response = await self.http_session.get(review_url)
            # Initialize basic structure (start/end timestamps)
            student_quiz_data = parse_student_page(response.text, student_name)

            soup = BeautifulSoup(response.text, "html.parser")
            question_blocks = soup.select("div.que.coderunner")

            for index, question_div in enumerate(question_blocks):
                if index >= len(student_quiz_data.questions):
                    break

                current_question = student_quiz_data.questions[index]
                # Retrieve submission links from the history table
                steps_metadata = extract_available_steps(question_div)

                question_steps = []
                for metadata in steps_metadata:
                    # Download the detailed page for each individual submission
                    step_response = await self.http_session.get(metadata["url"])
                    step_object = parse_step_detail(step_response.text, metadata["timestamp"])
                    if step_object:
                        question_steps.append(step_object)

                # Sort and update question metrics
                current_question.steps = sorted(question_steps, key=lambda step: step.timestamp)
                if current_question.steps:
                    latest_step = current_question.steps[-1]
                    current_question.final_score = latest_step.score
                    current_question.test_results = latest_step.test_results
                    current_question.total_submissions = len(current_question.steps)

            if ui_status:
                ui_status.write(f"🟢 {student_name}: Synchronized")
            return student_quiz_data

        except Exception as error:
            if ui_status:
                ui_status.write(f"🔴 {student_name}: Error ({error})")
            return UserQuizData(username=student_name)

    async def run(self, quiz_id: str, status_container=None) -> List[UserQuizData]:
        """Orchestrates parallel fetching for all students in the quiz."""
        if not await self.login():
            return []

        report_url = f"{self.base_url}/mod/quiz/report.php?id={quiz_id}&mode=overview"
        response = await self.http_session.get(report_url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Select the attempts table by common Moodle IDs/classes
        table = soup.select_one("table#attempts, table.generaltable")
        if not table:
            return []

        fetching_tasks = []
        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            # Locate the review link within the row
            review_link_tag = cells[2].find("a", href=lambda href: href and "review.php" in href)
            if not review_link_tag:
                continue

            # Clean student name by removing the Moodle "Review attempt" label
            raw_name_text = cells[2].get_text(strip=True)
            clean_name = raw_name_text.replace("Revisão de tentativa", "").strip()

            fetching_tasks.append(
                self.fetch_student_full_history(clean_name, review_link_tag["href"],
                                                status_container)
            )

        # Execute all student history fetches concurrently
        return await asyncio.gather(*fetching_tasks)

    async def close(self):
        """Closes the asynchronous HTTP session."""
        await self.http_session.aclose()
