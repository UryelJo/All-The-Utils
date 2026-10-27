"""
Testes unitários e de validação de efeito real para media.inspector.
"""
from pathlib import Path
import subprocess
import pytest

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe
from wintoolbox.tools.media.inspector.logic import (
    inspect_media_file,
    generate_text_report,
    format_duration_timecode,
)


def _generate_test_audio_wav(path: Path) -> None:
    ffmpeg = get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=1",
        "-c:a", "pcm_s16le",
        "-ar", "44100",
        "-ac", "2",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def test_inspect_media_file_real(tmp_path: Path):
    """Testa inspeção via ffprobe de um arquivo WAV gerado dinamicamente."""
    wav_path = tmp_path / "teste_audio.wav"
    _generate_test_audio_wav(wav_path)

    res = inspect_media_file(wav_path)

    gen = res["general"]
    assert gen["file_name"] == "teste_audio.wav"
    assert gen["duration_seconds"] > 0.9
    assert gen["size_bytes"] > 0

    # Validação rigorosa dos metadados de áudio extraídos
    audio_streams = res["audio_streams"]
    assert len(audio_streams) == 1
    a0 = audio_streams[0]
    assert a0["codec"] == "pcm_s16le"
    assert a0["sample_rate_hz"] == 44100
    assert a0["channels"] == 2

    # Testa relatório em texto formatado
    report = generate_text_report(res)
    assert "pcm_s16le" in report.lower()
    assert "44100" in report


def test_format_duration_timecode():
    assert format_duration_timecode(0.0) == "00:00:00"
    assert format_duration_timecode(3661.5) == "01:01:01.500"
