"""
Lógica pura para leitura sob demanda, paginação e visualização hexadecimal de arquivos binários.
Suporta arquivos de qualquer tamanho com rolagem virtual por offset e busca por hex ou ASCII.

Zero dependências de interface gráfica ou widgets.
"""
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple


def read_hex_chunk(
    file_path: str,
    offset: int,
    length: int = 4096,
) -> Tuple[bytes, int, int]:
    """
    Lê um bloco de 'length' bytes a partir do 'offset' no arquivo.
    Retorna (dados_bytes, offset_real, tamanho_total_do_arquivo).
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    total_size = p.stat().st_size
    real_offset = max(0, min(offset, total_size))

    with open(file_path, "rb") as f:
        f.seek(real_offset)
        data = f.read(length)

    return data, real_offset, total_size


def format_hex_dump(
    data: bytes,
    base_offset: int = 0,
    bytes_per_line: int = 16,
) -> str:
    """
    Formata bytes no formato canônico de hex dump:
    OFFSET (8 hex) | BYTES HEXADECIMAIS (16 bytes com separador) | CARACTERES ASCII
    """
    if not data:
        return ""

    lines: List[str] = []
    total_len = len(data)

    for i in range(0, total_len, bytes_per_line):
        chunk = data[i:i + bytes_per_line]
        current_offset = base_offset + i

        # Hex representation
        hex_parts: List[str] = []
        for b in chunk:
            hex_parts.append(f"{b:02X}")

        # Se a linha for menor que bytes_per_line, preenche com espaços
        if len(hex_parts) < bytes_per_line:
            hex_parts.extend(["  "] * (bytes_per_line - len(hex_parts)))

        # Separação a cada 8 bytes
        first_half = " ".join(hex_parts[:8])
        second_half = " ".join(hex_parts[8:])
        hex_str = f"{first_half}  {second_half}"

        # ASCII representation (apenas imprimíveis)
        ascii_parts: List[str] = []
        for b in chunk:
            if 32 <= b <= 126:
                ascii_parts.append(chr(b))
            else:
                ascii_parts.append(".")
        ascii_str = "".join(ascii_parts)

        lines.append(f"{current_offset:08X}  {hex_str}  |{ascii_str}|")

    return "\n".join(lines)


def search_in_binary_file(
    file_path: str,
    query: str,
    is_hex: bool = False,
    max_results: int = 100,
) -> List[int]:
    """
    Busca ocorrências de uma sequência hexadecimal ou string ASCII em um arquivo binário.
    Retorna lista de offsets onde o padrão foi encontrado.
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    # Converte query para bytes alvo
    if is_hex:
        clean_hex = re.sub(r"[^a-fA-F0-9]", "", query)
        if len(clean_hex) % 2 != 0:
            clean_hex = "0" + clean_hex
        try:
            target_bytes = bytes.fromhex(clean_hex)
        except ValueError:
            return []
    else:
        target_bytes = query.encode("utf-8", errors="replace")

    if not target_bytes:
        return []

    target_len = len(target_bytes)
    found_offsets: List[int] = []
    chunk_size = 65536
    overlap = target_len - 1

    with open(file_path, "rb") as f:
        file_offset = 0
        tail = b""

        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break

            data = tail + chunk
            pos = 0
            while True:
                idx = data.find(target_bytes, pos)
                if idx == -1:
                    break

                abs_offset = file_offset - len(tail) + idx
                found_offsets.append(abs_offset)
                if len(found_offsets) >= max_results:
                    return found_offsets
                pos = idx + 1

            if len(data) >= overlap:
                tail = data[-overlap:] if overlap > 0 else b""
            else:
                tail = data

            file_offset += len(chunk)

    return found_offsets
