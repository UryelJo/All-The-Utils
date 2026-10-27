"""
Testes unitários para a ferramenta de alteração de velocidade de mídia (media.speed_changer).
Valida processamento real com FFmpeg e comportamento de filtros.
"""
import subprocess
import pytest
from pathlib import Path

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_duration
from wintoolbox.tools.media.speed_changer.logic import (
    build_atempo_filters,
    change_media_speed,
)


@pytest.fixture
def sample_audio_wav(tmp_path: Path) -> Path:
    """Gera um arquivo WAV real com tom de 440 Hz e exatamente 2.0 segundos de duração."""
    ffmpeg = get_ffmpeg_exe()
    out = tmp_path / "sample_2s.wav"
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=2.0",
        "-ar", "44100",
        "-ac", "1",
        str(out)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert res.returncode == 0
    assert out.is_file()
    return out


def test_build_atempo_filters():
    """Valida a construção determinística de filtros atempo encadeados."""
    # 1.0x -> neutro
    assert build_atempo_filters(1.0) == "atempo=1.0"

    # 1.5x -> único filtro dentro do intervalo 0.5..2.0
    assert "atempo=1.5" in build_atempo_filters(1.5)

    # 4.0x -> encadeia atempo=2.0,atempo=2.0
    chain_4x = build_atempo_filters(4.0)
    assert chain_4x == "atempo=2.0,atempo=2.0000"

    # 0.25x -> encadeia atempo=0.5,atempo=0.5
    chain_025x = build_atempo_filters(0.25)
    assert chain_025x == "atempo=0.5,atempo=0.5000"

    # Valor <= 0 deve falhar
    with pytest.raises(ValueError):
        build_atempo_filters(0.0)


def test_change_media_speed_real_acceleration(tmp_path: Path, sample_audio_wav: Path):
    """Testa acelerar áudio 2.0x (de 2.0s para ~1.0s) com preservação de pitch."""
    out_file = tmp_path / "audio_2x.wav"
    res = change_media_speed(sample_audio_wav, out_file, speed=2.0, preserve_pitch=True)
    assert res == out_file
    assert out_file.is_file()
    assert out_file.stat().st_size > 0

    duration = get_media_duration(out_file)
    # 2.0 segundos acelerados a 2.0x devem durar aproximadamente 1.0 segundo
    assert round(duration, 1) == 1.0


def test_change_media_speed_real_slowdown(tmp_path: Path, sample_audio_wav: Path):
    """Testa desacelerar áudio 0.5x (de 2.0s para ~4.0s) sem pitch (efeito vinil)."""
    out_file = tmp_path / "audio_half.wav"
    res = change_media_speed(sample_audio_wav, out_file, speed=0.5, preserve_pitch=False)
    assert res == out_file
    assert out_file.is_file()

    duration = get_media_duration(out_file)
    # 2.0 segundos a 0.5x devem durar aproximadamente 4.0 segundos
    assert round(duration, 1) == 4.0


def test_change_media_speed_invalid_inputs(tmp_path: Path, sample_audio_wav: Path):
    """Testa validação de erros para arquivos inexistentes ou parâmetros inválidos."""
    with pytest.raises(FileNotFoundError):
        change_media_speed(tmp_path / "inexistente.mp4", tmp_path / "out.mp4", speed=1.5)

    with pytest.raises(ValueError):
        change_media_speed(sample_audio_wav, tmp_path / "out.wav", speed=-1.0)
