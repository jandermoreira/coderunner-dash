"""
MoodleScraper Module
Manages authentication and incremental data extraction.
"""

import streamlit as st
import httpx
import asyncio
from bs4 import BeautifulSoup
from typing import List, Optional, Set, Dict

from models.quiz_models import UserQuizData, SubmissionStep
from scraper.parser import (
    parse_student_page,
    extract_available_steps,
    parse_step_detail
)


class MoodleScraper:
    def __init__(self, username: str, password: str, cached_steps: Optional[Set[str]] = None):
        self.username = username
        self.password = password
        self.base_url = "https://ava.ufscar.br"
        self.http_session = httpx.AsyncClient(
            headers={"User-Agent": "MoodleAnalyticsBot/1.0"},
            follow_redirects=True,
            timeout=60.0
        )
        self.steps_urls: Set[str] = cached_steps if cached_steps else set()

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
            return "sesskey" in auth_response.text or "login/logout.php" in auth_response.text
        except Exception as error:
            st.error(f"Authentication Error: {error}")
            return False

    async def fetch_student_full_history(self, student_name: str, review_url: str,
                                         ui_status, existing_user_data: Optional[UserQuizData] = None) -> UserQuizData:
        """Extracts history and merges with existing data to prevent data loss."""
        try:
            response = await self.http_session.get(review_url)

            # Create a fresh parser object for the current page state
            current_page_data = parse_student_page(response.text, student_name)

            # If we have existing data, we use it as the base to preserve metadata
            # otherwise we use the newly parsed structure
            final_user_data = existing_user_data if existing_user_data else current_page_data

            # Update quiz timestamps in case they changed or were missing
            final_user_data.quiz_start_timestamp = current_page_data.quiz_start_timestamp
            final_user_data.quiz_end_timestamp = current_page_data.quiz_end_timestamp

            soup = BeautifulSoup(response.text, "html.parser")
            question_blocks = soup.select("div.que.coderunner")

            # Map existing steps by timestamp for this specific student
            existing_steps_map = {}
            for q in final_user_data.questions:
                for s in q.steps:
                    existing_steps_map[s.timestamp] = s

            for index, question_div in enumerate(question_blocks):
                if index >= len(final_user_data.questions):
                    break

                current_question = final_user_data.questions[index]
                steps_metadata = extract_available_steps(question_div)

                new_question_steps = []
                for metadata in steps_metadata:
                    step_url = metadata["url"]
                    step_ts = metadata["timestamp"]

                    if step_url in self.steps_urls and step_ts in existing_steps_map:
                        new_question_steps.append(existing_steps_map[step_ts])
                    else:
                        step_response = await self.http_session.get(step_url)
                        step_obj = parse_step_detail(step_response.text, step_ts)
                        if step_obj:
                            new_question_steps.append(step_obj)
                            self.steps_urls.add(step_url)

                # Update the question with the combined list of steps
                current_question.steps = sorted(new_question_steps, key=lambda s: s.timestamp)
                if current_question.steps:
                    latest = current_question.steps[-1]
                    current_question.final_score = latest.score
                    current_question.test_results = latest.test_results
                    current_question.total_submissions = len(current_question.steps)

            if ui_status:
                ui_status.write(f"🟢 {student_name}: Synchronized")

            return final_user_data

        except Exception as error:
            if ui_status:
                ui_status.write(f"🔴 {student_name}: Error ({error})")
            return existing_user_data if existing_user_data else UserQuizData(username=student_name)

    async def run(self, quiz_id: str, status_container=None, existing_data: List[UserQuizData] = None) -> List[UserQuizData]:
        """Orchestrates the scraping process."""
        if not await self.login():
            return []

        existing_data_map = {}
        if existing_data and isinstance(existing_data, list):
            for u in existing_data:
                if hasattr(u, "username"):
                    existing_data_map[u.username] = u

        report_url = f"{self.base_url}/mod/quiz/report.php?id={quiz_id}&mode=overview"
        response = await self.http_session.get(report_url)
        soup = BeautifulSoup(response.text, "html.parser")

        table = soup.select_one("table#attempts, table.generaltable")
        if not table:
            return []

        tasks = []
        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 3: continue

            link_tag = cells[2].find("a", href=lambda h: h and "review.php" in h)
            if not link_tag: continue

            raw_name = cells[2].get_text(strip=True)
            clean_name = raw_name.replace("Revisão de tentativa", "").strip()

            tasks.append(self.fetch_student_full_history(
                clean_name, link_tag["href"], status_container, existing_data_map.get(clean_name)
            ))

        return await asyncio.gather(*tasks)

    async def close(self):
        await self.http_session.aclose()