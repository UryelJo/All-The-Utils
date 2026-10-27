"""
Testes unitários e de validação de efeito real para archive.integrity_repair.
"""
from pathlib import Path
import zipfile

from wintoolbox.tools.archive.integrity_repair.logic import (
    verify_zip_integrity,
    salvage_archive_files,
    scan_zip_local_headers,
)


def test_verify_zip_intact(tmp_path: Path):
    """Testa verificação de um arquivo ZIP 100% saudável."""
    zip_path = tmp_path / "saudavel.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("doc1.txt", "Texto do documento 1")
        zf.writestr("doc2.txt", "Texto do documento 2")

    res = verify_zip_integrity(zip_path)
    assert res["status"] == "INTACTO"
    assert res["total_members"] == 2
    assert res["intact_members"] == 2
    assert res["corrupt_members"] == 0
    assert res["header_intact"] is True


def test_verify_and_salvage_corrupted_zip(tmp_path: Path):
    """Testa detecção e salvamento de arquivos intactos em um ZIP corrompido."""
    zip_path = tmp_path / "corrompido.zip"
    out_dir = tmp_path / "saida_recuperada"

    content_intacto = "Este texto deve ser salvo sem nenhum erro!"
    content_alvo = "Este texto vai sofrer corrupcao binaria proposital!"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("intacto.txt", content_intacto)
        zf.writestr("danificado.txt", content_alvo)

    # Corrompe intencionalmente bytes do segundo arquivo no disco físico
    raw = bytearray(zip_path.read_bytes())
    pos = raw.find(b"proposital")
    assert pos != -1
    raw[pos : pos + 5] = b"XXXXX"  # Altera bytes sem alterar o header
    zip_path.write_bytes(raw)

    # 1. Verifica integridade
    res_verify = verify_zip_integrity(zip_path)
    assert res_verify["status"] == "PARCIALMENTE_CORROMPIDO"
    assert res_verify["intact_members"] == 1
    assert res_verify["corrupt_members"] == 1

    # 2. Executa salvamento de emergência
    res_salvage = salvage_archive_files(zip_path, out_dir)
    assert res_salvage["salvaged_count"] == 1
    assert "intacto.txt" in res_salvage["salvaged_files"]

    # 3. Validação do efeito real: o arquivo intacto recuperado é idêntico ao original
    salvaged_file = out_dir / "intacto.txt"
    assert salvaged_file.is_file()
    assert salvaged_file.read_text(encoding="utf-8") == content_intacto


def test_scan_zip_local_headers(tmp_path: Path):
    """Testa varredura heurística quando o diretório central é perdido."""
    zip_path = tmp_path / "sem_central.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("relatorio.csv", "id,nome\n1,Alpha\n2,Beta")

    headers = scan_zip_local_headers(zip_path)
    assert len(headers) == 1
    assert headers[0]["name"] == "relatorio.csv"
    assert headers[0]["status"] == "RECUPERAVEL"
