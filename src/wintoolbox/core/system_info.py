"""
Coleta de métricas e informações do sistema Windows via psutil e ctypes.
"""
import psutil
from typing import Dict, List

def get_realtime_metrics() -> Dict:
    """Coleta métricas em tempo real de CPU, Memória e Armazenamento."""
    cpu_percent = psutil.cpu_percent(interval=None)
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
            except (PermissionError, OSError):
                continue

    return {
        "cpu_percent": cpu_percent,
        "cpu_count": cpu_count,
        "mem_total_gb": mem_total_gb,
        "mem_used_gb": mem_used_gb,
        "mem_percent": mem_percent,
        "disks": disks
    }
