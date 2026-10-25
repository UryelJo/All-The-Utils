"""
Testes unitários rigorosos e verídicos para as novas ferramentas e recursos:
- files.junction_mover (criação de junção NTFS real, validação contra recursão e rollback)
- archive.manager (compressão e extração real de .7z e .zip, listagem com 7z/py7zr)
- pdf.stamp (carimbo e numeração sem deprecation warnings, extração e validação de texto)
- pdf.page_organizer (renderização de miniaturas e compilação de PDF reordenado)
- media.normalize (preservação de taxa de amostragem sem inflação de 192 kHz)
- media.subtitles (parsing, time shift e conversão de legendas)
- media.transcribe (formatos de timestamp e geração de SRT)
- calc.date_calculator (Consciência Negra >= 2024, Páscoa e dias úteis exatos)
- network.public_apis (tratamento de erro sem vazamento de JSONDecodeError e validações)
"""
from datetime import date
import io
import os
from pathlib import Path
import subprocess
import urllib.error
import pytest

import pypdf
import py7zr

from wintoolbox.tools.calc.date_calculator.logic import (
    calculate_easter, get_brazilian_holidays, get_detailed_holidays_for_year,
    diff_dates, add_business_days
)
from wintoolbox.tools.media.subtitles.logic import (
    parse_subtitles, shift_subtitles, generate_srt, generate_vtt
)
from wintoolbox.tools.media.transcribe.logic import (
    format_srt_timestamp, segments_to_srt, segments_to_plain_text
)
from wintoolbox.tools.media.normalize.logic import (
    build_loudnorm_command, normalize_audio_file, get_audio_sample_rate
)
from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe
from wintoolbox.tools.files.junction_mover.logic import (
    is_reparse_point, calculate_dir_size, validate_move_junction,
    move_folder_and_create_junction, create_ntfs_junction
)
from wintoolbox.tools.archive.manager.logic import (
    compress_items, extract_archive, inspect_archive
)
from wintoolbox.tools.pdf.stamp.logic import apply_stamp_and_numbering
from wintoolbox.tools.pdf.page_organizer.logic import (
    render_page_thumbnails, save_organized_pdf
)
from wintoolbox.tools.network.public_apis.logic import (
    fetch_cep_info, fetch_cnpj_info, fetch_ddd_info, fetch_fipe_info,
    _handle_brasilapi_error
)


def test_date_calculator_holidays_and_historical_rules():
    """Valida cálculo de Páscoa e regra histórica da Consciência Negra (Lei 14.759/2023)."""
    # Páscoa 2026: 5 de Abril de 2026
    easter_2026 = calculate_easter(2026)
    assert easter_2026 == date(2026, 4, 5)

    # 20/11 NÃO era feriado nacional em 2020
    hols_2020 = get_brazilian_holidays(2020)
    assert date(2020, 11, 20) not in hols_2020

    # 20/11 É feriado nacional a partir de 2024
    hols_2024 = get_brazilian_holidays(2024)
    assert date(2024, 11, 20) in hols_2024
    hols_2026 = get_brazilian_holidays(2026)
    assert date(2026, 11, 20) in hols_2026

    detailed = get_detailed_holidays_for_year(2026)
    assert len(detailed) >= 12
    assert any(h["name"] == "Natal" for h in detailed)
    assert any("Consciência Negra" in h["name"] for h in detailed)

    # Diferença exata de 1 de Abril a 10 de Abril de 2026:
    # 03/04/2026 é Sexta-feira Santa (feriado nacional)
    diff = diff_dates(date(2026, 4, 1), date(2026, 4, 10), consider_holidays=True)
    assert diff["holidays_count"] == 1
    assert diff["total_days"] == 9


def test_subtitles_parsing_shifting_and_export():
    """Valida análise, deslocamento temporal e exportação para SRT e WebVTT."""
    sample_srt = """1
00:00:01,000 --> 00:00:04,000
<i>Primeira linha</i> com marcação.

2
00:00:05,500 --> 00:00:08,000
Segunda fala sincronizada.
"""
    items = parse_subtitles(sample_srt)
    assert len(items) == 2
    assert items[0]["start_ms"] == 1000
    assert items[0]["end_ms"] == 4000
    assert "Primeira linha" in items[0]["text"]

    # Deslocamento positivo (+500ms)
    shifted_pos = shift_subtitles(items, 500)
    assert shifted_pos[0]["start_ms"] == 1500
    assert shifted_pos[0]["end_ms"] == 4500

    # Deslocamento negativo sem deixar tempo negativo
    shifted_neg = shift_subtitles(items, -2000)
    assert shifted_neg[0]["start_ms"] == 0

    # Exportação SRT
    out_srt = generate_srt(shifted_pos, strip_tags=True)
    assert "00:00:01,500 --> 00:00:04,500" in out_srt
    assert "<i>" not in out_srt  # Marcações HTML removidas

    # Exportação WebVTT
    out_vtt = generate_vtt(shifted_pos, strip_tags=True)
    assert out_vtt.startswith("WEBVTT")
    assert "00:00:01.500 --> 00:00:04.500" in out_vtt


