"""
MoodleScraper Module
====================

This module contains the MoodleScraper class, which is responsible for authenticating
with a Moodle instance, fetching quiz attempt data, and extracting detailed
student submission information.

The scraper navigates the Moodle quiz review interface to collect per-question
performance data, including scores, submission counts, and test case results.
"""

import streamlit as st
import httpx
from bs4 import BeautifulSoup

from models.quiz_models import UserQuizData
from scraper.parser import parse_question_div


class MoodleScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.base_url = "https://ava.ufscar.br"
        self.client = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
            follow_redirects=True,
            timeout=60.0
        )

    def login(self) -> bool:
        try:
            login_url = f"{self.base_url}/login/index.php"
            resp = self.client.get(login_url)
            soup = BeautifulSoup(resp.text, "html.parser")
            token = soup.find("input", {"name": "logintoken"})
            if not token:
                return False

            payload = {
                "username": self.username,
                "password": self.password,
                "logintoken": token["value"]
            }
            r2 = self.client.post(login_url, data=payload)
            return "sesskey" in r2.text or "login/logout.php" in r2.text
        except Exception:
            return False

    def run(self, quiz_id: str, status_container):
        if not self.login():
            st.error("Login failed! Verify your username and password.")
            return []

        report_url = (
            f"{self.base_url}/mod/quiz/report.php?id={quiz_id}"
            "&mode=overview&attempts=enrolled_with&onlygraded"
            "&onlyregraded&slotmarks=1&tsort=firstname&tdir=4"
        )

        resp = self.client.get(report_url)
        soup = BeautifulSoup(resp.text, "html.parser")

        table = soup.select_one("table#attempts, table.generaltable")
        if not table:
            st.error("Results table not found.")
            return []

        all_user_data = []
        rows = table.select("tbody tr")

        for idx, row in enumerate(rows):
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            link = cols[2].find("a", href=lambda h: h and "review.php" in h)
            if not link:
                continue

            name = cols[2].get_text(strip=True).replace("Revisão de tentativa", "")
            status_container.write(f"🔄 **[{idx + 1}]** Processing: {name}")

            all_user_data.append(
                self.fetch_student_details(name, link["href"])
            )

        return all_user_data

    def fetch_student_details(self, name: str, url: str) -> UserQuizData:
        resp = self.client.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        q_divs = soup.select("div.que.coderunner")
        user_data = UserQuizData(username=name)

        for div in q_divs:
            user_data.questions.append(
                parse_question_div(div)
            )

        return user_data

    def close(self):
        self.client.close()
