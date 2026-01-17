import os
import sys
from datetime import datetime
import pytest

# Adiciona o diretório raiz ao path para encontrar parser.py e models/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scraper.parser import parse_step_detail

# Configure aqui o caminho para seus arquivos HTML locais
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "samples")

def get_html_samples():
    """Lista arquivos .html na pasta de samples para criar testes dinâmicos."""
    if not os.path.exists(SAMPLES_DIR):
        return []
    return [f for f in os.listdir(SAMPLES_DIR) if f.endswith(".html")]

@pytest.mark.parametrize("html_file", get_html_samples())
def test_parse_step_detail_with_local_files(html_file):
    """Testa a extração de dados de arquivos HTML reais salvos localmente."""
    file_path = os.path.join(SAMPLES_DIR, html_file)

    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Executa o parser
    step = parse_step_detail(
        html=html_content,
        timestamp=datetime.now(),
        url="http://localhost/test"
    )

    # Validações baseadas na lógica da função parse_step_detail
    assert step is not None
    assert isinstance(step.score, float)
    assert isinstance(step.test_results, list)

    # Log para inspeção visual durante o teste (use pytest -s)
    print(f"\nFile: {html_file} | Score: {step.score} | Tests: {len(step.test_results)}")