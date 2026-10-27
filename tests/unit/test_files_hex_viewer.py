"""
Testes unitários rigorosos para files.hex_viewer.logic.
Garante leitura por chunks, formatação de hex dump canônico e busca binária exata.
"""
from pathlib import Path
import pytest
from wintoolbox.tools.files.hex_viewer.logic import (
    format_hex_dump,
    read_hex_chunk,
    search_in_binary_file,
)


def test_format_hex_dump():
    data = b"Hello, World!\x00\x01\x02"
    dump = format_hex_dump(data, base_offset=0, bytes_per_line=16)

    assert "00000000" in dump
    assert "48 65 6C 6C 6F 2C 20 57" in dump  # "Hello, W"
    assert "|Hello, World!...|" in dump


def test_read_hex_chunk_and_search(tmp_path: Path):
    sample_file = tmp_path / "binario.dat"
    content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32 + b"TOKEN_SECRETO_123" + bytes(range(100))
    sample_file.write_bytes(content)

    # Leitura do chunk
    chunk, offset, total = read_hex_chunk(str(sample_file), offset=0, length=16)
    assert offset == 0
    assert total == len(content)
    assert chunk == b"\x89PNG\r\n\x1a\n" + b"\x00" * 8

    # Busca ASCII
    offsets_token = search_in_binary_file(str(sample_file), "TOKEN_SECRETO_123", is_hex=False)
    assert len(offsets_token) == 1
    assert offsets_token[0] == 8 + 32  # 40 bytes
    assert content[offsets_token[0]:offsets_token[0] + 17] == b"TOKEN_SECRETO_123"

    # Busca Hex
    offsets_hex = search_in_binary_file(str(sample_file), "89 50 4E 47", is_hex=True)
    assert len(offsets_hex) == 1
    assert offsets_hex[0] == 0


def test_search_nonexistent_and_file_not_found(tmp_path: Path):
    f = tmp_path / "teste.bin"
    f.write_bytes(b"dados_comuns")

    assert search_in_binary_file(str(f), "inexistente") == []

    with pytest.raises(FileNotFoundError):
        read_hex_chunk("C:/arquivo/inexistente_12345.bin", offset=0)
