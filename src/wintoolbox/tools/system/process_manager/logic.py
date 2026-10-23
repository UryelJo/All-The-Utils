"""
Lógica pura do Gerenciador de Processos do Windows.
Interage com psutil e win32 sem dependência de interface gráfica.
"""
import ctypes
import os
import time
from typing import Any, Dict, List, Optional
import psutil

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("process_manager")


# --- Snapshot nativo -------------------------------------------------------------
# psutil abre cada processo individualmente (OpenProcess + consultas): ~1,2 s para
# ~280 processos com memória/status/threads. NtQuerySystemInformation devolve nome,
# memória, threads, handles e tempos de CPU de todos os processos numa única chamada
# (é o que o Gerenciador de Tarefas usa): poucos milissegundos.

class _UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort), ("Buffer", ctypes.c_void_p)]


class _SYSTEM_PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("NextEntryOffset", ctypes.c_ulong),
        ("NumberOfThreads", ctypes.c_ulong),
        ("WorkingSetPrivateSize", ctypes.c_longlong),
        ("HardFaultCount", ctypes.c_ulong),
        ("NumberOfThreadsHighWatermark", ctypes.c_ulong),
        ("CycleTime", ctypes.c_ulonglong),
        ("CreateTime", ctypes.c_longlong),
        ("UserTime", ctypes.c_longlong),
        ("KernelTime", ctypes.c_longlong),
        ("ImageName", _UNICODE_STRING),
        ("BasePriority", ctypes.c_long),
        ("UniqueProcessId", ctypes.c_void_p),
        ("InheritedFromUniqueProcessId", ctypes.c_void_p),
        ("HandleCount", ctypes.c_ulong),
        ("SessionId", ctypes.c_ulong),
        ("UniqueProcessKey", ctypes.c_void_p),
        ("PeakVirtualSize", ctypes.c_size_t),
        ("VirtualSize", ctypes.c_size_t),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivatePageCount", ctypes.c_size_t),
    ]


_SYSTEM_PROCESS_INFORMATION_CLASS = 5
_STATUS_INFO_LENGTH_MISMATCH = 0xC0000004


