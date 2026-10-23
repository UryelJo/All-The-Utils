"""
Lógica pura para consulta e gerenciamento de Tarefas Agendadas do Windows (API COM, com schtasks de reserva).
Isolada de interface gráfica.
"""
import csv
import io
import subprocess
from typing import Any, Dict, List, Tuple

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.shell import CONSOLE_ENCODING, CREATE_NO_WINDOW

_log = get_logger("task_scheduler")


STATUS_MAP = {
    "ready": "Pronto",
    "running": "Em execução",
    "disabled": "Desativado",
    "pronto": "Pronto",
    "em execução": "Em execução",
    "desativado": "Desativado",
}


def _list_via_schtasks(hide_microsoft: bool = True, filter_text: str = "") -> List[Dict[str, Any]]:
    """
    Lista as tarefas agendadas do Windows via 'schtasks /query /fo CSV'.
    Permite ocultar tarefas padrão da Microsoft e filtrar por texto.
    """
    tasks: List[Dict[str, Any]] = []
    filter_norm = filter_text.strip().lower()

    try:
        # Executa schtasks formatado como CSV
        res = subprocess.run(["schtasks.exe", "/query", "/fo", "CSV"], capture_output=True, text=True, encoding=CONSOLE_ENCODING, errors="replace", timeout=15, creationflags=CREATE_NO_WINDOW)
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
                    "last_run": "-",
                    "last_result": "-",
                    "status_raw": status_raw,
                    "status": clean_status,
                    "is_microsoft": task_name.startswith("\\Microsoft"),
                })
    except Exception:
        pass

    tasks.sort(key=lambda x: x["name"].lower())
    return tasks


# Estados de IRegisteredTask.State (TASK_STATE)
_COM_STATES = {0: "Desconhecido", 1: "Desativado", 2: "Na fila", 3: "Pronto", 4: "Em execução"}
_TASK_ENUM_HIDDEN = 1


def _com_date(value: Any) -> str:
    """Datas COM do agendador: o pywin32 rotula a hora local como UTC; 1899 = nunca."""
    try:
        if value is None or value.year < 1900:
            return "Nunca"
        return value.replace(tzinfo=None).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "-"


def _com_result(code: Any) -> str:
    try:
        code = int(code) & 0xFFFFFFFF
    except Exception:
        return "-"
    known = {0: "Sucesso (0x0)", 0x41301: "Em execução", 0x41303: "Ainda não executada",
             0x41306: "Interrompida pelo usuário", 0x8004131F: "Instância já em execução"}
    return known.get(code, f"0x{code:X}")


def _list_via_com() -> List[Dict[str, Any]]:
    """
    Lista todas as tarefas pela API COM do Agendador (Schedule.Service): independente do
    idioma do Windows e ~2x mais rápida que 'schtasks /query', com último resultado.
    """
    import pythoncom
    import win32com.client

    def collect() -> List[Dict[str, Any]]:
        # Todos os objetos COM vivem só neste escopo: precisam ser liberados antes do
        # CoUninitialize, senão o pywin32 acusa "Win32 exception releasing IUnknown"
        service = win32com.client.Dispatch("Schedule.Service")
        service.Connect()
        tasks: List[Dict[str, Any]] = []

        def walk(folder) -> None:
            for t in folder.GetTasks(_TASK_ENUM_HIDDEN):
                full = str(t.Path)
                parts = full.rsplit("\\", 1)
                state = int(t.State)
                tasks.append({
                    "full_name": full,
                    "name": parts[-1],
                    "folder": parts[0] or "\\",
                    "next_run": _com_date(t.NextRunTime) if t.Enabled else "-",
                    "last_run": _com_date(t.LastRunTime),
                    "last_result": _com_result(t.LastTaskResult),
                    "status_raw": str(state),
                    "status": _COM_STATES.get(state, str(state)),
                    "is_microsoft": full.startswith("\\Microsoft"),
                })
            for sub in folder.GetFolders(0):
                walk(sub)

        walk(service.GetFolder("\\"))
        return tasks

    pythoncom.CoInitialize()
    try:
        return collect()
    finally:
        pythoncom.CoUninitialize()


def list_all_scheduled_tasks() -> List[Dict[str, Any]]:
    """Todas as tarefas (inclusive Microsoft); filtros ficam a cargo da interface."""
    try:
        tasks = _list_via_com()
    except Exception:
        _log.warning("API COM do Agendador indisponível; usando schtasks", exc_info=True)
        # schtasks repete a tarefa em uma linha por gatilho
        tasks = list({t["full_name"]: t for t in _list_via_schtasks(hide_microsoft=False)}.values())
    tasks.sort(key=lambda x: x["name"].lower())
    return tasks


def list_scheduled_tasks(hide_microsoft: bool = True, filter_text: str = "") -> List[Dict[str, Any]]:
    """
    Lista as tarefas agendadas do Windows.
    Permite ocultar tarefas padrão da Microsoft e filtrar por texto.
    """
    filter_norm = filter_text.strip().lower()
    return [
        t for t in list_all_scheduled_tasks()
        if not (hide_microsoft and t["is_microsoft"]) and (not filter_norm or filter_norm in t["full_name"].lower())
    ]



def run_scheduled_task(task_full_name: str) -> Tuple[bool, str]:
    """
    Dispara a execução imediata de uma tarefa agendada via 'schtasks /run /tn ...'.
    """
    task_name = task_full_name.strip()
    if not task_name:
        return False, "Nome da tarefa inválido."

    try:
        res = subprocess.run(["schtasks.exe", "/run", "/tn", task_name], capture_output=True, text=True, encoding=CONSOLE_ENCODING, errors="replace", timeout=10, creationflags=CREATE_NO_WINDOW)
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
        res = subprocess.run(["schtasks.exe", "/change", "/tn", task_name, action], capture_output=True, text=True, encoding=CONSOLE_ENCODING, errors="replace", timeout=10, creationflags=CREATE_NO_WINDOW)
        if res.returncode == 0:
            verb = "ativada" if enable else "desativada"
            return True, f"Tarefa '{task_name}' {verb} com sucesso."
        return False, f"Falha ao alterar estado da tarefa: {res.stderr or res.stdout}"
    except Exception as e:
        return False, f"Erro ao executar schtasks: {str(e)}"
