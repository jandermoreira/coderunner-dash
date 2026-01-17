from scraper.parser import parse_step_detail
from datetime import datetime

files = ["somente-erro-saida.html"]

for f_name in files:
    with open('samples/' +f_name, 'r', encoding='utf-8') as f:
        html = f.read()

    step = parse_step_detail(html, datetime.now(), f_name)

    print(f"\n--- ARQUIVO: {f_name} ---")
    print(f"Nota: {step.score}")
    print(f"Total de Testes: {len(step.test_results)}")

    # Verifica se algum teste foi marcado como erro
    for t in step.test_results:
        print("Comp", t.is_compilation_error)
        print("Exec", t.is_runtime_error)

    comp_err = any(t.is_compilation_error for t in step.test_results)
    runt_err = any(t.is_runtime_error for t in step.test_results)

    print(f"Erro de Compilação Detectado: {comp_err}")
    print(f"Erro de Runtime Detectado: {runt_err}")

    # Se a nota for 0 e não houver erro detectado, há algo errado na lógica
    if step.score == 0 and not (comp_err or runt_err):
        print("⚠️ AVISO: Nota zero mas nenhum erro técnico foi classificado!")