import streamlit as st
import pandas as pd
import time
import os
import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
import logging



@dataclass
class TestCase:
    passed: bool
    input_data: str
    expected: str
    got: str

@dataclass
class Submission:
    step: str
    timestamp: Optional[datetime]
    state: str
    score: Optional[float]
    is_submission: bool

@dataclass
class QuestionData:
    total_submissions: int
    first_submission_time: Optional[datetime]
    final_score: Optional[float]
    final_status: Optional[str]
    history: List[Submission] = field(default_factory=list)
    test_results: List[TestCase] = field(default_factory=list)
    time_deltas_min: List[int] = field(default_factory=list)

@dataclass
class UserQuizData:
    username: str
    questions: List[QuestionData] = field(default_factory=list)

class MoodleScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.base_url = "https://ava.ufscar.br"
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": f"{self.base_url}/login/index.php"
            },
            follow_redirects=True,
            timeout=60.0,
            cookies=httpx.Cookies()
        )

    async def login(self) -> bool:
        login_path = f"{self.base_url}/login/index.php"
        r1 = await self.client.get(login_path)
        soup = BeautifulSoup(r1.text, "html.parser")

        token_element = soup.find("input", {"name": "logintoken"})
        if not token_element:
            return False

        payload = {
            "username": self.username,
            "password": self.password,
            "logintoken": token_element["value"]
        }

        r2 = await self.client.post(login_path, data=payload)
        return 'sesskey' in r2.text

    def parse_datetime(self, date_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(date_str, "%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            return None

    def extract_grading(self, div) -> Tuple[float, float]:
        grading = div.select_one("div.gradingdetails")
        if not grading:
            return 0.0, 1.0
        try:
            score_text = grading.get_text(strip=True).split()[-1]
            p, t = score_text.split("/")
            return (float(p.replace(",", ".")),
                    float(t.replace(".", "").replace(",", ".")))
        except (IndexError, ValueError):
            return 0.0, 1.0

    def process_question(self, div) -> QuestionData:
        p_score, t_score = self.extract_grading(div)

        # Histórico de Submissões
        history = []
        hist_table = div.select_one("div.history table.generaltable")
        if hist_table and hist_table.tbody:
            for row in hist_table.tbody.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) < 5: continue
                action = cols[2].get_text(strip=True)
                history.append(Submission(
                    step=cols[0].get_text(strip=True),
                    timestamp=self.parse_datetime(cols[1].get_text(strip=True)),
                    state=cols[3].get_text(strip=True),
                    score=p_score,
                    is_submission=action.startswith("Enviar:")
                ))

        # Resultados dos Testes (CodeRunner)
        tests = []
        test_table = div.select_one("table.coderunner-test-results")
        if test_table and test_table.tbody:
            for row in test_table.tbody.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) < 4: continue
                icon = cols[0].find("i")
                tests.append(TestCase(
                    passed="fa-check" in (icon.get("class", []) if icon else []),
                    input_data=cols[1].get_text(strip=True),
                    expected=cols[2].get_text(strip=True),
                    got=cols[3].get_text(strip=True)
                ))

        submissions = [h for h in history if h.is_submission]
        deltas = [
            int((curr.timestamp - prev.timestamp).total_seconds() / 60)
            for prev, curr in zip(submissions, submissions[1:])
            if curr.timestamp and prev.timestamp
        ]

        badge = div.select_one("div.correctness.badge")

        return QuestionData(
            total_submissions=len(submissions),
            first_submission_time=submissions[0].timestamp if submissions else None,
            final_score=round((p_score / t_score) * 100, 1) if t_score > 0 else 0.0,
            final_status=badge.get_text(strip=True) if badge else "N/A",
            history=history,
            test_results=tests,
            time_deltas_min=deltas
        )

    async def get_user_data(self, user_name, url) -> UserQuizData:
        resp = await self.client.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        q_divs = soup.find_all("div", class_="coderunner")

        user_data = UserQuizData(username=user_name)
        for div in q_divs:
            user_data.questions.append(self.process_question(div))
        return user_data

    async def run(self, quiz_id: str) -> List[UserQuizData]:
        if not await self.login():
            logging.error("Falha na autenticação.")
            return []

        results_url = (f"{self.base_url}/mod/quiz/report.php?id={quiz_id}"
                       "&mode=overview&attempts=enrolled_with&onlygraded"
                       "&onlyregraded&slotmarks=1")

        resp = await self.client.get(results_url)
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", class_="generaltable")

        tasks = []
        if table and table.tbody:
            for row in table.tbody.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) < 3: continue
                link = cols[2].find("a", href=lambda h: h and "review.php" in h)
                if link:
                    name = cols[2].get_text(strip=True).replace("Revisão de tentativa", "")
                    tasks.append(self.get_user_data(name, link["href"]))

        return await asyncio.gather(*tasks)

    async def close(self):
        await self.client.aclose()

