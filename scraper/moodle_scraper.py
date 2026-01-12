"""
MoodleScraper Module (Async Version with Incremental Step Fetching)
===================================================================
Orchestrates the fetching of student data.
Strategy:
1. Fetch all student main pages in parallel.
2. For each student, identify missing steps (incremental diff).
3. Fetch missing steps sequentially (to avoid hammering server per student).
4. Merge new steps with cached steps.
"""

import streamlit as st
import httpx
import asyncio
from bs4 import BeautifulSoup
from typing import List, Optional, Dict

# Imports dos seus módulos locais
from models.quiz_models import UserQuizData, QuestionData, SubmissionStep
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

        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
            follow_redirects=True,
            timeout=60.0
        )

    async def login(self) -> bool:
        """Autenticação padrão no Moodle."""
        try:
            login_url = f"{self.base_url}/login/index.php"
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
            r2 = await self.client.post(login_url, data=payload)
            return "logout.php" in r2.text or "Painel" in r2.text
        except Exception as e:
            st.error(f"Login failed: {e}")
            return False

    def _get_cached_student(self, username: str) -> Optional[UserQuizData]:
        """Recover cached data."""
        if "raw_data" in st.session_state and st.session_state.raw_data:
            for user in st.session_state.raw_data:
                # Verifica se é um objeto UserQuizData e não uma string/lixo
                if hasattr(user, 'username') and not isinstance(user, str):
                    if user.username == username:
                        return user
        return None

    async def fetch_step_data(self, url: str, timestamp) -> Optional[SubmissionStep]:
        """Baixa e processa um único step."""
        try:
            resp = await self.client.get(url)
            return parse_step_detail(resp.text, timestamp)
        except Exception as e:
            print(f"Error fetching step {url}: {e}")
            return None

    def _update_question_summary(self, question: QuestionData):
        """
        Atualiza os campos de resumo (nota final, resultados atuais)
        baseado no ÚLTIMO step da lista cronológica.
        """
        if not question.steps:
            return

        # Ordena garantidamente por timestamp
        question.steps.sort(key=lambda x: x.timestamp)

        # Pega o estado mais recente
        last_step = question.steps[-1]

        question.final_score = last_step.score
        question.test_results = last_step.test_results
        question.total_submissions = len(question.steps)

        # Opcional: Recalcular métricas de tinkering aqui ou deixar para metrics.py
        # question.has_tinkering = len(question.steps) >= 4 (exemplo)

    async def fetch_student_details(self, name, review_url, status_container):
        """
        Processa um aluno individualmente:
        1. Baixa página principal.
        2. Identifica steps faltantes.
        3. Baixa steps faltantes.
        4. Mescla com cache.
        """
        full_review_url = review_url if review_url.startswith("http") else f"{self.base_url}{review_url}"

        # 1. Baixa a página principal de revisão
        resp = await self.client.get(full_review_url)
        html = resp.text

        # Parser inicial (cria esqueleto do UserQuizData e Questions)
        new_user_data = parse_student_page(html, name)

        # Recupera cache antigo para este aluno
        cached_user = self._get_cached_student(name)

        # Parse manual para encontrar as DIVs das questões e extrair metadados
        soup = BeautifulSoup(html, "html.parser")
        question_divs = soup.select("div.que.coderunner")

        # Itera sobre cada questão encontrada
        for idx, q_div in enumerate(question_divs):
            if idx >= len(new_user_data.questions):
                break

            current_question = new_user_data.questions[idx]

            # 2. Descobre todos os steps disponíveis no Moodle agora
            available_steps_meta = extract_available_steps(q_div)

            # Recupera steps que já tínhamos em cache
            existing_steps = []
            known_timestamps = set()

            if cached_user and idx < len(cached_user.questions):
                existing_steps = cached_user.questions[idx].steps
                # Criamos um set de timestamps para identificar duplicatas
                # (Assumindo que timestamp é único por tentativa)
                known_timestamps = {s.timestamp for s in existing_steps}

            # 3. Identifica quais steps são NOVOS
            steps_to_fetch = []
            for meta in available_steps_meta:
                if meta["timestamp"] not in known_timestamps:
                    steps_to_fetch.append(meta)

            # 4. Baixa APENAS os steps novos (Sequencial, conforme solicitado)
            new_steps_objects = []
            for meta in steps_to_fetch:
                # Opcional: Feedback visual se houver muitos downloads
                # if status_container: status_container.write(f"Baixando step novo para {name}...")

                step_obj = await self.fetch_step_data(meta["url"], meta["timestamp"])
                if step_obj:
                    new_steps_objects.append(step_obj)

            # 5. Consolidação (Merge)
            # Soma antigos + novos
            all_steps = existing_steps + new_steps_objects

            # Atribui à questão
            current_question.steps = all_steps

            # Atualiza os dados de resumo (Nota final, Testes atuais) baseado no último step
            self._update_question_summary(current_question)

        return new_user_data

    async def run(self, quiz_id, status_container=None) -> List[UserQuizData]:
        """Ponto de entrada principal."""
        if not await self.login():
            st.error("Login falhou.")
            return []

        # URL do relatório geral (lista de alunos)
        report_url = (
            f"{self.base_url}/mod/quiz/report.php?id={quiz_id}"
            "&mode=overview&attempts=enrolled_with&onlygraded"
            "&onlyregraded&slotmarks=1&tsort=firstname&tdir=3"
            "&states=inprogress-finished"
        )
        print(report_url)

        resp = await self.client.get(report_url)
        soup = BeautifulSoup(resp.text, "html.parser")

        table = soup.select_one("table#attempts, table.generaltable")
        if not table:
            st.error("Tabela de resultados não encontrada.")
            return []

        tasks = []
        rows = table.select("tbody tr")

        # Cria tasks para cada aluno (PARALELO)
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3: continue

            link = cols[2].find("a", href=lambda h: h and "review.php" in h)
            if not link: continue

            name = cols[2].get_text(strip=True).replace("Revisão de tentativa", "")

            tasks.append(
                self.fetch_student_details(name, link["href"], status_container)
            )

        if status_container:
            status_container.write(f"🔄 Sincronizando {len(tasks)} alunos...")

        # Executa todos os alunos simultaneamente
        results = await asyncio.gather(*tasks)

        await self.client.aclose()
        return results

    async def close(self):
        """Finaliza o cliente HTTP de forma segura."""
        await self.client.aclose()