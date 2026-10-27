"""
Testes unitários para a sentinela e monitor de processos do Windows.
Diretrizes Anti-Gambiarra: Validação determinística de condições lógicas de disparo.
"""
from wintoolbox.tools.automation.process_watcher.logic import (
    ProcessRule,
    evaluate_process_rule,
    load_process_rules_json,
    save_process_rules_json,
)


def test_evaluate_process_rule_on_exit():
    r_exit = ProcessRule("r1", "Exit", "app.exe", "on_exit", 0.0, "notify", "fim", True)
    # Estava rodando e agora parou -> True
    assert evaluate_process_rule(r_exit, is_running=False, was_running=True) is True
    # Continua rodando -> False
    assert evaluate_process_rule(r_exit, is_running=True, was_running=True) is False


def test_evaluate_process_rule_on_start():
    r_start = ProcessRule("r2", "Start", "app.exe", "on_start", 0.0, "notify", "inicio", True)
    # Não estava rodando e começou -> True
    assert evaluate_process_rule(r_start, is_running=True, was_running=False) is True
    # Já estava rodando -> False
    assert evaluate_process_rule(r_start, is_running=True, was_running=True) is False


def test_evaluate_process_rule_thresholds():
    r_mem = ProcessRule("r3", "Mem", "app.exe", "memory_above", 2048.0, "notify", "alerta", True)
    assert evaluate_process_rule(r_mem, is_running=True, was_running=True, current_mem_mb=2500.0) is True
    assert evaluate_process_rule(r_mem, is_running=True, was_running=True, current_mem_mb=1500.0) is False

    r_cpu = ProcessRule("r4", "CPU", "app.exe", "cpu_above", 80.0, "notify", "alerta", True)
    assert evaluate_process_rule(r_cpu, is_running=True, was_running=True, current_cpu_pct=85.0) is True
    assert evaluate_process_rule(r_cpu, is_running=True, was_running=True, current_cpu_pct=50.0) is False


def test_process_rules_json_serialization(tmp_path):
    p = tmp_path / "proc_rules.json"
    rules = [
        ProcessRule("p1", "Regra 1", "blender.exe", "on_exit", 0.0, "notify", "pronto", True)
    ]
    save_process_rules_json(rules, str(p))
    assert p.exists()

    loaded = load_process_rules_json(str(p))
    assert len(loaded) == 1
    assert loaded[0].id == "p1"
    assert loaded[0].process_name == "blender.exe"
