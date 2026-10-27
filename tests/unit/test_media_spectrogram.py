"""
Testes unitários e de validação de efeito real para media.spectrogram.
"""
from pathlib import Path
import subprocess
from PIL import Image

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe
from wintoolbox.tools.media.spectrogram.logic import (
    generate_spectrogram,
    generate_waveform,
)


def _generate_sine_wav(path: Path) -> None:
    ffmpeg = get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=1",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def test_spectrogram_and_waveform_generation(tmp_path: Path):
    """Testa geração real de espectrograma e forma de onda acústica com verificação de imagem PIL."""
    audio_file = tmp_path / "tom_440.wav"
    spec_png = tmp_path / "espectrograma.png"
    wave_png = tmp_path / "forma_de_onda.png"

    _generate_sine_wav(audio_file)

    # 1. Espectrograma
    res_spec = generate_spectrogram(audio_file, spec_png, width=800, height=400, color_map="magma")
    assert res_spec.is_file()

    # Validação física com leitor PIL (com legenda legend=1, as bordas numéricas adicionam dimensões extras)
    with Image.open(res_spec) as img:
        assert img.format == "PNG"
        assert img.size[0] >= 800
        assert img.size[1] >= 400

    # 2. Forma de Onda
    res_wave = generate_waveform(audio_file, wave_png, width=600, height=200)
    assert res_wave.is_file()

    with Image.open(res_wave) as img:
        assert img.format == "PNG"
        assert img.size == (600, 200)
