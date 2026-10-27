"""
Testes unitários e de validação de efeito real para media.compress_target.
"""
from pathlib import Path
import subprocess

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_info
from wintoolbox.tools.media.compress_target.logic import (
    calculate_target_bitrate_kbps,
    compress_to_target_size,
)


def _generate_test_video(path: Path) -> None:
    ffmpeg = get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=2:size=320x240:rate=10",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=2",
        "-c:v", "libx264",
        "-c:a", "aac",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def test_calculate_target_bitrate():
    # 25 MB para vídeo de 60 segundos com áudio a 128 kbps
    kbps = calculate_target_bitrate_kbps(
        target_mb=25.0,
        duration_seconds=60.0,
        audio_bitrate_kbps=128,
    )
    # 25 MB * 8 * 1024 * 1024 * 0.96 / 60 / 1000 ~= 3355 kbps - 128 = ~3227 kbps
    assert 3000 <= kbps <= 3500


def test_compress_to_target_size_real(tmp_path: Path):
    """Testa compressão de vídeo para atingir meta de tamanho com verificação física."""
    vid_in = tmp_path / "video_original.mp4"
    vid_out = tmp_path / "video_meta.mp4"

    _generate_test_video(vid_in)

    res = compress_to_target_size(
        input_path=vid_in,
        output_path=vid_out,
        target_mb=0.5,  # 500 KB
        audio_bitrate_kbps=64,
        two_pass=False,
    )

    assert res.is_file()
    assert res == vid_out

    # Validação do efeito real: tamanho físico menor que a meta
    size_mb = res.stat().st_size / (1024 * 1024)
    assert size_mb <= 0.65

    # Valida integridade do contêiner de vídeo gerado
    info = get_media_info(res)
    assert len(info.get("streams", [])) >= 1
