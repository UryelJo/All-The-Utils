"""
Lógica pura da ferramenta Scanner de Rede (Portas e Dispositivos Locais ARP).
Varredura de portas TCP e leitura de tabela ARP sem acoplamento ao Qt.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import socket
import subprocess
from typing import Callable, Dict, List, Optional

COMMON_PORTS: Dict[int, str] = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP",
    110: "POP3", 135: "RPC", 139: "NetBIOS", 143: "IMAP", 443: "HTTPS",
    445: "SMB", 993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1521: "Oracle",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC", 8080: "HTTP-Proxy",
}


@dataclass
class OpenPortItem:
    port: int
    service: str
    status: str = "Aberta"


@dataclass
class ArpDeviceItem:
    ip: str
    mac: str
    tipo: str
    hostname: str


def scan_single_port(host: str, port: int, timeout: float = 0.5) -> Optional[OpenPortItem]:
    """Testa se uma porta TCP está aberta."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        res = s.connect_ex((host, port))
        s.close()
        if res == 0:
            service = COMMON_PORTS.get(port, "Desconhecido")
            return OpenPortItem(port=port, service=service, status="Aberta")
    except Exception:
        pass
    return None


def scan_ports_concurrent(
    host: str,
    ports: List[int],
    max_workers: int = 30,
    is_cancelled_fn: Optional[Callable[[], bool]] = None,
) -> List[OpenPortItem]:
    """Executa varredura concorrente de portas TCP."""
    open_ports: List[OpenPortItem] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_single_port, host, p): p for p in ports}
        for f in as_completed(futures):
            if is_cancelled_fn and is_cancelled_fn():
                break
            res = f.result()
            if res:
                open_ports.append(res)
    open_ports.sort(key=lambda x: x.port)
    return open_ports


def scan_arp_table() -> List[ArpDeviceItem]:
    """Lê a tabela ARP do Windows para listar dispositivos ativos na rede local."""
    devices: List[ArpDeviceItem] = []
    try:
        out = subprocess.check_output("arp -a", shell=True, text=True, errors="replace")
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 3 and parts[0].count(".") == 3:
                ip = parts[0]
                mac = parts[1].replace("-", ":").upper()
                tipo = parts[2]
                if mac != "FF:FF:FF:FF:FF:FF" and not ip.startswith("224.") and not ip.startswith("239."):
                    hostname = "-"
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                    except Exception:
                        pass
                    devices.append(
                        ArpDeviceItem(
                            ip=ip,
                            mac=mac,
                            tipo=tipo,
                            hostname=hostname,
                        )
                    )
    except Exception:
        pass
    return devices
