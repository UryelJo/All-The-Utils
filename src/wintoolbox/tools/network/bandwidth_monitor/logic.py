"""
Lógica pura para monitoramento de largura de banda e tráfego de rede em tempo real.

Calcula taxas instantâneas de download/upload e volume de dados acumulado
utilizando contadores de rede de baixo nível (psutil).
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from dataclasses import asdict, dataclass
import time
from typing import Any, Dict, List, Optional, Tuple
import psutil

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("network.bandwidth_monitor.logic")


@dataclass
class NetworkSnapshot:
    bytes_recv: int
    bytes_sent: int
    timestamp: float


@dataclass
class BandwidthRate:
    download_bytes_per_sec: float
    upload_bytes_per_sec: float
    delta_seconds: float

    @property
    def download_display(self) -> str:
        return format_bandwidth_speed(self.download_bytes_per_sec)

    @property
    def upload_display(self) -> str:
        return format_bandwidth_speed(self.upload_bytes_per_sec)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "download_bps": self.download_bytes_per_sec,
            "upload_bps": self.upload_bytes_per_sec,
            "download_display": self.download_display,
            "upload_display": self.upload_display,
            "delta_seconds": self.delta_seconds,
        }


def format_bandwidth_speed(bytes_per_sec: float) -> str:
    """Formata velocidade de transferência por segundo (B/s, KB/s, MB/s, GB/s)."""
    if bytes_per_sec < 0:
        return "0.0 B/s"
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.1f} B/s"
    elif bytes_per_sec < (1024 * 1024):
        return f"{bytes_per_sec / 1024.0:.1f} KB/s"
    elif bytes_per_sec < (1024 * 1024 * 1024):
        return f"{bytes_per_sec / (1024.0 ** 2):.2f} MB/s"
    else:
        return f"{bytes_per_sec / (1024.0 ** 3):.2f} GB/s"


def format_total_bytes(total_bytes: int) -> str:
    """Formata volume total acumulado em KB, MB ou GB."""
    if total_bytes < 1024:
        return f"{total_bytes} B"
    elif total_bytes < (1024 * 1024):
        return f"{total_bytes / 1024.0:.1f} KB"
    elif total_bytes < (1024 * 1024 * 1024):
        return f"{total_bytes / (1024.0 ** 2):.2f} MB"
    else:
        return f"{total_bytes / (1024.0 ** 3):.2f} GB"


def calculate_bandwidth_rate(prev: NetworkSnapshot, curr: NetworkSnapshot) -> BandwidthRate:
    """
    Calcula a velocidade de transferência entre dois instantes no tempo.
    """
    delta_t = curr.timestamp - prev.timestamp
    if delta_t <= 0.0:
        return BandwidthRate(0.0, 0.0, 0.0)

    delta_recv = max(0, curr.bytes_recv - prev.bytes_recv)
    delta_sent = max(0, curr.bytes_sent - prev.bytes_sent)

    down_bps = delta_recv / delta_t
    up_bps = delta_sent / delta_t

    return BandwidthRate(
        download_bytes_per_sec=down_bps,
        upload_bytes_per_sec=up_bps,
        delta_seconds=delta_t
    )


def get_available_interfaces() -> List[str]:
    """Retorna a lista de nomes de interfaces de rede físicas e virtuais ativas."""
    try:
        counters = psutil.net_io_counters(pernic=True)
        return sorted(list(counters.keys()))
    except Exception as e:
        _log.warning(f"Erro ao listar interfaces de rede: {e}")
        return []


def take_network_snapshot(interface: Optional[str] = None) -> NetworkSnapshot:
    """
    Captura o total de bytes recebidos e transmitidos no momento.
    Se interface for None ou 'Todas', retorna o total somado do sistema.
    """
    now = time.time()
    try:
        if interface and interface != "Todas":
            pernic = psutil.net_io_counters(pernic=True)
            if interface in pernic:
                c = pernic[interface]
                return NetworkSnapshot(c.bytes_recv, c.bytes_sent, now)

        total = psutil.net_io_counters()
        return NetworkSnapshot(total.bytes_recv, total.bytes_sent, now)
    except Exception as e:
        _log.warning(f"Erro ao ler contadores de rede: {e}")
        return NetworkSnapshot(0, 0, now)