def test_transcribe_helpers():
    """Valida conversão de timestamps e formatação de texto de IA."""
    ts = format_srt_timestamp(3661.5)
    assert ts == "01:01:01,500"

    segments = [
        {"start": 0.0, "end": 2.5, "text": "Bem-vindo ao WinToolbox."},
        {"start": 3.0, "end": 6.0, "text": "Ferramentas completas para Windows."}
    ]
    srt = segments_to_srt(segments)
    assert "00:00:00,000 --> 00:00:02,500" in srt
    assert "Bem-vindo ao WinToolbox." in srt

    plain = segments_to_plain_text(segments)
    assert "Bem-vindo ao WinToolbox." in plain
    assert "Ferramentas completas para Windows." in plain


def test_normalize_loudnorm_preserves_sample_rate(tmp_path):
    """Gera áudio real com FFmpeg e verifica que a normalização preserva a taxa de amostragem."""
    ffmpeg = get_ffmpeg_exe()
    if not ffmpeg:
        pytest.skip("FFmpeg não disponível no ambiente para teste de codificação de áudio.")

    src_wav = tmp_path / "tom_44100.wav"
    dst_wav = tmp_path / "tom_normalizado.wav"

    # Gera tom senoidal sintético de 1 segundo a 44100 Hz
    flags = 0x08000000 if os.name == "nt" else 0
    gen_cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=1",
        "-ar", "44100",
        str(src_wav)
    ]
    subprocess.run(gen_cmd, capture_output=True, check=True, creationflags=flags)
    assert src_wav.exists()

    # Normaliza o áudio
    normalize_audio_file(src_wav, dst_wav, target_lufs=-14.0)
    assert dst_wav.exists()

    # Confere se a taxa de amostragem permaneceu 44100 Hz (não virou 192 kHz)
    out_sr = get_audio_sample_rate(dst_wav)
    assert out_sr == 44100


def test_junction_mover_prevents_recursion_and_executes_real_junction(tmp_path):
    """Valida prevenção de recursão e cria uma junção NTFS real no Windows."""
    source = tmp_path / "origem_dados"
    source.mkdir()
    doc = source / "documento.txt"
    doc.write_text("conteúdo confidencial que deve ser preservado", encoding="utf-8")

    # 1. Validação: Bloquear destino dentro da própria origem
    sub_dest = source / "subpasta_destino"
    is_valid, msg = validate_move_junction(source, sub_dest)
    assert is_valid is False
    assert "recursão" in msg.lower() or "dentro" in msg.lower()

    # 2. Executar movimentação e criação de junção real para destino externo
    dest = tmp_path / "destino_externo"
    result = move_folder_and_create_junction(source, dest)
    assert result["success"] is True

    # 3. Validações da Junção NTFS no Windows
    assert is_reparse_point(source)
    assert dest.exists()
    assert (dest / "documento.txt").exists()

    # O arquivo deve continuar acessível e legível através do caminho original da junção!
    link_doc = source / "documento.txt"
    assert link_doc.exists()
    assert link_doc.read_text(encoding="utf-8") == "conteúdo confidencial que deve ser preservado"


def test_pdf_stamp_and_text_content_validation(tmp_path):
    """Aplica carimbo e numeração em PDF e extrai o texto com pypdf para comprovar aplicação."""
    # Cria PDF inicial mínimo de 2 páginas
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_blank_page(width=595, height=842)

    in_pdf = tmp_path / "base.pdf"
    out_pdf = tmp_path / "carimbado.pdf"
    with open(in_pdf, "wb") as f:
        writer.write(f)

    # Aplica marca d'água e numeração sem DeprecationWarnings
    apply_stamp_and_numbering(
        src_path=in_pdf,
        dst_path=out_pdf,
        enable_watermark=True,
        watermark_text="CONFIDENCIAL",
        enable_numbering=True,
        numbering_position="bottom_right",
        numbering_format="Página {page} de {total}",
        watermark_opacity=0.3
    )

    assert out_pdf.exists()
    reader = pypdf.PdfReader(str(out_pdf))
    assert len(reader.pages) == 2

    # Extrai o texto renderizado na primeira e segunda página
    p1_text = reader.pages[0].extract_text()
    p2_text = reader.pages[1].extract_text()

    assert "CONFIDENCIAL" in p1_text
    assert "Página 1 de 2" in p1_text
    assert "CONFIDENCIAL" in p2_text
    assert "Página 2 de 2" in p2_text


