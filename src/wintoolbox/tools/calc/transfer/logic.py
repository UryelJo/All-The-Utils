"""
Lógica pura para estimativa de tempo de transferência e download de arquivos.
Diferenciação precisa entre Mbps (Megabits/s de banda contratada) e MB/s (Megabytes/s de transferência de dados).
Desacoplada de frameworks de interface gráfica.
"""
from typing import Any, Dict


def size_to_bytes(value: float, unit: str) -> float:
    """Converte valor de tamanho de arquivo para bytes."""
    u = unit.upper().strip()
    multipliers = {
        "B": 1.0,
        "KB": 1024.0,
        "MB": 1024.0 ** 2,
        "GB": 1024.0 ** 3,
        "TB": 1024.0 ** 4,
    }
    return value * multipliers.get(u, 1024.0 ** 2)


def speed_to_bps(value: float, unit: str) -> float:
    """
    Converte taxa de transferência para bits por segundo (bps).
    Telecomunicações utilizam potências decimais (1 Mbps = 1.000.000 bps).
    """
    u = unit.strip()
    if u == "Kbps":
        return value * 1_000.0
    elif u == "Mbps":
        return value * 1_000_000.0
    elif u == "Gbps":
        return value * 1_000_000_000.0
    elif u == "KB/s":
        return value * 8.0 * 1024.0
    elif u == "MB/s":
        return value * 8.0 * (1024.0 ** 2)
    elif u == "GB/s":
        return value * 8.0 * (1024.0 ** 3)
    return value * 1_000_000.0


def format_duration(seconds: float) -> str:
    """Formata duração em segundos para texto amigável em português."""
    if seconds <= 0:
        return "Instantâneo"

    sec = int(round(seconds))
    days, sec = divmod(sec, 86400)
    hours, sec = divmod(sec, 3600)
    minutes, sec = divmod(sec, 60)

    parts = []
    if days > 0:
        parts.append(f"{days} dia{'s' if days > 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hora{'s' if hours > 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} min")
    if sec > 0 or not parts:
        parts.append(f"{sec} seg")

    return " e ".join(parts[:2]) if len(parts) <= 2 else f"{parts[0]}, {parts[1]} e {parts[2]}"


def calculate_transfer_time(
    file_size_val: float,
    size_unit: str,
    speed_val: float,
    speed_unit: str,
    overhead_pct: float = 5.0
) -> Dict[str, Any]:
    """
    Calcula tempo estimado de download com base no tamanho, velocidade e overhead de pacotes TCP/IP.
    """
    if file_size_val <= 0 or speed_val <= 0:
        return {
            "segundos": 0.0,
            "tempo_formatado": "0 segundos",
            "velocidade_mbps": 0.0,
            "velocidade_mb_s": 0.0,
            "tamanho_mb": 0.0
        }

    total_bytes = size_to_bytes(file_size_val, size_unit)
    total_bits = total_bytes * 8.0

    raw_bps = speed_to_bps(speed_val, speed_unit)

    # Overhead TCP/IP reduz a vazão líquida de payload
    fator_eficiencia = max(0.5, (100.0 - overhead_pct) / 100.0)
    effective_bps = raw_bps * fator_eficiencia

    seconds = total_bits / effective_bps

    speed_mbps = round(raw_bps / 1_000_000.0, 2)
    speed_mb_s = round(raw_bps / (8.0 * (1024.0 ** 2)), 2)
    effective_mb_s = round(effective_bps / (8.0 * (1024.0 ** 2)), 2)
    tamanho_mb = round(total_bytes / (1024.0 ** 2), 2)

    return {
        "segundos": round(seconds, 2),
        "tempo_formatado": format_duration(seconds),
        "velocidade_mbps": speed_mbps,
        "velocidade_mb_s": speed_mb_s,
        "velocidade_efetiva_mb_s": effective_mb_s,
        "tamanho_mb": tamanho_mb
    }
