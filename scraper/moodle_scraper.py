"""
MoodleScraper Module
Manages authentication and incremental data extraction.
"""

import streamlit as st
import httpx
import asyncio
from bs4 import BeautifulSoup
from typing import List, Optional, Set, Tuple
from models.quiz_models import UserQuizData

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
                                         ui_status, existing_user_data: Optional[
                UserQuizData] = None) -> UserQuizData:
        """Extracts history and merges with existing data to enable incremental updates."""
        try:
            if ui_status:
                student_row = ui_status.empty()
                student_row.write(f"🔄 Searching for {student_name}")

            response = await self.http_session.get(review_url)
            current_page_data = parse_student_page(response.text, student_name)

            # Use existing data object if available to preserve previous state
            final_user_data = existing_user_data if existing_user_data else current_page_data

            # Update global metadata from the latest scan
            final_user_data.quiz_start_timestamp = current_page_data.quiz_start_timestamp
            final_user_data.quiz_end_timestamp = current_page_data.quiz_end_timestamp

            soup = BeautifulSoup(response.text, "html.parser")
            question_blocks = soup.select("div.que.coderunner")

            # Index existing steps for fast lookup during the merge
            existing_steps_map = {}
            for question in final_user_data.questions:
                for step in question.steps:
                    if hasattr(step, "url") and step.url:
                        existing_steps_map[step.url] = step

            # No moodle_scraper.py, logo após montar o existing_steps_map:
            if existing_steps_map:
                primeira_url = list(existing_steps_map.keys())[0]
                obj_exemplo = existing_steps_map[primeira_url]

            for index, question_div in enumerate(question_blocks):
                if index >= len(final_user_data.questions):
                    break

                current_question = final_user_data.questions[index]
                steps_metadata = extract_available_steps(question_div)

                merged_steps = []
                for metadata in steps_metadata:
                    step_url = metadata["url"]
                    step_ts = metadata["timestamp"]
                    step_url = metadata["url"]

                    # If step was already downloaded, retrieve it from existing data
                    if step_url in self.steps_urls and step_url in existing_steps_map:
                        merged_steps.append(existing_steps_map[step_url])
                    else:
                        # Caso não exista, baixa e salva a URL no objeto
                        step_response = await self.http_session.get(step_url)
                        step_obj = parse_step_detail(step_response.text, step_ts, step_url)
                        if step_obj:
                            step_obj.url = step_url  # Guarda a URL para a próxima vez
                            merged_steps.append(step_obj)
                            self.steps_urls.add(step_url)

                # Re-sort and update final status
                current_question.steps = sorted(merged_steps, key=lambda s: s.timestamp)
                if current_question.steps:
                    latest = current_question.steps[-1]
                    current_question.final_score = latest.score
                    current_question.test_results = latest.test_results
                    current_question.total_submissions = len(current_question.steps)

            if ui_status:
                student_row.write(f"🟢 {student_name}: Synchronized")

            return final_user_data

        except Exception as error:
            if ui_status:
                student_row.write(f"🔴 {student_name}: Error ({error})")
            return existing_user_data if existing_user_data else UserQuizData(username=student_name)

    async def run(self, quiz_id: str, status_container=None,
                  existing_data: List[UserQuizData] = None
                  ) -> Tuple[List[UserQuizData], Set[str]]:
        """Orchestrates the incremental scraping process for all students."""
        if not await self.login():
            return []

        # Map existing students for fast access
        existing_data_map = {}
        if existing_data:
            for user in existing_data:
                if hasattr(user, "username"):
                    existing_data_map[user.username] = user

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

        results = await asyncio.gather(*tasks)
        final_data = [r for r in results if r is not None]

        return final_data, self.steps_urls

    async def close(self):
        """Closes the HTTP client."""
        await self.http_session.aclose()
