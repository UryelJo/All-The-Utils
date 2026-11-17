"""
Lógica pura do Gerenciador de Serviços do Windows.
Interage com psutil e sc.exe sem dependência de interface gráfica.
"""
import os
import re
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


def extract_service_exe_path(binpath: str) -> str:
    """Extrai o caminho do executável a partir da linha de comando (binpath) do serviço."""
    s = (binpath or "").strip()
    if not s:
        return ""
    s = os.path.expandvars(s)
    if s.startswith('"'):
        end_q = s.find('"', 1)
        if end_q > 1:
            return s[1:end_q]
    m = re.match(r"^([a-zA-Z]:\\[^\r\n]*?\.(?:exe|sys|dll))\b", s, re.IGNORECASE)
    if m:
        return m.group(1)
    return s.split()[0].strip('"') if s else ""


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
                binpath = info.get("binpath") or ""

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
                    "binpath": binpath,
                    "exe_path": extract_service_exe_path(binpath),
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
            subprocess.run(
                ["net", "stop", service_name, "/y"],
                capture_output=True, text=True, encoding=CONSOLE_ENCODING,
                errors="replace", timeout=20, creationflags=CREATE_NO_WINDOW
            )
            res = subprocess.run(
                ["net", "start", service_name],
                capture_output=True, text=True, encoding=CONSOLE_ENCODING,
                errors="replace", timeout=20, creationflags=CREATE_NO_WINDOW
            )
            if res.returncode == 0:
                return True, f"Serviço '{service_name}' reiniciado com sucesso."
            return False, f"Falha ao iniciar serviço '{service_name}': {res.stderr or res.stdout}"

        elif action in ("start", "stop"):
            cmd = ["net", action, service_name]
            if action == "stop":
                cmd.append("/y")
            res = subprocess.run(
                cmd,
                capture_output=True, text=True, encoding=CONSOLE_ENCODING,
                errors="replace", timeout=25, creationflags=CREATE_NO_WINDOW
            )
            if res.returncode == 0:
                verb = "iniciado" if action == "start" else "interrompido"
                return True, f"Serviço '{service_name}' {verb} com sucesso."
            return False, f"Falha ao alterar '{service_name}': {res.stderr or res.stdout or 'Verifique permissões de administrador.'}"

        else:
            return False, f"Ação desconhecida: {action}"
    except subprocess.TimeoutExpired:
        return False, f"Tempo limite excedido aguardando o serviço '{service_name}'."
    except Exception as e:
        return False, f"Erro inesperado em '{service_name}': {str(e)}"


def change_multiple_services_status(service_names: List[str], action: str) -> Tuple[bool, str]:
    """Executa iniciar, parar ou reiniciar em lote para vários serviços."""
    if not service_names:
        return False, "Nenhum serviço selecionado."
    if len(service_names) == 1:
        return change_service_status(service_names[0], action)

    ok_count = 0
    errors: List[str] = []
    for srv in service_names:
        ok, msg = change_service_status(srv, action)
        if ok:
            ok_count += 1
        else:
            errors.append(msg.strip())

    if ok_count > 0 and not errors:
        return True, f"{ok_count} serviço(s) atualizado(s) com sucesso."
    elif ok_count > 0 and errors:
        return True, f"{ok_count} serviço(s) concluído(s), mas {len(errors)} falharam:\n" + "\n".join(errors[:4])
    else:
        return False, "Falha ao alterar os serviços selecionados:\n" + "\n".join(errors[:4])


def change_service_startup_type(service_name: str, start_type: str) -> Tuple[bool, str]:
    """
    Altera o tipo de inicialização de um serviço via sc.exe.
    start_type: 'auto' | 'manual' | 'demand' | 'disabled'
    """
    valid = {"auto": "auto", "manual": "demand", "demand": "demand", "disabled": "disabled"}
    val = valid.get(start_type.lower())
    if not val:
        return False, f"Tipo de inicialização inválido: {start_type}"

    try:
        cmd = ["sc.exe", "config", service_name, f"start= {val}"]
        res = subprocess.run(
            cmd,
            capture_output=True, text=True, encoding=CONSOLE_ENCODING,
            errors="replace", timeout=10, creationflags=CREATE_NO_WINDOW
        )
        if res.returncode == 0:
            return True, f"Tipo de inicialização do serviço '{service_name}' alterado para '{start_type}'."
        return False, f"Erro ao configurar '{service_name}': {res.stderr or res.stdout}"
    except Exception as e:
        return False, f"Erro ao executar sc.exe: {str(e)}"


def change_multiple_services_startup(service_names: List[str], start_type: str) -> Tuple[bool, str]:
    """Altera o tipo de inicialização em lote para múltiplos serviços."""
    if not service_names:
        return False, "Nenhum serviço selecionado."
    if len(service_names) == 1:
        return change_service_startup_type(service_names[0], start_type)

    ok_count = 0
    errors: List[str] = []
    for srv in service_names:
        ok, msg = change_service_startup_type(srv, start_type)
        if ok:
            ok_count += 1
        else:
            errors.append(msg.strip())

    if ok_count > 0 and not errors:
        return True, f"Tipo de inicialização aplicado com sucesso em {ok_count} serviço(s)."
    elif ok_count > 0 and errors:
        return True, f"{ok_count} serviço(s) atualizado(s), mas {len(errors)} falharam:\n" + "\n".join(errors[:4])
    else:
        return False, "Falha ao alterar tipo de inicialização:\n" + "\n".join(errors[:4])
