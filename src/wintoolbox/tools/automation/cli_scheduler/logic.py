"""
Lógica pura para agendamento de rotinas do WinToolbox via Agendador de Tarefas do Windows (schtasks).
Permite automatizar ferramentas no modo headless (linha de comando).
Desacoplada de frameworks de interface gráfica.
"""
from dataclasses import asdict, dataclass
import json
import os
import subprocess
from typing import Any, Dict, List, Optional


@dataclass
class ScheduledTask:
    """Representa uma tarefa agendada do WinToolbox no Windows."""
    task_name: str
    tool_id: str
    tool_args: str
    frequency: str      # "DAILY", "WEEKLY", "ONSTART", "ONLOGON"
    time_str: str       # "HH:MM"
    enabled: bool = True


def build_schtasks_create_command(
    task_name: str,
    python_exe: str,
    main_script_path: str,
    tool_id: str,
    frequency: str = "DAILY",
    time_str: str = "03:00"
) -> List[str]:
    """
    Constrói a chamada de linha de comando para criar uma tarefa no Agendador do Windows via 'schtasks.exe'.
    """
    cmd_run = f'"{python_exe}" "{main_script_path}" run {tool_id}'
    cmd = [
        "schtasks", "/Create",
        "/TN", f"WinToolbox_{task_name}",
        "/TR", cmd_run,
        "/SC", frequency.upper(),
        "/F"  # Forçar sobrescrita se já existir
    ]
    if frequency.upper() in ["DAILY", "WEEKLY", "HOURLY"]:
        cmd.extend(["/ST", time_str])

    return cmd


def build_schtasks_delete_command(task_name: str) -> List[str]:
    """Constrói comando para deletar a tarefa agendada no Windows."""
    return ["schtasks", "/Delete", "/TN", f"WinToolbox_{task_name}", "/F"]


def save_scheduled_tasks_json(tasks: List[ScheduledTask], filepath: str) -> None:
    """Salva catálogo de tarefas agendadas em JSON."""
    raw = [asdict(t) for t in tasks]
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)


def load_scheduled_tasks_json(filepath: str) -> List[ScheduledTask]:
    """Carrega catálogo de tarefas agendadas em JSON."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
            return [
                ScheduledTask(
                    task_name=d.get("task_name", ""),
                    tool_id=d.get("tool_id", ""),
                    tool_args=d.get("tool_args", ""),
                    frequency=d.get("frequency", "DAILY"),
                    time_str=d.get("time_str", "03:00"),
                    enabled=d.get("enabled", True)
                )
                for d in raw if isinstance(d, dict)
            ]
    except Exception:
        return []