def _native_snapshot() -> List[Dict[str, Any]]:
    """Lista crua de processos via NtQuerySystemInformation (uma chamada para todos)."""
    ntdll = ctypes.windll.ntdll
    size = 512 * 1024
    for _ in range(6):
        buf = ctypes.create_string_buffer(size)
        needed = ctypes.c_ulong(0)
        status = ntdll.NtQuerySystemInformation(_SYSTEM_PROCESS_INFORMATION_CLASS, buf, size, ctypes.byref(needed))
        status &= 0xFFFFFFFF
        if status == _STATUS_INFO_LENGTH_MISMATCH:
            size = max(size * 2, needed.value + 64 * 1024)
            continue
        if status != 0:
            raise OSError(f"NtQuerySystemInformation falhou: 0x{status:08X}")
        break
    else:
        raise OSError("NtQuerySystemInformation: buffer insuficiente")

    base = ctypes.addressof(buf)
    out: List[Dict[str, Any]] = []
    offset = 0
    while True:
        spi = _SYSTEM_PROCESS_INFORMATION.from_address(base + offset)
        pid = spi.UniqueProcessId or 0
        if spi.ImageName.Buffer and spi.ImageName.Length:
            name = ctypes.wstring_at(spi.ImageName.Buffer, spi.ImageName.Length // 2)
        else:
            name = "System Idle Process" if pid == 0 else "System"
        out.append({
            "pid": pid,
            "ppid": spi.InheritedFromUniqueProcessId or 0,
            "name": name,
            "create_time": spi.CreateTime,
            "cpu_time": spi.UserTime + spi.KernelTime,  # unidades de 100 ns
            "memory": spi.WorkingSetSize,
            "private": spi.PrivatePageCount,
            "threads": spi.NumberOfThreads,
            "handles": spi.HandleCount,
        })
        if not spi.NextEntryOffset:
            break
        offset += spi.NextEntryOffset
    return out


def _psutil_snapshot() -> List[Dict[str, Any]]:
    """Fallback (mais lento) caso a API nativa não esteja disponível."""
    out = []
    for proc in psutil.process_iter(["pid", "ppid", "name", "create_time", "cpu_times", "memory_info", "num_threads"]):
        info = proc.info
        cpu = info.get("cpu_times")
        mem = info.get("memory_info")
        out.append({
            "pid": info.get("pid", 0),
            "ppid": info.get("ppid") or 0,
            "name": info.get("name") or "Desconhecido",
            "create_time": int((info.get("create_time") or 0) * 1e7),
            "cpu_time": int(((cpu.user + cpu.system) if cpu else 0) * 1e7),
            "memory": mem.rss if mem else 0,
            "private": getattr(mem, "private", 0) if mem else 0,
            "threads": info.get("num_threads") or 0,
            "handles": 0,
        })
    return out


class ProcessSampler:
    """
    Amostrador de processos: CPU% calculado entre amostras (normalizado pelo total de
    núcleos, como no Gerenciador de Tarefas) e cache de usuário por (pid, criação).
    """

    def __init__(self) -> None:
        self._prev_cpu: Dict[tuple, int] = {}
        self._prev_ts: Optional[float] = None
        self._users: Dict[tuple, str] = {}
        self._cpu_count = psutil.cpu_count(logical=True) or 1
        self._native = True

    def sample(self) -> List[Dict[str, Any]]:
        if self._native:
            try:
                raw = _native_snapshot()
            except Exception:
                _log.warning("Snapshot nativo indisponível; usando psutil (mais lento)", exc_info=True)
                self._native = False
                raw = _psutil_snapshot()
        else:
            raw = _psutil_snapshot()

        now = time.perf_counter()
        elapsed_100ns = (now - self._prev_ts) * 1e7 if self._prev_ts else 0.0
        cur_cpu: Dict[tuple, int] = {}
        result: List[Dict[str, Any]] = []
        for p in raw:
            pid = p["pid"]
            if pid == 0:
                continue  # "Processo Ocioso do Sistema" não é um processo real
            key = (pid, p["create_time"])
            cur_cpu[key] = p["cpu_time"]
            prev = self._prev_cpu.get(key)
            cpu_pct = 0.0
            if prev is not None and elapsed_100ns > 0:
                cpu_pct = max(0.0, (p["cpu_time"] - prev) / (elapsed_100ns * self._cpu_count) * 100.0)
            result.append({
                "pid": pid,
                "ppid": p["ppid"],
                "name": p["name"],
                "cpu_percent": round(min(cpu_pct, 100.0), 1),
                "memory_mb": round(p["memory"] / (1024 * 1024), 1),
                "private_mb": round(p["private"] / (1024 * 1024), 1),
                "threads": p["threads"],
                "handles": p["handles"],
                "username": self._username(key),
            })

        self._prev_cpu = cur_cpu
        self._prev_ts = now
        # Descarta usuários de processos que já terminaram
        self._users = {k: v for k, v in self._users.items() if k in cur_cpu}
        return result

    def _username(self, key: tuple) -> str:
        if key not in self._users:
            try:
                user = psutil.Process(key[0]).username() or ""
                # "DOMINIO\usuario" -> "usuario" (mais legível na tabela)
                self._users[key] = user.rsplit("\\", 1)[-1]
            except Exception:
                self._users[key] = ""
        return self._users[key]


def list_running_processes(filter_text: str = "") -> List[Dict[str, Any]]:
    """
    Retorna uma lista estruturada de processos em execução (usada pelo CLI e testes).
    Suporta filtragem por nome, PID ou usuário.
    """
    filter_norm = filter_text.strip().lower()
    processes = ProcessSampler().sample()
    if filter_norm:
        processes = [p for p in processes if filter_norm in p["name"].lower()
                     or filter_norm in str(p["pid"]) or filter_norm in p["username"].lower()]
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
