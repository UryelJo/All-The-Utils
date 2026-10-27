"""
Testes unitários para a ferramenta Divisor de CUE Sheet (media.cue_splitter).
Valida parsing de arquivos CUE e fatiamento real de áudio com FFmpeg.
"""
import subprocess
import pytest
from pathlib import Path

from wintoolbox.tools.media.cue_splitter.logic import (
    find_audio_file,
    parse_cue_content,
    parse_cue_time,
    split_cue_audio,
)
from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_duration


def test_parse_cue_time():
    """Valida conversão precisa de timestamps MM:SS:FF."""
    # 00:00:00 -> 0.0s
    assert parse_cue_time("00:00:00") == 0.0

    # 01:30:00 -> 90.0s
    assert parse_cue_time("01:30:00") == 90.0

    # 03:45:30 -> 3*60 + 45 + 30/75 = 225.4s
    assert abs(parse_cue_time("03:45:30") - 225.4) < 1e-5

    with pytest.raises(ValueError):
        parse_cue_time("invalid_time")


def test_parse_cue_content():
    """Valida extração estruturada de metadados de álbum e faixas."""
    sample_cue = """
    PERFORMER "Banda Teste"
    TITLE "Álbum Demonstração"
    FILE "disco.wav" WAVE
      TRACK 01 AUDIO
        TITLE "Abertura"
        PERFORMER "Banda Teste"
        INDEX 01 00:00:00
      TRACK 02 AUDIO
        TITLE "Clímax"
        PERFORMER "Banda Teste"
        INDEX 01 02:00:00
      TRACK 03 AUDIO
        TITLE "Encerramento"
        PERFORMER "Banda Teste"
        INDEX 01 04:00:00
    """
    sheet = parse_cue_content(sample_cue)
    assert sheet.album_title == "Álbum Demonstração"
    assert sheet.album_performer == "Banda Teste"
    assert sheet.referenced_file == "disco.wav"
    assert len(sheet.tracks) == 3

    t1, t2, t3 = sheet.tracks
    assert t1.number == 1
    assert t1.title == "Abertura"
    assert t1.start_seconds == 0.0
    assert t1.end_seconds == 120.0

    assert t2.number == 2
    assert t2.start_seconds == 120.0
    assert t2.end_seconds == 240.0

    assert t3.number == 3
    assert t3.start_seconds == 240.0
    assert t3.end_seconds is None


def test_split_cue_audio_real(tmp_path: Path):
    """Testa divisão física real de um arquivo mestre de áudio em 3 faixas com FFmpeg."""
    ffmpeg = get_ffmpeg_exe()

    # Gera arquivo mestre de 6 segundos
    master_wav = tmp_path / "disco.wav"
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=6.0",
        "-ar", "44100",
        "-ac", "1",
        str(master_wav)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert res.returncode == 0
    assert master_wav.is_file()

    # Cria arquivo CUE correspondente
    cue_content = f"""
    PERFORMER "Artista Fictício"
    TITLE "Trilogia Musical"
    FILE "disco.wav" WAVE
      TRACK 01 AUDIO
        TITLE "Primeiro Movimento"
        INDEX 01 00:00:00
      TRACK 02 AUDIO
        TITLE "Segundo Movimento"
        INDEX 01 00:02:00
      TRACK 03 AUDIO
        TITLE "Terceiro Movimento"
        INDEX 01 00:04:00
    """
    cue_file = tmp_path / "album.cue"
    cue_file.write_text(cue_content, encoding="utf-8")

    out_dir = tmp_path / "faixas_extraidas"
    generated_tracks = split_cue_audio(
        cue_path=cue_file,
        audio_file=master_wav,
        output_dir=out_dir,
        filename_pattern="{track:02d} - {title}",
        output_format="wav"
    )

    assert len(generated_tracks) == 3
    for p in generated_tracks:
        assert p.is_file()
        assert p.stat().st_size > 0

    # Confere durações: Faixa 1 (~2s), Faixa 2 (~2s), Faixa 3 (~2s)
    dur1 = get_media_duration(generated_tracks[0])
    dur2 = get_media_duration(generated_tracks[1])
    dur3 = get_media_duration(generated_tracks[2])

    assert round(dur1, 1) == 2.0
    assert round(dur2, 1) == 2.0
    assert round(dur3, 1) == 2.0


def test_find_audio_file_heuristics(tmp_path: Path):
    """Valida resolução automática do arquivo de áudio associado ao CUE."""
    cue_file = tmp_path / "album.cue"
    cue_file.touch()

    # Se referenciar disco.wav mas no disco estiver disco.flac
    flac_file = tmp_path / "disco.flac"
    flac_file.touch()

    found = find_audio_file(cue_file, "disco.wav")
    assert found == flac_file
