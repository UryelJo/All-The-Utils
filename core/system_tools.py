import os
import sys
import shutil
import ctypes
import psutil
import subprocess
import threading
from typing import Callable, List, Dict

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def run_as_admin():
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit()

def run_command_async(cmd: str, on_output: Callable[[str], None], on_done: Callable[[int], None]):
    def worker():
        try:
            # CREATE_NO_WINDOW evita abrir a janela preta do cmd
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="cp850", # Codificação padrão do terminal Windows pt-BR
                errors="replace",
                creationflags=creation_flags
            )

            for line in process.stdout:
                on_output(line.rstrip())

            process.wait()
            on_done(process.returncode)
        except Exception as e:
            on_output(f"[ERRO]: {str(e)}")
            on_done(-1)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

def clean_temp_folder(on_log: Callable[[str], None] = None) -> Dict[str, int]:
    """Limpa a pasta temporária do usuário (%TEMP%)."""
    temp_dir = os.environ.get("TEMP", "")
    deleted_files = 0
    deleted_bytes = 0
    errors = 0

    if not temp_dir or not os.path.isdir(temp_dir):
        if on_log:
            on_log("Diretório temporário não localizado.")
        return {"files": 0, "freed_mb": 0, "errors": 0}

    for root, dirs, files in os.walk(temp_dir, topdown=False):
        for name in files:
            file_path = os.path.join(root, name)
            try:
                size = os.path.getsize(file_path)
                os.remove(file_path)
                deleted_files += 1
                deleted_bytes += size
            except Exception:
                errors += 1

        for name in dirs:
            dir_path = os.path.join(root, name)
            try:
                shutil.rmtree(dir_path, ignore_errors=True)
            except Exception:
                pass

    freed_mb = round(deleted_bytes / (1024 * 1024), 2)
    if on_log:
        on_log(f"Limpeza concluída! {deleted_files} arquivos removidos (~{freed_mb} MB liberados). {errors} em uso ignorados.")

    return {"files": deleted_files, "freed_mb": freed_mb, "errors": errors}

def get_system_metrics() -> Dict:
    """Coleta métricas em tempo real de CPU, Memória e Discos."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    cpu_count = psutil.cpu_count(logical=True)
    
    mem = psutil.virtual_memory()
    mem_total_gb = round(mem.total / (1024**3), 1)
    mem_used_gb = round(mem.used / (1024**3), 1)
    mem_percent = mem.percent

    disks = []
    for part in psutil.disk_partitions(all=False):
        if "fixed" in part.opts or part.fstype:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(usage.total / (1024**3), 1),
                    "used_gb": round(usage.used / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "percent": usage.percent
                })
            except PermissionError:
                continue

    return {
        "cpu_percent": cpu_percent,
        "cpu_count": cpu_count,
        "mem_total_gb": mem_total_gb,
        "mem_used_gb": mem_used_gb,
        "mem_percent": mem_percent,
        "disks": disks
    }
