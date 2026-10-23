"""
Lógica pura do Gerenciador de Serviços do Windows.
Interage com psutil e sc.exe sem dependência de interface gráfica.
"""
import subprocess
from typing import Any, Dict, List, Tuple
import psutil

from wintoolbox.core.shell import CONSOLE_ENCODING, CREATE_NO_WINDOW


STATUS_TRANSLATIONS = {
    "running": "Em execução",
    "stopped": "Parado",
    "start_pending": "Iniciando",
    "stop_pending": "Parando",
    "paused": "Pausado",
}

START_TYPE_TRANSLATIONS = {
    "automatic": "Automático",
    "manual": "Manual",
    "disabled": "Desativado",
    "boot": "Inicialização (Boot)",
    "system": "Sistema",
}


def list_windows_services(filter_text: str = "", status_filter: str = "all") -> List[Dict[str, Any]]:
    """
    Lista todos os serviços registrados no Windows.
    Permite filtrar por texto (nome ou display_name) e por status ('all', 'running', 'stopped').
    """
    filter_norm = filter_text.strip().lower()
    services: List[Dict[str, Any]] = []

    try:
        for s in psutil.win_service_iter():
            try:
                info = s.as_dict()
                name = info.get("name") or ""
                display_name = info.get("display_name") or name
                raw_status = str(info.get("status") or "stopped")
                raw_start_type = str(info.get("start_type") or "manual")
                pid = info.get("pid") or 0

                # Filtro de status
                if status_filter == "running" and raw_status != "running":
                    continue
                if status_filter == "stopped" and raw_status != "stopped":
                    continue

                # Filtro de texto
                if filter_norm:
                    if filter_norm not in name.lower() and filter_norm not in display_name.lower():
                        continue

                services.append({
                    "name": name,
                    "display_name": display_name,
                    "status_raw": raw_status,
                    "status": STATUS_TRANSLATIONS.get(raw_status, raw_status.capitalize()),
                    "start_type_raw": raw_start_type,
                    "start_type": START_TYPE_TRANSLATIONS.get(raw_start_type, raw_start_type.capitalize()),
                    "pid": pid,
                    "binpath": info.get("binpath") or "",
                    "description": info.get("description") or "",
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass

    services.sort(key=lambda x: x["display_name"].lower())
    return services


def change_service_status(service_name: str, action: str) -> Tuple[bool, str]:
    """
    Inicia, para ou reinicia um serviço do Windows via comando nativo sc.exe / net.exe.
    action: 'start' | 'stop' | 'restart'
    """
    service_name = service_name.strip()
    if not service_name:
        return False, "Nome de serviço inválido."

    try:
        if action == "restart":
            # Para e inicia
            subprocess.run(["net", "stop", service_name, "/y"], capture_output=True, text=True, encoding=CONSOLE_ENCODING, errors="replace", timeout=20, creationflags=CREATE_NO_WINDOW)
            res = subprocess.run(["net", "start", service_name], capture_output=True, text=True, encoding=CONSOLE_ENCODING, errors="replace", timeout=20, creationflags=CREATE_NO_WINDOW)
            if res.returncode == 0:
                return True, f"Serviço '{service_name}' reiniciado com sucesso."
            return False, f"Falha ao iniciar serviço: {res.stderr or res.stdout}"

        elif action in ("start", "stop"):
            cmd = ["net", action, service_name]
            if action == "stop":
                cmd.append("/y")
            res = subprocess.run(cmd, capture_output=True, text=True, encoding=CONSOLE_ENCODING, errors="replace", timeout=25, creationflags=CREATE_NO_WINDOW)
            if res.returncode == 0:
                verb = "iniciado" if action == "start" else "interrompido"
                return True, f"Serviço '{service_name}' {verb} com sucesso."
            return False, f"Falha ao alterar serviço: {res.stderr or res.stdout or 'Verifique permissões de administrador.'}"

        else:
            return False, f"Ação desconhecida: {action}"
    except subprocess.TimeoutExpired:
        return False, "Tempo limite excedido aguardando a resposta do serviço."
    except Exception as e:
        return False, f"Erro inesperado: {str(e)}"


def change_service_startup_type(service_name: str, start_type: str) -> Tuple[bool, str]:
    """
    Altera o tipo de inicialização de um serviço via sc.exe.
    start_type: 'auto' | 'demand' | 'disabled'
    """
    valid = {"auto": "auto", "manual": "demand", "demand": "demand", "disabled": "disabled"}
    val = valid.get(start_type.lower())
    if not val:
        return False, f"Tipo de inicialização inválido: {start_type}"

    try:
        # sc config requer espaço após 'start='
        cmd = ["sc.exe", "config", service_name, f"start= {val}"]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding=CONSOLE_ENCODING, errors="replace", timeout=10, creationflags=CREATE_NO_WINDOW)
        if res.returncode == 0:
            return True, f"Tipo de inicialização do serviço '{service_name}' alterado para '{start_type}'."
        return False, f"Erro ao configurar: {res.stderr or res.stdout}"
    except Exception as e:
        return False, f"Erro ao executar sc.exe: {str(e)}"
