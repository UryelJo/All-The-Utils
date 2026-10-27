"""
Testes unitários e de validação de efeito real para media.stream_manager.
"""
from pathlib import Path
import subprocess

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_info
from wintoolbox.tools.media.stream_manager.logic import (
    list_media_streams,
    remux_streams,
    extract_stream_to_file,
)


def _generate_test_multitrack_video(path: Path) -> None:
    ffmpeg = get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=1:size=320x240:rate=10",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=1",
        "-c:v", "libx264",
        "-c:a", "aac",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def test_stream_manager_remux_and_extract(tmp_path: Path):
    """Testa listagem, remux removendo faixa de áudio e extração de faixa individual."""
    vid_in = tmp_path / "video_multitrack.mp4"
    vid_out_video_only = tmp_path / "video_somente.mp4"
    audio_out = tmp_path / "audio_extraido.aac"

    _generate_test_multitrack_video(vid_in)

    # 1. Listagem de trilhas
    streams = list_media_streams(vid_in)
    assert len(streams) == 2
    types = [s["type"] for s in streams]
    assert "video" in types
    assert "audio" in types

    # Identifica índice de vídeo
    video_idx = [s["index"] for s in streams if s["type"] == "video"][0]
    audio_idx = [s["index"] for s in streams if s["type"] == "audio"][0]

    # 2. Remux: mantém apenas o vídeo
    res_remux = remux_streams(vid_in, vid_out_video_only, [video_idx])
    assert res_remux.is_file()

    # Validação física: o arquivo gerado não deve ter faixa de áudio
    info_remux = get_media_info(res_remux)
    assert len(info_remux.get("streams", [])) == 1
    assert info_remux["streams"][0]["codec_type"] == "video"

    # 3. Extração individual da trilha de áudio
    res_audio = extract_stream_to_file(vid_in, audio_out, audio_idx)
    assert res_audio.is_file()
    assert res_audio.stat().st_size > 0
