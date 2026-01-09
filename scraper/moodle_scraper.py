"""
MoodleScraper Module (Async Version)
====================================
Restores asynchronous fetching using httpx.AsyncClient and asyncio.gather.
"""

import streamlit as st
import httpx
import asyncio
from bs4 import BeautifulSoup
from typing import List

# Ensure these imports match your project structure
from models.quiz_models import UserQuizData
from scraper.parser import parse_student_page


class MoodleScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.base_url = "https://ava.ufscar.br"
        # Changed to AsyncClient
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
            follow_redirects=True,
            timeout=60.0
        )

    async def login(self) -> bool:
        """Authenticates asynchronously."""
        try:
            login_url = f"{self.base_url}/login/index.php"
            # Await the GET request
            resp = await self.client.get(login_url)
            soup = BeautifulSoup(resp.text, "html.parser")
            token = soup.find("input", {"name": "logintoken"})
            if not token:
                return False

            payload = {
                "username": self.username,
                "password": self.password,
                "logintoken": token["value"]
            }
            # Await the POST request
            r2 = await self.client.post(login_url, data=payload)
            return "sesskey" in r2.text or "login/logout.php" in r2.text
        except Exception as e:
            st.error(f"Login Error: {e}")
            return False

    async def fetch_student_details(self, name: str, url: str, status_container) -> UserQuizData:
        """
        Fetches a specific student's review page asynchronously
        and hands the HTML to the synchronous parser.
        """
        try:
            status_container.write(f"⚪ {name}")
            resp = await self.client.get(url)
            status_container.write(f"🟢 {name}")
            return parse_student_page(resp.text, name)
        except Exception as e:
            st.warning(f"Failed to fetch data for {name}: {e}")
            return UserQuizData(username=name)

    async def run(self, quiz_id: str, status_container=None) -> List[UserQuizData]:
        """
        Main execution flow:
        1. Login
        2. Get main report table
        3. Create async tasks for every student link
        4. Execute all tasks in parallel
        """
        if not await self.login():
            st.error("Login failed! Verify your username and password.")
            return []

        report_url = (
            f"{self.base_url}/mod/quiz/report.php?id={quiz_id}"
            "&mode=overview&attempts=enrolled_with&onlygraded"
            "&onlyregraded&slotmarks=1&tsort=firstname&tdir=3"
            "&states=inprogress"
        )

        resp = await self.client.get(report_url)
        soup = BeautifulSoup(resp.text, "html.parser")

        table = soup.select_one("table#attempts, table.generaltable")
        if not table:
            st.error("Results table not found. Check Quiz ID or permissions.")
            return []

        tasks = []
        rows = table.select("tbody tr")

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            # Find the review link
            link = cols[2].find("a", href=lambda h: h and "review.php" in h)
            if not link:
                continue

            name = cols[2].get_text(strip=True).replace("Revisão de tentativa", "")

            # Create a coroutine object for this student and add to tasks list
            tasks.append(self.fetch_student_details(name, link["href"], status_container))

        if status_container:
            status_container.write(f"🚀 Starting fetch for {len(tasks)} students...")

        # Run all requests in parallel
        results = await asyncio.gather(*tasks)
        return results

    async def close(self):
        """Closes the async client session."""
        await self.client.aclose()
