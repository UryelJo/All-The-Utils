"""
Lógica pura da ferramenta Editor e Conversor de Legendas (media.subtitles).
Suporta leitura, conversão bidirecional entre SRT e WebVTT e ajuste de sincronismo (Time Shift).
"""
import re
from pathlib import Path
from typing import Any, Dict, List


def ms_to_srt_time(ms: int) -> str:
    """Converte milissegundos para o formato SRT: HH:MM:SS,mmm"""
    ms = max(0, ms)
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    milliseconds = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def ms_to_vtt_time(ms: int) -> str:
    """Converte milissegundos para o formato VTT: HH:MM:SS.mmm"""
    ms = max(0, ms)
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    milliseconds = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def time_to_ms(time_str: str) -> int:
    """Converte string de tempo HH:MM:SS,mmm ou HH:MM:SS.mmm para milissegundos."""
    time_str = time_str.strip().replace(",", ".")
    parts = time_str.split(":")
    if len(parts) == 3:
        h = int(parts[0])
        m = int(parts[1])
        s_parts = parts[2].split(".")
        s = int(s_parts[0])
        ms = int(s_parts[1].ljust(3, "0")[:3]) if len(s_parts) > 1 else 0
        return (h * 3600 + m * 60 + s) * 1000 + ms
    elif len(parts) == 2:
        m = int(parts[0])
        s_parts = parts[1].split(".")
        s = int(s_parts[0])
        ms = int(s_parts[1].ljust(3, "0")[:3]) if len(s_parts) > 1 else 0
        return (m * 60 + s) * 1000 + ms
    return 0


def strip_html_tags(text: str) -> str:
    """Remove marcações HTML como <i>, <b>, <font>, etc."""
    return re.sub(r"<[^>]+>", "", text).strip()


def parse_subtitles(content: str) -> List[Dict[str, Any]]:
    """Lê conteúdo em formato SRT ou WebVTT e extrai a lista estruturada de legendas."""
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    items: List[Dict[str, Any]] = []

    # Pula cabeçalho WEBVTT se presente
    start_idx = 0
    if lines and "WEBVTT" in lines[0]:
        start_idx = 1
        while start_idx < len(lines) and lines[start_idx].strip() != "":
            start_idx += 1

    current_idx = 1
    i = start_idx
    n = len(lines)

    time_regex = re.compile(r"((?:\d{2}:)?\d{2}:\d{2}[,\.]\d{3})\s*-->\s*((?:\d{2}:)?\d{2}:\d{2}[,\.]\d{3})")

    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Verifica se é timestamp
        match = time_regex.search(line)
        if match:
            start_ms = time_to_ms(match.group(1))
            end_ms = time_to_ms(match.group(2))
            i += 1
            text_lines = []
            while i < n and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            items.append({
                "index": current_idx,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": "\n".join(text_lines),
            })
            current_idx += 1
        else:
            # Pode ser o número sequencial do SRT anterior ao timestamp
            if i + 1 < n and time_regex.search(lines[i + 1]):
                i += 1
                continue
        i += 1

    return items


def shift_subtitles(items: List[Dict[str, Any]], offset_ms: int) -> List[Dict[str, Any]]:
    """Aplica deslocamento de tempo em milissegundos (+ para adiantar, - para atrasar)."""
    shifted = []
    for it in items:
        new_start = max(0, it["start_ms"] + offset_ms)
        new_end = max(new_start + 100, it["end_ms"] + offset_ms)
        shifted.append({
            "index": it["index"],
            "start_ms": new_start,
            "end_ms": new_end,
            "text": it["text"],
        })
    return shifted


def generate_srt(items: List[Dict[str, Any]], strip_tags: bool = False) -> str:
    """Gera string no formato SRT oficial."""
    blocks = []
    for idx, it in enumerate(items, 1):
        txt = strip_html_tags(it["text"]) if strip_tags else it["text"]
        t_start = ms_to_srt_time(it["start_ms"])
        t_end = ms_to_srt_time(it["end_ms"])
        blocks.append(f"{idx}\n{t_start} --> {t_end}\n{txt}")
    return "\n\n".join(blocks) + "\n"


def generate_vtt(items: List[Dict[str, Any]], strip_tags: bool = False) -> str:
    """Gera string no formato WebVTT oficial."""
    blocks = ["WEBVTT\n"]
    for idx, it in enumerate(items, 1):
        txt = strip_html_tags(it["text"]) if strip_tags else it["text"]
        t_start = ms_to_vtt_time(it["start_ms"])
        t_end = ms_to_vtt_time(it["end_ms"])
        blocks.append(f"{idx}\n{t_start} --> {t_end}\n{txt}")
    return "\n\n".join(blocks) + "\n"


def load_subtitle_file(file_path: Path) -> List[Dict[str, Any]]:
    """Carrega e analisa um arquivo de legenda .srt ou .vtt com fallback de codificação."""
    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    raw = file_path.read_bytes()
    for enc in ["utf-8-sig", "utf-8", "windows-1252", "iso-8859-1"]:
        try:
            text = raw.decode(enc)
            return parse_subtitles(text)
        except UnicodeDecodeError:
            continue
    return parse_subtitles(raw.decode("utf-8", errors="replace"))
