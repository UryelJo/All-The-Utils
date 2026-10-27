"""
Lógica pura para benchmark comparativo de desempenho e latência de servidores DNS.

Constrói pacotes de consulta DNS RFC 1035 puros via UDP na porta 53,
medindo a latência real de resposta para múltiplos provedores (Cloudflare, Google,
Quad9, OpenDNS, AdGuard).
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from dataclasses import asdict, dataclass
import random
import socket
import struct
import time
from typing import Any, Dict, List, Optional

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("network.dns_benchmark.logic")

DEFAULT_DNS_SERVERS = [
    {"name": "Cloudflare", "ip": "1.1.1.1"},
    {"name": "Cloudflare Secundário", "ip": "1.0.0.1"},
    {"name": "Google Public DNS", "ip": "8.8.8.8"},
    {"name": "Google Secundário", "ip": "8.8.4.4"},
    {"name": "Quad9 (Segurança)", "ip": "9.9.9.9"},
    {"name": "OpenDNS (Cisco)", "ip": "208.67.222.222"},
    {"name": "AdGuard DNS", "ip": "94.140.14.14"},
]

BENCHMARK_DOMAINS = [
    "google.com",
    "microsoft.com",
    "cloudflare.com",
    "wikipedia.org",
]


@dataclass
class DnsBenchmarkResult:
    rank: int
    name: str
    ip: str
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    success_rate_percent: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_dns_query_packet(domain: str, query_id: Optional[int] = None) -> bytes:
    """
    Constrói um pacote de requisição DNS RFC 1035 tipo A (IPv4) com flag de recursão desejada.
    """
    qid = query_id if query_id is not None else random.randint(0, 65535)
    # Header: ID, Flags (0x0100 = Standard query, Recursion Desired), QDCOUNT=1, ANCOUNT=0, NSCOUNT=0, ARCOUNT=0
    header = struct.pack("!HHHHHH", qid, 0x0100, 1, 0, 0, 0)

    # Question QNAME: labels separadas por comprimento (ex: 6google3com0)
    qname = b""
    for part in domain.strip(".").split("."):
        encoded_part = part.encode("ascii")
        qname += bytes([len(encoded_part)]) + encoded_part
    qname += b"\x00"

    # QTYPE=1 (A), QCLASS=1 (IN)
    footer = struct.pack("!HH", 1, 1)
    return header + qname + footer


def measure_single_dns_query(
    server_ip: str,
    domain: str,
    timeout_sec: float = 2.0,
    port: int = 53
) -> Optional[float]:
    """
    Envia uma consulta DNS UDP para o servidor e retorna o tempo de resposta em milissegundos.
    """
    packet = build_dns_query_packet(domain)
    start_time = time.perf_counter()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout_sec)
            s.sendto(packet, (server_ip, port))
            resp, _ = s.recvfrom(512)
            if resp and len(resp) >= 12:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return round(elapsed_ms, 2)
    except Exception:
        pass

    return None


def benchmark_dns_server(
    server_info: Dict[str, str],
    domains: Optional[List[str]] = None,
    timeout_sec: float = 1.5
) -> Dict[str, Any]:
    """
    Mede a latência média de um servidor DNS testando múltiplos domínios populares.
    """
    test_domains = domains or BENCHMARK_DOMAINS
    latencies: List[float] = []

    for dom in test_domains:
        val = measure_single_dns_query(server_info["ip"], dom, timeout_sec=timeout_sec)
        if val is not None:
            latencies.append(val)

    success_count = len(latencies)
    total_count = len(test_domains)
    success_rate = round((success_count / total_count) * 100.0, 1)

    if latencies:
        avg_ms = round(sum(latencies) / len(latencies), 1)
        min_ms = round(min(latencies), 1)
        max_ms = round(max(latencies), 1)
    else:
        avg_ms = 9999.0
        min_ms = 9999.0
        max_ms = 9999.0

    return {
        "name": server_info["name"],
        "ip": server_info["ip"],
        "avg_latency_ms": avg_ms,
        "min_latency_ms": min_ms,
        "max_latency_ms": max_ms,
        "success_rate_percent": success_rate,
    }


def run_full_dns_benchmark(
    servers: Optional[List[Dict[str, str]]] = None,
    domains: Optional[List[str]] = None
) -> List[DnsBenchmarkResult]:
    """
    Executa o benchmark completo de todos os servidores e retorna a lista classificada pelo menor tempo.
    """
    target_servers = servers or DEFAULT_DNS_SERVERS
    raw_results = [benchmark_dns_server(srv, domains=domains) for srv in target_servers]

    # Ordena por menor latência média
    sorted_results = sorted(raw_results, key=lambda r: (r["avg_latency_ms"], -r["success_rate_percent"]))

    final_results: List[DnsBenchmarkResult] = []
    for idx, r in enumerate(sorted_results, 1):
        final_results.append(DnsBenchmarkResult(
            rank=idx,
            name=r["name"],
            ip=r["ip"],
            avg_latency_ms=r["avg_latency_ms"],
            min_latency_ms=r["min_latency_ms"],
            max_latency_ms=r["max_latency_ms"],
            success_rate_percent=r["success_rate_percent"]
        ))

    return final_results
