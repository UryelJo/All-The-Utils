"""
Lógica pura da ferramenta Quem Está Usando Este Arquivo?
Utiliza a API nativa do Windows Restart Manager (rstrtmgr.dll) e psutil sem acoplamento a UI.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
from typing import Dict, List
import psutil


class RM_UNIQUE_PROCESS(ctypes.Structure):
    _fields_ = [
        ("dwProcessId", wintypes.DWORD),
        ("ProcessStartTime", wintypes.FILETIME),
    ]


class RM_PROCESS_INFO(ctypes.Structure):
    _fields_ = [
        ("Process", RM_UNIQUE_PROCESS),
        ("strAppName", wintypes.WCHAR * 256),
        ("strServiceShortName", wintypes.WCHAR * 64),
        ("ApplicationType", wintypes.DWORD),
        ("AppStatus", wintypes.ULONG),
        ("TSSessionId", wintypes.DWORD),
        ("bRestartable", wintypes.BOOL),
    ]


def find_locking_processes(target_path: str) -> List[Dict[str, str]]:
    """Descobre os processos que travam o arquivo utilizando a API nativa Restart Manager do Windows."""
    results: List[Dict[str, str]] = []

    try:
        rm = ctypes.WinDLL("rstrtmgr.dll")
        session_handle = wintypes.DWORD()
        session_key = (wintypes.WCHAR * 33)()

        res = rm.RmStartSession(ctypes.byref(session_handle), 0, session_key)
        if res == 0:
            try:
                path_arr = (wintypes.LPCWSTR * 1)(target_path)
                res = rm.RmRegisterResources(session_handle, 1, path_arr, 0, None, 0, None)
                if res == 0:
                    n_needed = wintypes.UINT(0)
                    n_proc = wintypes.UINT(0)
                    reboot_reasons = wintypes.DWORD()

                    res = rm.RmGetList(
                        session_handle,
                        ctypes.byref(n_needed),
                        ctypes.byref(n_proc),
                        None,
                        ctypes.byref(reboot_reasons),
                    )
                    if res == 234 and n_needed.value > 0:  # ERROR_MORE_DATA
                        proc_info_arr = (RM_PROCESS_INFO * n_needed.value)()
                        n_proc.value = n_needed.value
                        res = rm.RmGetList(
                            session_handle,
                            ctypes.byref(n_needed),
                            ctypes.byref(n_proc),
                            proc_info_arr,
                            ctypes.byref(reboot_reasons),
                        )
                        if res == 0:
                            for i in range(n_proc.value):
                                item = proc_info_arr[i]
                                pid = item.Process.dwProcessId
                                proc_name = item.strAppName
                                if not proc_name:
                                    try:
                                        proc_name = psutil.Process(pid).name()
                                    except Exception:
                                        proc_name = "Desconhecido"
                                results.append({
                                    "pid": str(pid),
                                    "name": proc_name,
                                    "service": item.strServiceShortName or "-",
                                })
            finally:
                rm.RmEndSession(session_handle)
    except Exception:
        pass

    # Fallback complementar caso a API não retorne e o arquivo seja local
    if not results and os.path.exists(target_path) and os.path.isfile(target_path):
        target_norm = os.path.normcase(os.path.abspath(target_path))
        try:
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    for of in p.open_files():
                        if os.path.normcase(os.path.abspath(of.path)) == target_norm:
                            results.append({
                                "pid": str(p.info["pid"]),
                                "name": p.info["name"] or "Processo",
                                "service": "-",
                            })
                            break
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    continue
        except Exception:
            pass

    return results


def terminate_process(pid: int) -> None:
    """Encerra um processo em execução dado seu PID."""
    proc = psutil.Process(pid)
    proc.terminate()
