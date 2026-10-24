"""
Lógica pura de detecção e conversão de codificação de texto e finais de linha (CRLF/LF).
Totalmente desacoplada de bibliotecas de interface visual.
"""
from typing import Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("files.encoding_converter")


def detect_encoding(raw_bytes: bytes) -> str:
    """Detecta a codificação mais provável do arquivo a partir de BOMs e heurísticas."""
    if not raw_bytes:
        return "utf-8"

    # Verifica BOMs
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    elif raw_bytes.startswith(b"\xff\xfe"):
        return "utf-16-le"
    elif raw_bytes.startswith(b"\xfe\xff"):
        return "utf-16-be"

    # Tenta decodificar como UTF-8 estrito
    try:
        raw_bytes.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # Tenta decodificar como Windows-1252 / ANSI
    try:
        raw_bytes.decode("cp1252")
        return "windows-1252"
    except UnicodeDecodeError:
        pass

    # Fallback para ISO-8859-1 (aceita qualquer byte)
    return "iso-8859-1"


def convert_text_content(
    raw_bytes: bytes,
    target_encoding: str = "utf-8",
    line_ending: str = "keep"
) -> Tuple[bytes, str]:
    """
    Converte bytes de texto para a codificação de destino e ajusta finais de linha.
    line_ending: 'keep', 'crlf' (Windows \r\n), 'lf' (Linux \n).
    """
    source_enc = detect_encoding(raw_bytes)

    # Decodifica para string Python
    try:
        text = raw_bytes.decode(source_enc)
    except Exception:
        # Fallback tolerante com substituição
        text = raw_bytes.decode(source_enc, errors="replace")

    # Ajusta finais de linha
    if line_ending == "crlf":
        # Normaliza primeiro para \n e depois converte para \r\n
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    elif line_ending == "lf":
        text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Mapeia identificador de codificação amigável
    enc_map = {
        "utf-8": "utf-8",
        "utf-8-sig": "utf-8-sig",
        "utf-16": "utf-16",
        "utf-16-le": "utf-16-le",
        "windows-1252": "cp1252",
        "ansi": "cp1252",
        "iso-8859-1": "iso-8859-1",
        "ascii": "ascii"
    }
    actual_enc = enc_map.get(target_encoding.lower().strip(), "utf-8")

    converted_bytes = text.encode(actual_enc, errors="replace")
    detail_msg = f"{source_enc.upper()} -> {actual_enc.upper()}"
    return converted_bytes, detail_msg
