"""
Lógica pura para leitura de arquivos de log volumosos, análise de níveis de severidade,
leitura do final do arquivo (tail), filtragem por texto/regex e cálculo de métricas.

Zero dependências de interface gráfica ou widgets.
"""
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple


LOG_LEVEL_PATTERN = re.compile(
    r"\b(FATAL|CRITICAL|ERROR|WARN|WARNING|INFO|DEBUG|TRACE)\b",
    re.IGNORECASE,
)

TIMESTAMP_PATTERN = re.compile(
    r"^(\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?|\b\d{2}:\d{2}:\d{2}\b)",
)


def get_file_info(file_path: str) -> Dict[str, Any]:
    """Retorna metadados básicos do arquivo de log."""
    p = Path(file_path)
    if not p.exists():
        return {"exists": False, "size_bytes": 0, "size_formatted": "0 B"}

    stat = p.stat()
    size = stat.st_size

    if size < 1024:
        size_fmt = f"{size} B"
    elif size < 1024 * 1024:
        size_fmt = f"{size / 1024:.1f} KB"
    else:
        size_fmt = f"{size / (1024 * 1024):.1f} MB"

    return {
        "exists": True,
        "name": p.name,
        "size_bytes": size,
        "size_formatted": size_fmt,
        "modified_timestamp": stat.st_mtime,
    }


def read_tail_lines(file_path: str, max_lines: int = 500, encoding: str = "utf-8") -> List[str]:
    """
    Lê com eficiência as últimas 'max_lines' de um arquivo sem carregar o arquivo inteiro na memória.
    """
    p = Path(file_path)
    if not p.exists() or p.stat().st_size == 0:
        return []

    file_size = p.stat().st_size
    lines: List[str] = []
    buffer_size = 8192
    block_offset = file_size

    with open(file_path, "rb") as f:
        accumulated = bytearray()
        while block_offset > 0 and len(lines) < max_lines:
            read_size = min(buffer_size, block_offset)
            block_offset -= read_size
            f.seek(block_offset)
            chunk = f.read(read_size)
            accumulated = chunk + accumulated

            try:
                text = accumulated.decode(encoding, errors="replace")
                split_lines = text.splitlines()
                if len(split_lines) > max_lines:
                    lines = split_lines[-max_lines:]
                    break
                else:
                    lines = split_lines
            except Exception:
                pass

    return lines


def parse_log_line(line: str) -> Dict[str, Any]:
    """
    Analisa uma linha de log para identificar timestamp, nível de severidade e mensagem.
    """
    clean_line = line.strip()
    level = "INFO"
    timestamp = ""

    # Extrai timestamp se estiver no início
    ts_match = TIMESTAMP_PATTERN.search(clean_line)
    if ts_match:
        timestamp = ts_match.group(1)

    # Identifica nível
    lvl_match = LOG_LEVEL_PATTERN.search(clean_line)
    if lvl_match:
        raw_lvl = lvl_match.group(1).upper()
        if raw_lvl == "WARNING":
            level = "WARN"
        elif raw_lvl == "CRITICAL":
            level = "FATAL"
        else:
            level = raw_lvl

    return {
        "raw": line,
        "level": level,
        "timestamp": timestamp,
        "message": clean_line,
    }


def filter_log_records(
    records: List[Dict[str, Any]],
    level_filter: str = "ALL",
    text_query: str = "",
    is_regex: bool = False,
) -> List[Dict[str, Any]]:
    """
    Filtra lista de registros de log por nível e por texto/expressão regular.
    """
    target_lvl = level_filter.upper()
    needle = text_query.strip()
    regex_obj = None

    if needle and is_regex:
        try:
            regex_obj = re.compile(needle, re.IGNORECASE)
        except re.error:
            # Fallback para substring comum se regex for inválido
            regex_obj = None

    filtered: List[Dict[str, Any]] = []

    for rec in records:
        # Filtro por nível
        if target_lvl != "ALL" and rec["level"] != target_lvl:
            continue

        # Filtro por texto
        if needle:
            raw_text = rec["raw"]
            if regex_obj is not None:
                if not regex_obj.search(raw_text):
                    continue
            else:
                if needle.lower() not in raw_text.lower():
                    continue

        filtered.append(rec)

    return filtered
