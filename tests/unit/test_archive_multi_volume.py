"""
Testes unitários e de validação de efeito real para archive.multi_volume.
"""
import hashlib
from pathlib import Path

from wintoolbox.tools.archive.multi_volume.logic import (
    split_file_into_volumes,
    find_volume_parts,
    join_volumes_to_file,
)


def test_split_and_join_ext_num_pattern(tmp_path: Path):
    """Testa divisão e junção com padrão .001, .002 validando integridade SHA-256."""
    src_file = tmp_path / "pacote.zip"
    # Cria arquivo de 250 KB
    content = b"TESTE_MULTI_VOLUME_DATA_12345\n" * 10000
    src_file.write_bytes(content)
    orig_hash = hashlib.sha256(content).hexdigest()

    out_split_dir = tmp_path / "volumes_ext"

    # Divide em partes de 80 KB
    parts = split_file_into_volumes(
        input_file=src_file,
        output_dir=out_split_dir,
        volume_size_bytes=80 * 1024,
        pattern="EXT_NUM",
    )

    assert len(parts) == 4
    assert parts[0].name == "pacote.zip.001"
    assert parts[1].name == "pacote.zip.002"
    assert parts[2].name == "pacote.zip.003"
    assert parts[3].name == "pacote.zip.004"

    # Testa busca automática de partes a partir do primeiro volume
    detected = find_volume_parts(parts[0])
    assert detected == parts

    # Reconstrói arquivo
    out_joined = tmp_path / "reconstruido.zip"
    res = join_volumes_to_file(detected, out_joined)

    assert res.is_file()
    assert res == out_joined
    joined_bytes = res.read_bytes()
    assert hashlib.sha256(joined_bytes).hexdigest() == orig_hash
    assert joined_bytes == content


def test_split_and_join_part_num_pattern(tmp_path: Path):
    """Testa divisão e junção com padrão .part01.bin, .part02.bin."""
    src_file = tmp_path / "dados.bin"
    content = b"\xAA\xBB\xCC\xDD" * 5000
    src_file.write_bytes(content)

    out_split_dir = tmp_path / "volumes_part"

    parts = split_file_into_volumes(
        input_file=src_file,
        output_dir=out_split_dir,
        volume_size_bytes=5 * 1024,
        pattern="PART_NUM",
    )

    assert len(parts) == 4
    assert parts[0].name == "dados.part01.bin"
    assert parts[1].name == "dados.part02.bin"

    detected = find_volume_parts(parts[0])
    assert detected == parts

    out_joined = tmp_path / "dados_unidos.bin"
    join_volumes_to_file(detected, out_joined)
    assert out_joined.read_bytes() == content
