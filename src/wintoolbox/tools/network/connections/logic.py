"""
Lógica pura de inspeção de conexões de rede ativas por processo (estilo TCPView).
Totalmente desacoplada de bibliotecas de interface visual.
"""
import socket
from typing import Any, Dict, List, Optional, Tuple
import psutil

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("network.connections")


def list_active_connections() -> List[Dict[str, Any]]:
    """
    Enumera todas as conexões de rede ativas (TCP e UDP)
    associando cada socket ao seu processo correspondente.
    """
    # Mapeia PIDs para nomes de processo para evitar lookups repetitivos
    proc_names: Dict[int, str] = {}
    for p in psutil.process_iter(["pid", "name"]):
        try:
            proc_names[p.info["pid"]] = p.info["name"] or "Sistema"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    connections: List[Dict[str, Any]] = []

    try:
        # psutil.net_connections pode requerer permissões para certos PIDs
        raw_conns = psutil.net_connections(kind="inet")
    except Exception as exc:
        _log.warning("Falha ao ler net_connections: %s", exc)
        return []

    for conn in raw_conns:
        proto = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"

        # Endereço local
        l_ip = conn.laddr.ip if conn.laddr else ""
        l_port = conn.laddr.port if conn.laddr else ""
        l_addr = f"{l_ip}:{l_port}" if l_ip else "-"

        # Endereço remoto
        if conn.raddr:
            r_ip = conn.raddr.ip
            r_port = conn.raddr.port
            r_addr = f"{r_ip}:{r_port}"
        else:
            r_addr = "*:*"

        pid = conn.pid or 0
        pname = proc_names.get(pid, "Sistema / Desconhecido" if pid == 0 else f"PID {pid}")

        connections.append({
            "proto": proto,
            "local_address": l_addr,
            "remote_address": r_addr,
            "status": conn.status or "NONE",
            "pid": pid,
            "process_name": pname
        })

    # Ordena: conexões ativas primeiro, depois pelo nome do processo
    status_priority = {"ESTABLISHED": 0, "SYN_SENT": 1, "LISTENING": 2}
    connections.sort(key=lambda c: (status_priority.get(c["status"], 9), c["process_name"].lower()))
    return connections


def terminate_connection_process(pid: int) -> Tuple[bool, str]:
    """Finaliza o processo associado à conexão especificada."""
    if pid <= 4:
        return False, "Não é permitido finalizar processos críticos do Sistema Operacional."

    try:
        proc = psutil.Process(pid)
        pname = proc.name()
        proc.terminate()
        return True, f"Processo '{pname}' (PID {pid}) finalizado com sucesso."
    except psutil.NoSuchProcess:
        return False, f"O processo com PID {pid} já não está mais em execução."
    except psutil.AccessDenied:
        return False, f"Acesso negado ao finalizar o PID {pid}. Execute como Administrador."
    except Exception as exc:
        return False, f"Falha ao finalizar processo: {exc}"
