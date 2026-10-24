"""
Lógica pura de medição contínua de latência, cálculo de jitter e perda de pacotes.
Totalmente desacoplada de bibliotecas de interface visual.
"""
import re
import subprocess
import time
from typing import List, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("network.latency_monitor")


def ping_host(host: str, timeout_ms: int = 1000) -> Tuple[bool, float]:
    """
    Executa um único pacote de ping ICMP para o host informado.
    Retorna (sucesso, tempo_ms).
    """
    clean_host = host.strip()
    if not clean_host:
        return False, 0.0

    cmd = ["ping", "-n", "1", "-w", str(timeout_ms), clean_host]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=(timeout_ms / 1000.0) + 1.5
        )
        out = proc.stdout

        # Procura tempo em milissegundos: "tempo=15ms" ou "time=15ms" ou "tempo<1ms"
        match = re.search(r"(?:tempo|time)[=<](\d+)ms", out, re.IGNORECASE)
        if match:
            ms = float(match.group(1))
            return True, ms
        elif "<1ms" in out:
            return True, 0.5
        return False, 0.0
    except Exception as exc:
        _log.debug("Falha no ping para %s: %s", clean_host, exc)
        return False, 0.0


def calculate_jitter(rtt_samples: List[float]) -> float:
    """
    Calcula a variação estatística de latência (Jitter) conforme a RFC 3550:
    Jitter = média das diferenças absolutas consecutivas |RTT_i - RTT_{i-1}|.
    """
    if len(rtt_samples) < 2:
        return 0.0

    diffs = [abs(rtt_samples[i] - rtt_samples[i - 1]) for i in range(1, len(rtt_samples))]
    return round(sum(diffs) / len(diffs), 2)


def calculate_stats(samples: List[float], total_sent: int) -> dict:
    """Consolida as métricas de latência, jitter e perda de pacotes."""
    if not samples:
        return {
            "current": 0.0,
            "min": 0.0,
            "avg": 0.0,
            "max": 0.0,
            "jitter": 0.0,
            "packet_loss_pct": 100.0 if total_sent > 0 else 0.0
        }

    total_received = len(samples)
    loss_pct = round(((total_sent - total_received) / total_sent * 100.0), 1) if total_sent > 0 else 0.0

    return {
        "current": round(samples[-1], 1),
        "min": round(min(samples), 1),
        "avg": round(sum(samples) / total_received, 1),
        "max": round(max(samples), 1),
        "jitter": calculate_jitter(samples),
        "packet_loss_pct": max(0.0, loss_pct)
    }
