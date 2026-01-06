import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
import logging

# Configuração de Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


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

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{self.base_url}/login/index.php"
        }

        # Usamos um Client com suporte explícito a cookies persistentes
        self.client = httpx.AsyncClient(
            headers=headers,
            follow_redirects=True, # Importante para seguir o 303 automaticamente
            timeout=40.0,
            cookies=httpx.Cookies()
        )

    async def login(self):
        login_path = f"{self.base_url}/login/index.php"

        # 1. GET para pegar o token e estabelecer a sessão (Cookie MoodleSession)
        r1 = await self.client.get(login_path)
        soup = BeautifulSoup(r1.text, "html.parser")

        token_element = soup.find("input", {"name": "logintoken"})
        if not token_element:
            logging.error("Não foi possível encontrar o logintoken.")
            return False

        token = token_element["value"]

        # 2. Payload exatamente como o navegador envia
        payload = {
            "anchor": "",
            "logintoken": token,
            "username": self.username,
            "password": self.password,
            "rememberusername": "1" # Às vezes ajuda a manter a sessão ativa
        }

        # 3. POST de Login
        # follow_redirects=True fará o httpx seguir o 303 automaticamente
        r2 = await self.client.post(login_path, data=payload)

        # Critério de sucesso: O Moodle deve exibir a chave de sessão (sesskey) no HTML
        if 'sesskey' in r2.text:
            logging.info(f"Login OK! Sessão estabelecida.")
            return True
        else:
            # Se falhar, vamos salvar o motivo para inspeção
            with open("erro_login.html", "w", encoding="utf-8") as f:
                f.write(r2.text)
            logging.error("Falha no login. Verifique 'erro_login.html'.")
            return False

    async def close(self):
        await self.client.aclose()

    def parse_datetime(self, date_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(date_str, "%d/%m/%Y %H:%M")
        except:
            return None

    def extract_grading(self, div) -> Tuple[float, float]:
        try:
            grading = div.select_one("div.gradingdetails")
            if not grading: return 0.0, 1.0
            score_text = grading.get_text(strip=True).split()[-1]
            p, t = score_text.split("/")
            return float(p.replace(",", ".")), float(t.replace(",", "."))
        except:
            return 0.0, 1.0

    def process_question(self, div) -> QuestionData:
        # 1. Histórico
        history = []
        hist_table = div.select_one("div.history table.generaltable")
        p_score, t_score = self.extract_grading(div)

        if hist_table and hist_table.tbody:
            for row in hist_table.tbody.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) < 5: continue

                action = cols[2].get_text(strip=True)
                history.append(Submission(
                    step=cols[0].get_text(strip=True),
                    timestamp=self.parse_datetime(cols[1].get_text(strip=True)),
                    state=cols[3].get_text(strip=True),
                    score=p_score,  # Simplificado para o exemplo
                    is_submission=action.startswith("Enviar:")
                ))

        # 2. Testes
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

        # 3. Deltas de tempo
        submissions = [h for h in history if h.is_submission]
        deltas = []
        for prev, curr in zip(submissions, submissions[1:]):
            if curr.timestamp and prev.timestamp:
                deltas.append(int((curr.timestamp - prev.timestamp).total_seconds() / 60))

        badge = div.select_one("div.correctness.badge")

        return QuestionData(
            total_submissions=len(submissions),
            first_submission_time=submissions[0].timestamp if submissions else None,
            final_score=round((p_score / t_score) * 100, 1) if t_score > 0 else 0,
            final_status=badge.get_text(strip=True) if badge else "N/A",
            history=history,
            test_results=tests,
            time_deltas_min=deltas
        )

    async def get_user_data(self, user_name, url) -> UserQuizData:
        logging.info(f"Processando: {user_name}")
        resp = await self.client.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        q_divs = soup.find_all("div", class_="coderunner")

        user_data = UserQuizData(username=user_name)
        for div in q_divs:
            user_data.questions.append(self.process_question(div))
        return user_data

    async def run(self, quiz_id):
        await self.login()
        results_url = f"{self.base_url}/mod/quiz/report.php?id={quiz_id}&mode=overview&attempts=enrolled_with&onlygraded&onlyregraded&slotmarks=1"

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

        # Executa todas as requisições em paralelo
        all_data = await asyncio.gather(*tasks)
        return all_data


# Exemplo de execução
async def main():
    # Substitua pelas suas credenciais reais para teste
    scraper = MoodleScraper("SEU_USER", "SUA_SENHA")
    sucesso = await scraper.login()

    if sucesso:
        print("Conectado! Agora podemos buscar os dados gráficos.")
        # Aqui você chamaria o restante da lógica de extração
    else:
        print("Falha ao conectar. Verifique usuário/senha.")

    await scraper.close()


if __name__ == "__main__":
    import os
    # Recomendo usar .env para não deixar senhas no código
    USER = os.getenv("MOODLE_USER", "seu_usuario")
    PASS = os.getenv("MOODLE_PASS", "sua_senha")
    QUIZ_ID = "958257"

    async def executar_completo():
        scraper = MoodleScraper(USER, PASS)
        try:
            # O run já chama o login internamente
            resultados = await scraper.run(QUIZ_ID)

            # Aqui os dados estão prontos para o gráfico
            print(f"\nProcessados {len(resultados)} alunos.")
            return resultados
        finally:
            await scraper.close()

    final_results = asyncio.run(executar_completo())