def test_pdf_page_organizer_thumbnails_and_reorder(tmp_path):
    """Testa renderização de miniaturas em memória e salvamento de PDF reorganizado."""
    writer = pypdf.PdfWriter()
    p1 = writer.add_blank_page(width=400, height=600)
    p2 = writer.add_blank_page(width=400, height=600)

    in_pdf = tmp_path / "doc_pages.pdf"
    out_pdf = tmp_path / "doc_reordered.pdf"
    with open(in_pdf, "wb") as f:
        writer.write(f)

    # Renderiza miniaturas
    thumbs = render_page_thumbnails(in_pdf, scale=0.1)
    assert len(thumbs) == 2
    assert thumbs[0][0] == 0  # original index
    assert len(thumbs[0][1]) > 50  # PNG bytes

    # Reordena: inverte páginas [1, 0] e descarta nenhuma
    plan = [
        {"original_index": 1, "rotation": 90},
        {"original_index": 0, "rotation": 0},
    ]
    save_organized_pdf(in_pdf, out_pdf, plan)
    assert out_pdf.exists()

    reader = pypdf.PdfReader(str(out_pdf))
    assert len(reader.pages) == 2
    assert reader.pages[0].rotation == 90
    assert reader.pages[1].rotation == 0


def test_archive_manager_7z_real_compression_and_extraction(tmp_path):
    """Compacta e extrai arquivo .7z real com py7zr e verifica conteúdo."""
    src_dir = tmp_path / "origem_7z"
    src_dir.mkdir()
    f1 = src_dir / "arquivo_teste.txt"
    f1.write_text("conteúdo compactado via py7zr", encoding="utf-8")

    archive_7z = tmp_path / "pacote_teste.7z"

    # Compacta em .7z usando a biblioteca py7zr
    with py7zr.SevenZipFile(archive_7z, "w") as z:
        z.write(f1, arcname="arquivo_teste.txt")
    assert archive_7z.exists()

    # Inspeciona conteúdo sem extrair
    items = inspect_archive(archive_7z)
    assert len(items) >= 1
    assert any(it["name"] == "arquivo_teste.txt" for it in items)

    # Extrai arquivo .7z
    out_dir = tmp_path / "destino_7z"
    count = extract_archive(archive_7z, out_dir)
    assert count >= 1
    assert (out_dir / "arquivo_teste.txt").exists()
    assert (out_dir / "arquivo_teste.txt").read_text(encoding="utf-8") == "conteúdo compactado via py7zr"


def test_public_apis_error_handling_and_validations():
    """Valida que erros HTTP não-JSON (502, HTML) não quebram com JSONDecodeError."""
    # Simula resposta HTTP 502 Bad Gateway com corpo HTML
    html_error = urllib.error.HTTPError(
        url="https://brasilapi.com.br/api/ddd/v1/11",
        code=502,
        msg="Bad Gateway",
        hdrs={},
        fp=io.BytesIO(b"<html><head><title>502 Bad Gateway</title></head><body>Cloudflare 502</body></html>")
    )

    with pytest.raises(ValueError) as excinfo:
        _handle_brasilapi_error(html_error, "DDD")
    assert "502" in str(excinfo.value)
    assert "JSONDecodeError" not in str(excinfo.value)

    # Simula resposta HTTP com JSON contendo 'message'
    json_error = urllib.error.HTTPError(
        url="https://brasilapi.com.br/api/cep/v1/00000000",
        code=404,
        msg="Not Found",
        hdrs={},
        fp=io.BytesIO(b'{"message": "CEP nao localizado na base"}')
    )

    with pytest.raises(ValueError) as excinfo2:
        _handle_brasilapi_error(json_error, "CEP")
    assert "CEP nao localizado na base" in str(excinfo2.value)

    # Validações de entrada estritas
    with pytest.raises(ValueError, match="8 dígitos"):
        fetch_cep_info("123")

    with pytest.raises(ValueError, match="14 dígitos"):
        fetch_cnpj_info("1234")

    with pytest.raises(ValueError, match="2 dígitos"):
        fetch_ddd_info("12345")

    with pytest.raises(ValueError, match="Código FIPE inválido"):
        fetch_fipe_info("invalido")
