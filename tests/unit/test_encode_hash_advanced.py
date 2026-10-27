"""
Testes unitários rigorosos (Black-Box Testing) para encode.hash_advanced.
Validação de integridade real, detecção de adulteração de arquivos e manifestos SFV/SHA256.
"""
from pathlib import Path
import pytest

from wintoolbox.tools.encode.hash_advanced.logic import (
    compute_file_hash_stream,
    generate_manifest_content,
    parse_manifest_lines,
    verify_manifest_file,
)
from wintoolbox.tools.encode.hash_advanced.tool import HashAdvancedTool


def test_hash_advanced_algorithms_deterministic(tmp_path: Path):
    # Cria arquivo com conteúdo exato
    content = b"WinToolbox 2026 Cryptographic Integrity Test"
    f = tmp_path / "sample.bin"
    f.write_bytes(content)

    # SHA-256
    sha256 = compute_file_hash_stream(f, "sha256")
    assert len(sha256) == 64
    assert sha256.islower()

    # SHA3-256
    sha3 = compute_file_hash_stream(f, "sha3-256")
    assert len(sha3) == 64

    # BLAKE2b
    b2b = compute_file_hash_stream(f, "blake2b")
    assert len(b2b) == 128

    # CRC32
    crc = compute_file_hash_stream(f, "crc32")
    assert len(crc) == 8
    assert crc.isupper()


def test_manifest_roundtrip_integrity_and_corruption_blackbox(tmp_path: Path):
    # Cria 3 arquivos reais
    f1 = tmp_path / "documento.pdf"
    f1.write_bytes(b"%PDF-1.4 teste de integridade 1")

    f2 = tmp_path / "foto.png"
    f2.write_bytes(b"\x89PNG teste de integridade 2")

    f3 = tmp_path / "audio.mp3"
    f3.write_bytes(b"ID3 teste de integridade 3")

    # Gera o manifesto SHA-256
    manifest_txt = generate_manifest_content([f1, f2, f3], algorithm="sha256")
    manifest_file = tmp_path / "checksums.sha256"
    manifest_file.write_text(manifest_txt, encoding="utf-8")

    # 1. Verifica estado original: todos devem ser OK
    results = verify_manifest_file(manifest_file)
    assert len(results) == 3
    for r in results:
        assert r["status"] == "OK"
        assert r["computed"] == r["expected"]

    # 2. Corrompe o arquivo 2 alterando 1 byte
    f2.write_bytes(b"\x89PNG teste de integridade 2 MODIFICADO")
    results_after_tamper = verify_manifest_file(manifest_file)
    r2 = next(r for r in results_after_tamper if r["filename"] == "foto.png")
    assert r2["status"] == "FALHOU"
    assert "Divergência de hash" in r2["details"]

    # 3. Deleta o arquivo 3
    f3.unlink()
    results_after_delete = verify_manifest_file(manifest_file)
    r3 = next(r for r in results_after_delete if r["filename"] == "audio.mp3")
    assert r3["status"] == "AUSENTE"
    assert "não encontrado" in r3["details"]


def test_sfv_format_manifest(tmp_path: Path):
    f = tmp_path / "arquivo.zip"
    f.write_bytes(b"PK\x03\x04 zip fake")

    crc_val = compute_file_hash_stream(f, "crc32")
    sfv_manifest = tmp_path / "checksums.sfv"
    sfv_manifest.write_text(f"; Comentario SFV\narquivo.zip {crc_val}\n", encoding="utf-8")

    results = verify_manifest_file(sfv_manifest)
    assert len(results) == 1
    assert results[0]["status"] == "OK"
    assert results[0]["filename"] == "arquivo.zip"
    assert results[0]["expected"] == crc_val


def test_hash_advanced_tool_ui(qtbot, tmp_path: Path):
    tool = HashAdvancedTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Cria arquivo temporário
    f = tmp_path / "teste_ui.txt"
    f.write_bytes(b"dados para ui de hash")

    # Gera manifesto
    view._selected_files_for_gen = [f]
    manifest_text = generate_manifest_content([f], "sha256")
    view._on_generate_success(manifest_text)
    assert "teste_ui.txt" in view._txt_manifest_output.toPlainText()

    # Salva manifesto em disco e testa verificação na UI
    manifest_file = tmp_path / "manifest.sha256"
    manifest_file.write_text(manifest_text, encoding="utf-8")
    view._txt_manifest_path.setText(str(manifest_file))

    results = verify_manifest_file(manifest_file)
    view._on_verify_success(results)
    assert "1 Válidos (OK)" in view._lbl_verify_summary.text()