async def main():
    import os
    USER = os.getenv("MOODLE_USER")
    PASS = os.getenv("MOODLE_PASS")

    scraper = MoodleScraper(USER, PASS)
    try:
        resultados = await scraper.run(QUIZ_ID)
        logging.info(f"Sucesso: {len(resultados)} usuários processados.")
        pprint(resultados)
    finally:
        await scraper.close()

# Configuração da Página Streamlit
st.set_page_config(page_title="Monitor CodeRunner", layout="wide")

async def update_data(scraper, quiz_id):
    """Executa o scraper e retorna os dados processados."""
    try:
        return await scraper.run(quiz_id)
    except Exception as e:
        st.error(f"Erro na coleta: {e}")
        return None

def transform_to_dataframe(resultados):
    """Converte a lista de objetos para um DataFrame tabular para o dashboard."""
    data_list = []
    for user in resultados:
        row = {"Aluno": user.username}
        for i, q in enumerate(user.questions):
            # Coluna por questão: ex: "Q1 (%)"
            row[f"Q{i+1}"] = q.final_score
            row[f"Q{i+1} Tentativas"] = q.total_submissions
        data_list.append(row)
    return pd.DataFrame(data_list)

def run_scraper_sync(scraper, quiz_id):
    """Bridge para rodar o código async dentro do fluxo do Streamlit."""
    return asyncio.run(scraper.run(quiz_id))

# 1. Configuração inicial
st.set_page_config(page_title="Monitor CodeRunner", layout="wide")
st.title("🚀 Monitor de Progresso - CodeRunner")

# 2. Inicialização do estado (Sidebar e Credenciais)
with st.sidebar:
    st.header("Configurações")
    u = st.text_input("Usuário Moodle")
    p = st.text_input("Senha Moodle", type="password")
    qid = st.text_input("ID do Quiz", value="958257")
    refresh = st.slider("Intervalo (min)", 1, 15, 5)

# 3. Placeholder para o conteúdo (Isso garante que a página não fique em branco)
status_box = st.empty()
metrics_area = st.container()
table_area = st.empty()

if u and p:
    # Loop de atualização
    while True:
        status_box.info(f"🔄 Atualizando dados... ({datetime.now().strftime('%H:%M:%S')})")

        # Instancia e roda o scraper
        scraper = MoodleScraper(u, p)
        resultados = run_scraper_sync(scraper, qid)

        if resultados:
            df = transform_to_dataframe(resultados)

            with metrics_area:
                c1, c2 = st.columns(2)
                c1.metric("Alunos Ativos", len(df))
                # Exemplo de alerta de "frustração"
                tentativas_altas = df[df.filter(like="Tentativas").gt(10).any(axis=1)]
                c2.metric("Alunos em Alerta (>10 tent.)", len(tentativas_altas))

            with table_area:
                score_cols = [c for c in df.columns if "Q" in c and "Tentativas" not in c]
                st.dataframe(
                    df.set_index("Aluno")[score_cols].style.background_gradient(cmap="RdYlGn", vmin=0, vmax=100),
                    use_container_width=True
                )

            status_box.success(f"✅ Última atualização: {datetime.now().strftime('%H:%M:%S')}")
        else:
            status_box.error("Falha ao obter dados. Verifique as credenciais ou o ID do Quiz.")

        # Aguarda o tempo definido antes de reiniciar o loop
        time.sleep(refresh * 60)
        st.rerun()
else:
    st.warning("Aguardando credenciais na barra lateral para iniciar...")