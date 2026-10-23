"""
Regressões das trocas de bibliotecas: opções das ferramentas de lote, criptografia v2,
XML seguro, QR (zxing-cpp), PDF (pikepdf/pypdfium2), HEIC/AVIF e isolamento do WinRT.
"""
import os
import threading
from pathlib import Path

import pytest
from PIL import Image

from wintoolbox.core.registry import FileTool, get_all_tools
from wintoolbox.tools.files.encrypt.logic import CHUNK_SIZE, decrypt_file, encrypt_file


def test_file_tools_expose_user_options(qtbot):
    """Regressão: ferramentas com 'get_params' tinham as opções da tela ignoradas pelo lote."""
    widgets = []
    for tool in get_all_tools():
        if not isinstance(tool, FileTool):
            continue
        assert not hasattr(tool, "get_params"), f"{tool.id} usa get_params (o lote chama get_options)"
        widgets.append(tool.build_options(None))
        if tool.id != "pdf.office_convert":  # única ferramenta de lote sem opções
            assert tool.get_options(), f"{tool.id}.get_options() vazio: opções da tela seriam ignoradas"


@pytest.mark.parametrize("size", [0, 1, CHUNK_SIZE, 2 * CHUNK_SIZE + 123])
def test_encryption_v2_roundtrip(tmp_path: Path, size: int):
    src = tmp_path / "dados.bin"
    src.write_bytes(os.urandom(size))
    enc = encrypt_file(src, tmp_path / "dados.enc", "senha")
    assert enc.read_bytes()[:8] == b"WTBX_AE2"
    assert decrypt_file(enc, tmp_path / "dados.out", "senha").read_bytes() == src.read_bytes()


def test_encryption_v2_detects_truncation_and_wrong_password(tmp_path: Path):
    src = tmp_path / "dados.bin"
    src.write_bytes(os.urandom(2 * CHUNK_SIZE + 10))
    enc = encrypt_file(src, tmp_path / "dados.enc", "senha")
    with pytest.raises(ValueError):
        decrypt_file(enc, tmp_path / "x.out", "errada")
    truncated = tmp_path / "trunc.enc"
    truncated.write_bytes(enc.read_bytes()[:-(10 + 16)])  # remove o último bloco
    with pytest.raises(ValueError):
        decrypt_file(truncated, tmp_path / "y.out", "senha")
    assert not (tmp_path / "x.out").exists() and not (tmp_path / "y.out").exists()


def test_xml_parsers_reject_entity_expansion(tmp_path: Path):
    from wintoolbox.tools.data.beautifier.logic import beautify_code
    from wintoolbox.tools.data.converter.logic import load_data
    bomb = '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><r>&b;</r>'
    f = tmp_path / "bomb.xml"
    f.write_text(bomb, encoding="utf-8")
    with pytest.raises(Exception):
        load_data(f)
    with pytest.raises(Exception):
        beautify_code(bomb, "XML")


def test_csv_from_excel_cp1252(tmp_path: Path):
    from wintoolbox.tools.data.converter.logic import load_data
    f = tmp_path / "excel.csv"
    f.write_bytes("nome,cidade\nJoão,São Paulo\n".encode("cp1252"))
    assert load_data(f) == [{"nome": "João", "cidade": "São Paulo"}]


def test_qrcode_roundtrip_with_zxing(tmp_path: Path):
    pytest.importorskip("zxingcpp")
    from wintoolbox.tools.images.qrcode.logic import decode_qrcode_from_image, generate_qrcode
    generate_qrcode("https://exemplo.com.br/ação", tmp_path / "qr.png")
    assert decode_qrcode_from_image(tmp_path / "qr.png") == "https://exemplo.com.br/ação"


def test_pdf_compress_recompresses_images_and_renders_pages(tmp_path: Path):
    pytest.importorskip("pikepdf")
    pytest.importorskip("pypdfium2")
    from wintoolbox.tools.pdf.compress.logic import compress_pdf_file
    from wintoolbox.tools.pdf.extract.logic import parse_page_selection, render_pdf_pages
    pages = [Image.effect_noise((1240, 1754), 40).convert("RGB") for _ in range(2)]
    src = tmp_path / "scan.pdf"
    pages[0].save(src, "PDF", save_all=True, append_images=pages[1:])
    res = compress_pdf_file(src, tmp_path / "scan_c.pdf", image_quality=60)
    assert res["engine"] == "pikepdf" and res["images_recompressed"] == 2
    assert res["dst_size"] < res["src_size"]
    out = render_pdf_pages(tmp_path / "scan_c.pdf", tmp_path / "pg", dpi=72, img_format="jpg", selection="2")
    assert [p.name for p in out] == ["scan_c_pagina_2.jpg"]
    assert parse_page_selection("1-2, 4-", 5) == [0, 1, 3, 4]


def test_pdf_compress_never_grows_file(tmp_path: Path):
    from wintoolbox.tools.pdf.compress.logic import compress_pdf_file
    src = tmp_path / "small.pdf"
    Image.new("RGB", (50, 50), "white").save(src, "PDF")
    res = compress_pdf_file(src, tmp_path / "small_c.pdf")
    assert res["dst_size"] <= res["src_size"]


def test_heic_and_avif_open_after_registration(tmp_path: Path):
    pytest.importorskip("pillow_heif")
    import wintoolbox.tools.images  # noqa: F401  (registra o leitor HEIC)
    img = Image.new("RGB", (64, 32), (10, 120, 200))
    img.save(tmp_path / "a.heic")
    img.save(tmp_path / "a.avif")
    assert Image.open(tmp_path / "a.heic").size == (64, 32)
    assert Image.open(tmp_path / "a.avif").size == (64, 32)


def test_winrt_calls_survive_sta_thread():
    """Regressão: WinRT async travava numa thread já inicializada como STA (pyttsx3/SAPI)."""
    pytest.importorskip("winrt.windows.media.speechsynthesis")
    pythoncom = pytest.importorskip("pythoncom")
    from wintoolbox.tools.media.speech.logic import _list_winrt_voices
    result = {}

    def sta_worker():
        pythoncom.CoInitialize()  # o mesmo que o comtypes faz para o SAPI
        try:
            result["voices"] = _list_winrt_voices()
        finally:
            pythoncom.CoUninitialize()

    t = threading.Thread(target=sta_worker, daemon=True)
    t.start()
    t.join(20)
    assert not t.is_alive(), "chamada WinRT travou em thread STA"
    assert "voices" in result
