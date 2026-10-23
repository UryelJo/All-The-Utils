"""
Lógica pura para consulta e gerenciamento de Tarefas Agendadas do Windows via schtasks.
Isolada de interface gráfica.
"""
import csv
import io
import subprocess
from typing import Any, Dict, List, Tuple


STATUS_MAP = {
    "ready": "Pronto",
    "running": "Em execução",
    "disabled": "Desativado",
    "pronto": "Pronto",
    "em execução": "Em execução",
    "desativado": "Desativado",
}


def list_scheduled_tasks(hide_microsoft: bool = True, filter_text: str = "") -> List[Dict[str, Any]]:
    """
    Lista as tarefas agendadas do Windows via 'schtasks /query /fo CSV'.
    Permite ocultar tarefas padrão da Microsoft e filtrar por texto.
    """
    tasks: List[Dict[str, Any]] = []
    filter_norm = filter_text.strip().lower()

    try:
        # Executa schtasks formatado como CSV
        res = subprocess.run(["schtasks.exe", "/query", "/fo", "CSV"], capture_output=True, text=True, timeout=15)
        if res.returncode == 0 and res.stdout:
            # Parseia CSV
            f = io.StringIO(res.stdout)
            reader = csv.reader(f)
            header = None

            for row in reader:
                if not row:
                    continue
                if header is None:
                    header = [h.strip().lower() for h in row]
                    continue

                if len(row) < 3:
                    continue

                task_name = row[0].strip()
                next_run = row[1].strip() if len(row) > 1 else "-"
                status_raw = row[2].strip() if len(row) > 2 else "Desconhecido"

                # Ignora cabeçalhos repetidos caso apareçam
                if "nome da tarefa" in task_name.lower() or "taskname" in task_name.lower():
                    continue

                # Filtro Microsoft
                if hide_microsoft and (task_name.startswith("\\Microsoft") or "\\Microsoft\\" in task_name):
                    continue

                # Filtro de texto
                if filter_norm and filter_norm not in task_name.lower():
                    continue

                clean_status = STATUS_MAP.get(status_raw.lower(), status_raw)

                # Separa pasta e nome da tarefa
                parts = task_name.rsplit("\\", 1)
                display_name = parts[-1] if len(parts) > 1 else task_name
                folder_path = parts[0] if len(parts) > 1 else "\\"

                tasks.append({
                    "full_name": task_name,
                    "name": display_name,
                    "folder": folder_path,
                    "next_run": next_run,
                    "status_raw": status_raw,
                    "status": clean_status,
                })
    except Exception:
        pass

    tasks.sort(key=lambda x: x["name"].lower())
    return tasks


def run_scheduled_task(task_full_name: str) -> Tuple[bool, str]:
    """
    Dispara a execução imediata de uma tarefa agendada via 'schtasks /run /tn ...'.
    """
    task_name = task_full_name.strip()
    if not task_name:
        return False, "Nome da tarefa inválido."

    try:
        res = subprocess.run(["schtasks.exe", "/run", "/tn", task_name], capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            return True, f"Tarefa '{task_name}' iniciada com sucesso."
        return False, f"Falha ao executar tarefa: {res.stderr or res.stdout}"
    except Exception as e:
        return False, f"Erro ao executar schtasks: {str(e)}"


def toggle_scheduled_task(task_full_name: str, enable: bool) -> Tuple[bool, str]:
    """
    Ativa ou desativa uma tarefa agendada via 'schtasks /change /tn ... /enable|disable'.
    """
    task_name = task_full_name.strip()
    if not task_name:
        return False, "Nome da tarefa inválido."

    action = "/enable" if enable else "/disable"
    try:
        res = subprocess.run(["schtasks.exe", "/change", "/tn", task_name, action], capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            verb = "ativada" if enable else "desativada"
            return True, f"Tarefa '{task_name}' {verb} com sucesso."
        return False, f"Falha ao alterar estado da tarefa: {res.stderr or res.stdout}"
    except Exception as e:
        return False, f"Erro ao executar schtasks: {str(e)}"
