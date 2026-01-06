import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any, Tuple
from pprint import pprint

ID = "958257"
BASE_URL = "https://ava.ufscar.br"
LOGIN_URL = f"{BASE_URL}/login/index.php"


def login():
    """
    Login and open session
    :return: session
    """

    username = ""
    password = ""
    session = requests.Session()
    login_page = session.get(LOGIN_URL)
    soup = BeautifulSoup(login_page.text, "html.parser")
    logintoken = soup.find("input", {"name": "logintoken"})["value"]
    payload = {
        "username": username,
        "password": password,
        "logintoken": logintoken
    }

    login_response = session.post(LOGIN_URL, data=payload)

    if "loginerrormessage" in login_response.text:
        raise RuntimeError("Falha no login")

    return session


def get_users_and_links(session, quiz_id):
    """
    Retrieve lists of users and URLs for attempts
    :param session: current session
    :param quiz_id: numeric id
    :return: list of (user, url)
    """
    results_url = (
        f"{BASE_URL}/mod/quiz/report.php?id={quiz_id}"
        "&mode=overview&attempts=enrolled_with&onlygraded"
        "&onlyregraded&slotmarks=1&tsort=firstname&tdir=4"
    )

    results_page = session.get(results_url)
    soup = BeautifulSoup(results_page.text, "html.parser")

    users_and_links = []

    table = soup.find("table", class_="generaltable")

    for row in table.tbody.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        nome = cols[2].get_text(strip=True).replace("Revisão de tentativa", "")
        href = cols[2].find("a", href=lambda h: h and "review.php" in h)
        if href:
            url = href["href"]
            users_and_links.append((nome, url))

    return users_and_links


def get_questions(session, url):
    """
    Retrieve code runner questions from quiz response
    :param session: current session
    :param url: quiz attempt URL
    :return: data from the response
    """
    attempt_page = session.get(url)
    soup = BeautifulSoup(attempt_page.text, "html.parser")
    questions = soup.find_all("div", class_="coderunner")

    for question in questions:
        process_question(question)


def generate_data(session, users_and_links):
    """
    Generate data
    :param users_and_links: list of (user, link to answers page)
    :return: data
    """
    data = []
    for user, link in users_and_links:
        print(">>>", user)

        questions = get_questions(session, link)
        print(f" {len(questions)} questions")

    return (
        user,
        data
    )


def parse_datetime_br(value: str) -> datetime:
    """
    Parses Moodle Brazilian datetime format: DD/MM/YYYY HH:MM
    """
    return datetime.strptime(value, "%d/%m/%Y %H:%M")


def extract_submission_history(question_div) -> List[Dict[str, Any]]:
    """
    Extracts objective submission history from a CodeRunner question.

    Returns one dict per submission step.
    """
    history = []

    history_div = question_div.find("div", class_="history")
    if not history_div:
        return history

    table = history_div.find("table", class_="generaltable")
    if not table or not table.tbody:
        return history

    _, total_score = extract_grading(question_div)

    for row in table.tbody.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        step = cols[0].get_text(strip=True)
        timestamp_raw = cols[1].get_text(strip=True)
        action = cols[2].get_text(strip=True)
        state = cols[3].get_text(strip=True)
        score_text = cols[4].get_text(strip=True)
        score = None
        if score_text:
            score = float() / total_score * 100

        history.append({
            "step": step,
            "timestamp": parse_datetime_br(timestamp_raw),
            # "action": action,
            "state": state,
            "score": score,
            "is_submission": action.startswith("Enviar:")
        })

    return history


def extract_test_results(question_div) -> List[Dict[str, Any]]:
    """
    Extracts objective test case results from CodeRunner feedback.
    """
    results = []

    results_table = question_div.select_one("table.coderunner-test-results")
    if not results_table or not results_table.tbody:
        return results

    for row in results_table.tbody.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        status_icon = cols[0].find("i")
        passed = "fa-check" in status_icon.get("class", []) if status_icon else False

        results.append({
            "passed": passed,
            "input": cols[1].get_text(strip=True),
            "expected": cols[2].get_text(strip=True),
            "got": cols[3].get_text(strip=True),
        })

    return results

# def extract_test_results(question_div):
#     """
#     Returns objective test case information from a CodeRunner question.
#
#     Output:
#         {
#             "total_tests": int,
#             "passed_tests": int,
#             "failed_tests": int,
#             "tests": [
#                 {
#                     "index": int,
#                     "passed": bool
#                 },
#                 ...
#             ]
#         }
#     """
#     summary = {
#         "total_tests": 0,
#         "passed_tests": 0,
#         "failed_tests": 0,
#         "tests": []
#     }
#
#     table = question_div.select_one("table.coderunner-test-results")
#     if not table or not table.tbody:
#         return summary
#
#     rows = table.tbody.find_all("tr")
#     summary["total_tests"] = len(rows)
#
#     for idx, row in enumerate(rows, start=1):
#         icon = row.find("i")
#         passed = False
#
#         if icon and "fa-check" in icon.get("class", []):
#             passed = True
#             summary["passed_tests"] += 1
#         else:
#             summary["failed_tests"] += 1
#
#         summary["tests"].append(passed)
#             # {"index": idx, "passed": passed}
#
#     return summary


def extract_grading(question_div) -> Tuple[float, float]:
    """
    Extracts student grade and total grade
    """
    grading = question_div.select_one("div.gradingdetails")
    if not grading:
        return None
    else:
        score_text = grading.get_text(strip=True).split()[-1]
        partial_score = float(score_text.split("/")[0].replace(",", "."))
        total_score = float(score_text.split("/")[1].replace(".", "").replace(",", "."))
        return partial_score, total_score


def extract_final_outcome(question_div) -> Dict[str, Any]:
    """
    Extracts final outcome indicators.
    """
    badge = question_div.select_one("div.correctness.badge")
    compound_score = extract_grading(question_div)
    final_score = None
    if compound_score:
        partial_score, total_score = compound_score
        final_score = round(partial_score / total_score * 100, 0)

    return {
        "final_status": badge.get_text(strip=True) if badge else None,
        "final_score": final_score
    }


def process_question(question_div) -> Dict[str, Any]:
    """
    Processes a single CodeRunner question div.
    """
    history = extract_submission_history(question_div)
    submissions = [h for h in history if h["is_submission"]]

    first_submission_time = submissions[0]["timestamp"] if submissions else None

    time_deltas = []
    for prev, curr in zip(submissions, submissions[1:]):
        delta = (curr["timestamp"] - prev["timestamp"]).total_seconds()
        time_deltas.append(int(delta / 60.0))

    final_outcome = extract_final_outcome(question_div)

    return {
        # "question_id": question_div.get("id"),
        "total_submissions": len(submissions),
        "first_submission_time": first_submission_time,
        "submission_history": history,
        "time_between_submissions_minutes": time_deltas,
        "test_results": extract_test_results(question_div),
        "final_score": final_outcome["final_score"],
        "final_status": final_outcome["final_status"],
    }


def main():
    session = login()
    users_and_links = get_users_and_links(session, ID)
    print(f"{len(users_and_links)} submissões recuperadas")
    data = generate_data(session, users_and_links)


if __name__ == "__main__":
    # main()
    with open("../sample-data/exemplo-tentativa5.html") as source:
        soup = BeautifulSoup(source, "html.parser")
        questions = soup.find_all("div", class_="coderunner")
        result = process_question(questions[1])
        pprint(result)
