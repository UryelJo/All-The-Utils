"""
Lógica pura da ferramenta Monitor de Hardware e Recursos do Sistema.
Coleta e formata métricas em tempo real de CPU, Memória RAM e Discos sem acoplamento com o Qt.
"""
from dataclasses import dataclass
from typing import Dict, List
import psutil
from wintoolbox.core.system_info import get_realtime_metrics


@dataclass
class DiskMetricItem:
    device: str
    mountpoint: str
    fstype: str
    total_gb: float
    free_gb: float
    percent: float


@dataclass
class SystemMetricsSnapshot:
    cpu_percent: float
    cpu_count: int
    mem_percent: float
    mem_used_gb: float
    mem_total_gb: float
    disks: List[DiskMetricItem]


def collect_hardware_metrics() -> SystemMetricsSnapshot:
    """Coleta e estrutura os dados instantâneos de telemetria de hardware."""
    m = get_realtime_metrics()

    disks_list: List[DiskMetricItem] = []
    for d in m.get("disks", []):
        disks_list.append(
            DiskMetricItem(
                device=d.get("device", ""),
                mountpoint=d.get("mountpoint", ""),
                fstype=d.get("fstype", ""),
                total_gb=float(d.get("total_gb", 0.0)),
                free_gb=float(d.get("free_gb", 0.0)),
                percent=float(d.get("percent", 0.0)),
            )
        )

    return SystemMetricsSnapshot(
        cpu_percent=float(m.get("cpu_percent", 0.0)),
        cpu_count=int(m.get("cpu_count", 1)),
        mem_percent=float(m.get("mem_percent", 0.0)),
        mem_used_gb=float(m.get("mem_used_gb", 0.0)),
        mem_total_gb=float(m.get("mem_total_gb", 0.0)),
        disks=disks_list,
    )
