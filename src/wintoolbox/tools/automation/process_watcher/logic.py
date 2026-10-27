"""
Lógica pura para sentinela e monitoramento de processos do Windows.
Monitora inicialização, encerramento e consumo de recursos (CPU e Memória) de executáveis.
Desacoplada de frameworks de interface gráfica.
"""
from dataclasses import asdict, dataclass
import json
import os
import subprocess
from typing import Any, Dict, List, Optional


@dataclass
class ProcessRule:
    """Regra de monitoramento de um processo específico."""
    id: str
    name: str
    process_name: str          # Ex: "blender.exe", "render.exe", "chrome.exe"
    trigger_condition: str     # "on_exit", "on_start", "cpu_above", "memory_above"
    threshold_value: float     # Ex: 80.0 (% de CPU) ou 2048.0 (MB de RAM)
    action_type: str           # "notify", "kill", "run_script"
    target_action: str         # Caminho do script ou som
    enabled: bool = True


def get_running_processes_list() -> List[Dict[str, Any]]:
    """
    Lista processos em execução usando 'tasklist /FO CSV /NH'.
    Gera lista limpa de dicionários contendo nome, PID e consumo aproximado de memória.
    """
    procs = []
    try:
        res = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=5
        )
        for line in res.stdout.splitlines():
            parts = [p.strip().strip('"') for p in line.split('","')]
            if len(parts) >= 5:
                name = parts[0]
                pid = parts[1]
                mem_str = parts[4].replace(".", "").replace(" K", "").replace(",", "")
                try:
                    mem_mb = round(float(mem_str) / 1024.0, 1)
                except ValueError:
                    mem_mb = 0.0
                procs.append({
                    "name": name,
                    "pid": pid,
                    "memory_mb": mem_mb
                })
    except Exception:
        pass
    return procs


def evaluate_process_rule(
    rule: ProcessRule,
    is_running: bool,
    was_running: bool,
    current_cpu_pct: float = 0.0,
    current_mem_mb: float = 0.0
) -> bool:
    """
    Avalia se uma regra de processo foi disparada com base no histórico de execução e recursos.
    """
    if not rule.enabled:
        return False

    cond = rule.trigger_condition

    if cond == "on_exit":
        # Estava rodando e agora não está mais
        return was_running and not is_running

    if cond == "on_start":
        # Não estava rodando e agora começou
        return not was_running and is_running

    if cond == "cpu_above" and is_running:
        return current_cpu_pct >= rule.threshold_value

    if cond == "memory_above" and is_running:
        return current_mem_mb >= rule.threshold_value

    return False


def save_process_rules_json(rules: List[ProcessRule], filepath: str) -> None:
    """Salva lista de regras de sentinela em JSON."""
    raw = [asdict(r) for r in rules]
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)


def load_process_rules_json(filepath: str) -> List[ProcessRule]:
    """Carrega regras de sentinela a partir de arquivo JSON."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
            return [
                ProcessRule(
                    id=d.get("id", ""),
                    name=d.get("name", "Sentinela de Processo"),
                    process_name=d.get("process_name", ""),
                    trigger_condition=d.get("trigger_condition", "on_exit"),
                    threshold_value=float(d.get("threshold_value", 0.0)),
                    action_type=d.get("action_type", "notify"),
                    target_action=d.get("target_action", ""),
                    enabled=d.get("enabled", True)
                )
                for d in raw if isinstance(d, dict)
            ]
    except Exception:
        return []
