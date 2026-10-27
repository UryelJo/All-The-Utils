"""
Testes unitários e de validação de efeito real para media.silence_remover.
"""
from pathlib import Path
import subprocess

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_duration
from wintoolbox.tools.media.silence_remover.logic import remove_silence_from_media


def _generate_audio_with_silence(path: Path) -> None:
    ffmpeg = get_ffmpeg_exe()
    # Concatena: 1s som + 2s silêncio + 1s som (total: 4s)
    cmd = [
        ffmpeg,
        "-y",
        "-f", "lavfi", "-i", "sine=frequency=800:duration=1",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo:d=2",
        "-f", "lavfi", "-i", "sine=frequency=800:duration=1",
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[outa]",
        "-map", "[outa]",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def test_remove_silence_real(tmp_path: Path):
    """Testa corte real de 2 segundos de silêncio e redução de duração."""
    audio_in = tmp_path / "audio_com_pausa.wav"
    audio_out = tmp_path / "audio_cortado.wav"

    _generate_audio_with_silence(audio_in)

    dur_original = get_media_duration(audio_in)
    assert 3.8 <= dur_original <= 4.2

    res = remove_silence_from_media(
        input_path=audio_in,
        output_path=audio_out,
        threshold_db=-30.0,
        min_silence_sec=0.5,
    )

    assert res.is_file()
    assert res == audio_out

    # Validação do efeito real: a duração do áudio foi reduzida significativamente
    dur_cortado = get_media_duration(res)
    assert dur_cortado < dur_original
    assert 1.8 <= dur_cortado <= 2.8
