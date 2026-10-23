"""
Lógica pura da ferramenta Informações de IP e Monitor de Rede em Tempo Real.
Desacoplada de componentes do Qt.
"""
from dataclasses import dataclass
import json
import socket
from typing import Dict, List, Tuple
import urllib.request
import psutil


@dataclass
class NetworkInterfaceInfo:
    name: str
    status: str
    ipv4: str
    ipv6: str
    mac: str

    def __getitem__(self, item: str):
        return getattr(self, item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item)


@dataclass
class TrafficRateInfo:
    down_str: str
    up_str: str
    down_kb: float
    up_kb: float


def get_local_interfaces() -> List[NetworkInterfaceInfo]:
    """Coleta adaptadores de rede, endereços IP e MAC locais."""
    interfaces: List[NetworkInterfaceInfo] = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for iface_name, addr_list in addrs.items():
        is_up = stats[iface_name].isup if iface_name in stats else False
        ipv4 = "-"
        ipv6 = "-"
        mac = "-"
        for addr in addr_list:
            if addr.family == socket.AF_INET:
                ipv4 = addr.address
            elif addr.family == socket.AF_INET6:
                ipv6 = addr.address.split("%")[0]
            elif addr.family == psutil.AF_LINK:
                mac = addr.address

        if ipv4 != "-" or mac != "-":
            interfaces.append(
                NetworkInterfaceInfo(
                    name=iface_name,
                    status="Conectado" if is_up else "Desconectado",
                    ipv4=ipv4,
                    ipv6=ipv6,
                    mac=mac.upper(),
                )
            )
    return interfaces


def fetch_public_ip() -> Dict[str, str]:
    """Consulta o endereço IP público e detalhes básicos de rede externa."""
    urls = [
        "https://api.ipify.org?format=json",
        "https://ifconfig.me/all.json",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "WinToolbox"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ip = data.get("ip") or data.get("ip_addr", "Desconhecido")
                return {"ip": ip, "origem": url}
        except Exception:
            continue
    return {"ip": "Indisponível (Sem conexão externa)", "origem": ""}


def calculate_traffic_rate(
    prev_counters,
    curr_counters,
    elapsed_seconds: float,
) -> TrafficRateInfo:
    """Calcula taxa de transferência (Download/Upload) em KB/s e formatação textual."""
    if elapsed_seconds <= 0:
        return TrafficRateInfo(down_str="0.0 KB/s", up_str="0.0 KB/s", down_kb=0.0, up_kb=0.0)

    bytes_recv = curr_counters.bytes_recv - prev_counters.bytes_recv
    bytes_sent = curr_counters.bytes_sent - prev_counters.bytes_sent

    down_kb = (bytes_recv / elapsed_seconds) / 1024
    up_kb = (bytes_sent / elapsed_seconds) / 1024

    down_str = f"{down_kb / 1024:.2f} MB/s" if down_kb >= 1024 else f"{down_kb:.1f} KB/s"
    up_str = f"{up_kb / 1024:.2f} MB/s" if up_kb >= 1024 else f"{up_kb:.1f} KB/s"

    return TrafficRateInfo(
        down_str=down_str,
        up_str=up_str,
        down_kb=down_kb,
        up_kb=up_kb,
    )
