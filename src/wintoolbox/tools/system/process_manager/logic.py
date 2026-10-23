"""
Lógica pura do Gerenciador de Processos do Windows.
Interage com psutil e win32 sem dependência de interface gráfica.
"""
import os
from typing import Any, Dict, List, Optional
import psutil


def list_running_processes(filter_text: str = "") -> List[Dict[str, Any]]:
    """
    Retorna uma lista estruturada de processos em execução.
    Suporta filtragem por nome, PID ou usuário.
    """
    filter_norm = filter_text.strip().lower()
    processes: List[Dict[str, Any]] = []

    for proc in psutil.process_iter(attrs=["pid", "name", "username", "status"]):
        try:
            info = proc.info
            name = info.get("name") or "Desconhecido"
            pid = info.get("pid", 0)
            username = info.get("username") or ""

            # Filtro rápido
            if filter_norm:
                if filter_norm not in name.lower() and filter_norm not in str(pid) and filter_norm not in username.lower():
                    continue

            # Memória
            try:
                mem_info = proc.memory_info()
                mem_rss_mb = round(mem_info.rss / (1024 * 1024), 1)
            except Exception:
                mem_rss_mb = 0.0

            # CPU Percent (não-bloqueante)
            try:
                cpu_pct = proc.cpu_percent(interval=None)
            except Exception:
                cpu_pct = 0.0

            # Número de Threads
            try:
                num_threads = proc.num_threads()
            except Exception:
                num_threads = 1

            processes.append({
                "pid": pid,
                "name": name,
                "cpu_percent": cpu_pct,
                "memory_mb": mem_rss_mb,
                "username": username,
                "status": str(info.get("status") or "running"),
                "num_threads": num_threads,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Ordena por uso de memória descendente por padrão
    processes.sort(key=lambda p: p["memory_mb"], reverse=True)
    return processes


def terminate_process(pid: int, kill_tree: bool = False) -> Dict[str, Any]:
    """
    Encerra um processo pelo PID. Se kill_tree=True, encerra os processos filhos também.
    """
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return {"success": False, "message": f"Processo com PID {pid} não foi encontrado."}
    except psutil.AccessDenied:
        return {"success": False, "message": f"Acesso negado ao tentar acessar o PID {pid}. Execute como administrador."}

    killed_count = 0
    try:
        if kill_tree:
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                    killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        parent.kill()
        killed_count += 1
        return {
            "success": True,
            "message": f"Processo '{parent.name()}' (PID {pid}) encerrado com sucesso. Total de processos finalizados: {killed_count}.",
            "killed_count": killed_count,
        }
    except psutil.AccessDenied:
        return {"success": False, "message": f"Permissão insuficiente para finalizar o PID {pid}."}
    except Exception as e:
        return {"success": False, "message": f"Erro ao finalizar processo: {str(e)}"}


def get_process_details(pid: int) -> Dict[str, Any]:
    """
    Obtém informações aprofundadas sobre um processo específico.
    """
    try:
        proc = psutil.Process(pid)
        with proc.oneshot():
            exe = proc.exe() if proc.exe() else "Não disponível"
            cmdline = " ".join(proc.cmdline()) if proc.cmdline() else "Não disponível"
            cwd = proc.cwd() if proc.cwd() else "Não disponível"
            create_time = proc.create_time()
            num_threads = proc.num_threads()
            priority = proc.nice()
            mem_info = proc.memory_info()

        return {
            "success": True,
            "pid": pid,
            "name": proc.name(),
            "executable": exe,
            "cmdline": cmdline,
            "cwd": cwd,
            "num_threads": num_threads,
            "priority": str(priority),
            "memory_rss_mb": round(mem_info.rss / (1024 * 1024), 2),
            "create_time": create_time,
        }
    except psutil.NoSuchProcess:
        return {"success": False, "message": f"Processo {pid} já foi finalizado."}
    except psutil.AccessDenied:
        return {"success": False, "message": f"Acesso negado aos detalhes do processo {pid}."}
    except Exception as e:
        return {"success": False, "message": str(e)}
