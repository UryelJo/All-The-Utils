"""
Testes unitários e de integração para o módulo de Áudio, Vídeo e Mídia Local (Fase 5).
Validação rigorosa do efeito real: inspeção de codecs, amostragem em Hz,
dimensões de imagem, duração de áudio/vídeo e tags ID3.
"""
from pathlib import Path
import subprocess
import wave
from PIL import Image
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
    """Gera um pequeno vídeo de teste sintético de 2 segundos com áudio a 44100 Hz."""
    tmp_dir = tmp_path_factory.mktemp("media_test")
    out_video = tmp_dir / "sample_video.mp4"
    ffmpeg = get_ffmpeg_exe()

    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-ar", "44100",
        str(out_video)
    ]
    res = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )
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
    assert len(info["streams"]) == 2  # 1 vídeo + 1 áudio
    codecs = {s.get("codec_name") for s in info["streams"]}
    assert "h264" in codecs
    assert "aac" in codecs

    dur = get_media_duration(sample_media)
    assert dur == pytest.approx(2.0, abs=0.2)


def test_media_convert(sample_media: Path, tmp_path: Path):
    # 1. Converter para GIF com validação de dimensões e formato real
    out_gif = tmp_path / "teste.gif"
    convert_media_file(sample_media, out_gif, target_format="gif", gif_fps=10, gif_width=160)
    assert out_gif.is_file()
    with Image.open(out_gif) as im:
        assert im.format == "GIF"
        assert im.size == (160, 120)
        assert im.is_animated is True
        assert getattr(im, "n_frames", 0) > 1

    # 2. Extrair áudio MP3 com validação de stream, codec e sample rate
    out_mp3 = tmp_path / "teste_audio.mp3"
    convert_media_file(sample_media, out_mp3, target_format="mp3", extract_audio_only=True)
    assert out_mp3.is_file()
    
    mp3_info = get_media_info(out_mp3)
    audio_streams = [s for s in mp3_info.get("streams", []) if s.get("codec_type") == "audio"]
    assert len(audio_streams) == 1
    assert audio_streams[0]["codec_name"] == "mp3"
    assert int(audio_streams[0]["sample_rate"]) == 44100


def test_media_trim_and_merge(sample_media: Path, tmp_path: Path):
    # Cortar 1 segundo e comprovar duração real
    trimmed = tmp_path / "corte_1s.mp4"
    trim_media(sample_media, trimmed, start_time="00:00:00", end_time="00:00:01", reencode=False)
    assert trimmed.is_file()
    dur_trimmed = get_media_duration(trimmed)
    assert dur_trimmed == pytest.approx(1.0, abs=0.2)

    # Juntar duas partes de 1s e comprovar duração de ~2s
    merged = tmp_path / "juntado.mp4"
    merge_media_files([trimmed, trimmed], merged, reencode=False)
    assert merged.is_file()
    dur_merged = get_media_duration(merged)
    assert dur_merged == pytest.approx(2.0, abs=0.3)


def test_media_frame_extractor(sample_media: Path, tmp_path: Path):
    out_dir = tmp_path / "frames"
    frames = extract_video_frames(sample_media, out_dir, mode="interval", interval_sec=1.0)
    # Vídeo sintético de 2s com intervalo de 1s deve extrair exatamente 2 frames
    assert len(frames) == 2
    for f in frames:
        assert f.is_file()
        with Image.open(f) as img:
            assert img.format == "PNG"
            assert img.size == (160, 120)


def test_id3_editor(sample_media: Path, tmp_path: Path):
    mp3_file = tmp_path / "musica.mp3"
    convert_media_file(sample_media, mp3_file, target_format="mp3", extract_audio_only=True)

    tags = edit_mp3_tags(
        mp3_file,
        artist="Artista Teste",
        album="Album Teste",
        year="2026",
        genre="Instrumental"
    )
    assert tags["artist"] == "Artista Teste"
    assert tags["album"] == "Album Teste"
    assert tags["date"] == "2026"
    assert tags["genre"] == "Instrumental"

    read_tags = read_mp3_tags(mp3_file)
    assert read_tags["artist"] == "Artista Teste"
    assert read_tags["album"] == "Album Teste"
    assert read_tags["date"] == "2026"
    assert read_tags["genre"] == "Instrumental"


def test_format_duration():
    assert format_duration(0) == "00:00"
    assert format_duration(65000) == "01:05"
    assert format_duration(3665000) == "01:01:05"


def test_speech_tts_real_wav_inspection(tmp_path: Path):
    voices = get_available_voices()
    assert isinstance(voices, list)

    wav_out = tmp_path / "fala_teste.wav"
    save_speech_to_file("Teste de fala no Windows", wav_out, rate=150)
    assert wav_out.is_file()

    # Validação rigorosa com o módulo wave nativo (Black-Box Testing)
    with wave.open(str(wav_out), "rb") as w:
        channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        framerate = w.getframerate()
        nframes = w.getnframes()
        assert channels in (1, 2)
        assert sampwidth == 2  # PCM 16-bit
        assert framerate in (16000, 22050, 44100, 48000)
        assert nframes > 0


def test_media_convert_failure_scenario(tmp_path: Path):
    """Cenário de falha: arquivo inexistente deve levantar exceção sem mascaramento."""
    non_existent = tmp_path / "nao_existe.mp4"
    out_dst = tmp_path / "out.mp3"
    with pytest.raises(Exception):
        convert_media_file(non_existent, out_dst, target_format="mp3")
