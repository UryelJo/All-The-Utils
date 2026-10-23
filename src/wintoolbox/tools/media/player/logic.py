"""
Lógica auxiliar para o player de mídia nativo do Qt.
"""


def format_duration(ms: int) -> str:
    """Converte duração em milissegundos para formato legível (MM:SS ou HH:MM:SS)."""
    if ms < 0:
        return "00:00"

    total_seconds = ms // 1000
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
