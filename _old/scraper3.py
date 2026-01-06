import streamlit as st
import pandas as pd
import time
import collections
import httpx
import os
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field


# ==========================================
# 1. DATA MODELS
# ==========================================

@dataclass
class TestCase:
    passed: bool


@dataclass
class QuestionData:
    total_submissions: int
    final_score: float
    test_results: List[TestCase] = field(default_factory=list)


@dataclass
class UserQuizData:
    username: str
    questions: List[QuestionData] = field(default_factory=list)


# ==========================================
# 2. ROBUST SCRAPER ENGINE
# ==========================================

class MoodleScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.base_url = "https://ava.ufscar.br"
        self.client = httpx.Client(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            follow_redirects=True,
            timeout=60.0
        )

    def login(self) -> bool:
        try:
            login_url = f"{self.base_url}/login/index.php"
            resp = self.client.get(login_url)
            soup = BeautifulSoup(resp.text, "html.parser")
            token = soup.find("input", {"name": "logintoken"})
            if not token: return False

            payload = {
                "username": self.username,
                "password": self.password,
                "logintoken": token["value"]
            }
            r2 = self.client.post(login_url, data=payload)
            # Check for Moodle session key or logout link to confirm login
            return "sesskey" in r2.text or "login/logout.php" in r2.text
        except:
            return False

    def run(self, quiz_id: str, status_container) -> List[UserQuizData]:
        if not self.login():
            st.error("Login failed! Verify your username and password.")
            return []

        report_url = f"{self.base_url}/mod/quiz/report.php?id={quiz_id}&mode=overview"
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
            if len(cols) < 3: continue

            link = cols[2].find("a", href=lambda h: h and "review.php" in h)
            if link:
                # Mantendo sua lógica original de limpeza do nome
                name = cols[2].get_text(strip=True).replace("Revisão de tentativa", "")

                # status_container.write(f"🔄 **[{idx+1}]** Processing: {name}")
                all_user_data.append(self.fetch_student_details(name, link["href"]))

        return all_user_data

    def fetch_student_details(self, name: str, url: str) -> UserQuizData:
        resp = self.client.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        # CodeRunner questions are usually inside divs with class 'que coderunner'
        q_divs = soup.select("div.que.coderunner")

        user_data = UserQuizData(username=name)
        for div in q_divs:
            user_data.questions.append(self.parse_question_div(div))
        return user_data

    def parse_question_div(self, div) -> QuestionData:
        # 1. Lógica de Score de 0 a 100% (Restaurada)
        p_score, t_score = 0.0, 1.0
        grading = div.select_one("div.gradingdetails")
        if grading:
            try:
                # Extrai o texto final (ex: "1,00/1,00")
                score_text = grading.get_text(strip=True).split()[-1]
                if "/" in score_text:
                    p, t = score_text.split("/")
                    # Converte formato brasileiro (1,50) para float (1.50)
                    p_val = float(p.replace(",", "."))
                    t_val = float(t.replace(".", "").replace(",", "."))
                    p_score, t_score = p_val, t_val
            except Exception:
                pass

        # 2. Extração dos Test Cases (Preservada)
        test_results = []
        test_table = div.select_one("table.coderunner-test-results")
        if test_table and test_table.tbody:
            for row in test_table.tbody.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 4:
                    icon = cols[0].find("i")
                    test_results.append(
                        TestCase(passed="fa-check" in (icon.get("class", []) if icon else [])))

        # 3. Contagem de Tentativas (Lógica original de procurar "Enviar:")
        hist_table = div.select_one("div.history table.generaltable")
        sub_count = 0
        if hist_table and hist_table.tbody:
            for row in hist_table.tbody.find_all("tr"):
                if "Enviar:" in row.get_text():
                    sub_count += 1

        return QuestionData(
            total_submissions=max(sub_count, 1),
            # Cálculo final da porcentagem de 0 a 100
            final_score=round((p_score / t_score) * 100, 1) if t_score > 0 else 0.0,
            test_results=test_results
        )

    def close(self):
        self.client.close()


# ==========================================
# 3. ANALYTICS & UI (Simplified)
# ==========================================

def calculate_analytics(results: List[UserQuizData]):
    flat_data = []
    failure_patterns = collections.defaultdict(int)
    for user in results:
        entry = {"Student": user.username}
        for i, q in enumerate(user.questions):
            entry[f"Q{i + 1} (%)"] = q.final_score
            entry[f"Q{i + 1} Attempts"] = q.total_submissions
            for t_idx, test in enumerate(q.test_results):
                if not test.passed:
                    failure_patterns[f"Q{i + 1}-T{t_idx + 1}"] += 1
        flat_data.append(entry)
    return pd.DataFrame(flat_data), pd.Series(failure_patterns).sort_values(ascending=False)


st.set_page_config(page_title="CodeRunner Dash", layout="wide")

if 'raw_data' not in st.session_state:
    st.session_state.raw_data = None
if 'last_sync' not in st.session_state:
    st.session_state.last_sync = None

st.title("📊 CodeRunner Monitoring System")

with st.sidebar:
    st.header("Settings")
    u_val = st.text_input("User", value=os.getenv("MOODLE_USER", ""))
    p_val = st.text_input("Pass", type="password", value=os.getenv("MOODLE_PASS", ""))
    q_val = st.text_input("Quiz ID", value=os.getenv("MOODLE_QUIZ_ID", "958257"))
    if st.button("🚀 Sync Now"):
        st.session_state.raw_data = "loading"  # Temporary flag

# --- FETCH ---
if st.session_state.raw_data == "loading":
    with st.status("Syncing with Moodle...", expanded=True) as status:
        scr = MoodleScraper(u_val, p_val)
        data = scr.run(q_val, status)
        scr.close()
        if data:
            st.session_state.raw_data = data
            st.session_state.last_sync = datetime.now().strftime('%H:%M:%S')
            st.rerun()
        else:
            st.session_state.raw_data = None
            status.update(label="No data found.", state="error")

# --- DISPLAY ---
if isinstance(st.session_state.raw_data, list):
    df, errors = calculate_analytics(st.session_state.raw_data)

    m1, m2, m3 = st.columns(3)
    m1.metric("Students", len(df))
    m2.metric("Total Submissions", int(df.filter(like="Attempts").sum().sum()))
    m3.metric("Last Sync", st.session_state.last_sync)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Success Distribution")
        st.bar_chart(df.filter(like="(%)").mean(axis=1).value_counts().sort_index())
    with c2:
        st.subheader("Top Roadblocks")
        if not errors.empty:
            st.bar_chart(errors.head(10))
        else:
            st.success("Everything passing!")

    st.subheader("Progress Matrix")
    st.dataframe(
        df.set_index("Student").filter(like="(%)").style.background_gradient(cmap="RdYlGn", vmin=0,
                                                                             vmax=100),
        width=True)
else:
    st.info("Fill credentials and click 'Sync Now'.")
