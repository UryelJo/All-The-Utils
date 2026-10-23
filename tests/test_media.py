"""
Testes unitários e de integração para o módulo de Áudio, Vídeo e Mídia Local (Fase 5).
"""
import subprocess
from pathlib import Path
import pytest

from wintoolbox.tools.media.ffmpeg_utils import (
    get_ffmpeg_exe, get_ffprobe_exe, get_media_duration, get_media_info
)
from wintoolbox.tools.media.convert.logic import convert_media_file
from wintoolbox.tools.media.trim_merge.logic import merge_media_files, trim_media
from wintoolbox.tools.media.frame_extractor.logic import extract_video_frames
from wintoolbox.tools.media.id3_editor.logic import edit_mp3_tags, read_mp3_tags
from wintoolbox.tools.media.player.logic import format_duration
from wintoolbox.tools.media.speech.logic import get_available_voices, save_speech_to_file


@pytest.fixture(scope="module")
def sample_media(tmp_path_factory) -> Path:
    """Gera um pequeno vídeo de teste sintético de 2 segundos com áudio."""
    tmp_dir = tmp_path_factory.mktemp("media_test")
    out_video = tmp_dir / "sample_video.mp4"
    ffmpeg = get_ffmpeg_exe()

    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        str(out_video)
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert res.returncode == 0
    assert out_video.is_file()
    return out_video


def test_ffmpeg_paths_and_info(sample_media: Path):
    ffmpeg = get_ffmpeg_exe()
    ffprobe = get_ffprobe_exe()
    assert Path(ffmpeg).is_file()
    assert Path(ffprobe).is_file()

    info = get_media_info(sample_media)
    assert "streams" in info
    assert len(info["streams"]) >= 1

    dur = get_media_duration(sample_media)
    assert dur >= 1.5


def test_media_convert(sample_media: Path, tmp_path: Path):
    # 1. Converter para GIF
    out_gif = tmp_path / "teste.gif"
    convert_media_file(sample_media, out_gif, target_format="gif", gif_fps=10, gif_width=160)
    assert out_gif.is_file()
    assert out_gif.stat().st_size > 0

    # 2. Extrair áudio MP3
    out_mp3 = tmp_path / "teste_audio.mp3"
    convert_media_file(sample_media, out_mp3, target_format="mp3", extract_audio_only=True)
    assert out_mp3.is_file()
    assert out_mp3.stat().st_size > 0


def test_media_trim_and_merge(sample_media: Path, tmp_path: Path):
    # Cortar 1 segundo
    trimmed = tmp_path / "corte_1s.mp4"
    trim_media(sample_media, trimmed, start_time="00:00:00", end_time="00:00:01", reencode=False)
    assert trimmed.is_file()
    assert trimmed.stat().st_size > 0

    # Juntar duas partes
    merged = tmp_path / "juntado.mp4"
    merge_media_files([trimmed, trimmed], merged, reencode=False)
    assert merged.is_file()
    assert merged.stat().st_size > 0


def test_media_frame_extractor(sample_media: Path, tmp_path: Path):
    out_dir = tmp_path / "frames"
    frames = extract_video_frames(sample_media, out_dir, mode="interval", interval_sec=1.0)
    assert len(frames) >= 1
    for f in frames:
        assert f.is_file()


def test_id3_editor(sample_media: Path, tmp_path: Path):
    # Gera um MP3
    mp3_file = tmp_path / "musica.mp3"
    convert_media_file(sample_media, mp3_file, target_format="mp3", extract_audio_only=True)

    # Grava tags
    tags = edit_mp3_tags(
        mp3_file,
        artist="Artista Teste",
        album="Album Teste",
        year="2026",
        genre="Instrumental"
    )
    assert tags["artist"] == "Artista Teste"
    assert tags["album"] == "Album Teste"
    assert tags["genre"] == "Instrumental"

    # Lê tags
    read_tags = read_mp3_tags(mp3_file)
    assert read_tags["artist"] == "Artista Teste"


def test_format_duration():
    assert format_duration(0) == "00:00"
    assert format_duration(65000) == "01:05"
    assert format_duration(3665000) == "01:01:05"


def test_speech_tts(tmp_path: Path):
    voices = get_available_voices()
    assert isinstance(voices, list)

    wav_out = tmp_path / "fala_teste.wav"
    save_speech_to_file("Teste de fala no Windows", wav_out, rate=150)
    assert wav_out.is_file()
    assert wav_out.stat().st_size > 0
