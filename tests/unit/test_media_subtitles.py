"""
Testes unitários rigorosos para o Editor e Conversor de Legendas (media.subtitles).
Validação de parsing SRT/VTT, ajuste de sincronismo (Time Shift), limpeza de tags HTML e roundtrip.
"""
from pathlib import Path
import pytest

from wintoolbox.tools.media.subtitles.logic import (
    generate_srt,
    generate_vtt,
    ms_to_srt_time,
    ms_to_vtt_time,
    parse_subtitles,
    shift_subtitles,
    strip_html_tags,
    time_to_ms,
)
from wintoolbox.tools.media.subtitles.tool import SubtitlesTool


def test_time_conversions():
    # 1h 23m 45s e 678ms
    ms = (1 * 3600 + 23 * 60 + 45) * 1000 + 678
    assert ms_to_srt_time(ms) == "01:23:45,678"
    assert ms_to_vtt_time(ms) == "01:23:45.678"
    assert time_to_ms("01:23:45,678") == ms
    assert time_to_ms("01:23:45.678") == ms


def test_strip_html_tags():
    raw = "<i>Olá</i>, <b>Mundo</b>! <font color='red'>Atenção</font>"
    assert strip_html_tags(raw) == "Olá, Mundo! Atenção"


def test_subtitles_parsing_and_shift(tmp_path: Path):
    srt_content = (
        "1\n"
        "00:00:01,000 --> 00:00:04,000\n"
        "Primeira fala da legenda.\n\n"
        "2\n"
        "00:00:05,500 --> 00:00:08,200\n"
        "Segunda fala da legenda.\n"
    )

    items = parse_subtitles(srt_content)
    assert len(items) == 2
    assert items[0]["index"] == 1
    assert items[0]["text"] == "Primeira fala da legenda."
    assert items[0]["start_ms"] == 1000
    assert items[0]["end_ms"] == 4000

    # Aplica time shift de +1500 ms (+1.5 segundos)
    shifted = shift_subtitles(items, 1500)
    assert shifted[0]["start_ms"] == 2500
    assert shifted[0]["end_ms"] == 5500

    # Gera VTT resultante
    vtt_text = generate_vtt(shifted)
    assert vtt_text.startswith("WEBVTT\n")
    assert "00:00:02.500 --> 00:00:05.500" in vtt_text
    assert "Primeira fala da legenda." in vtt_text


def test_subtitles_tool_ui(qtbot, tmp_path: Path):
    tool = SubtitlesTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Cria arquivo SRT temporário
    srt_file = tmp_path / "legendas.srt"
    srt_file.write_text("1\n00:00:01,000 --> 00:00:03,000\nTeste UI\n", encoding="utf-8")

    from wintoolbox.tools.media.subtitles.logic import load_subtitle_file
    view._items = load_subtitle_file(srt_file)
    view._render_table()
    assert len(view._items) == 1
    assert view.table.rowCount() == 1
    assert "Teste UI" in view.table.item(0, 3).text()
