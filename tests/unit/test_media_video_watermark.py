"""
Testes unitários para a ferramenta Marca d'Água em Vídeo (media.video_watermark).
Valida integração real de vídeo e imagem com FFmpeg.
"""
import subprocess
import pytest
from pathlib import Path
from PIL import Image

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_info
from wintoolbox.tools.media.video_watermark.logic import (
    apply_video_watermark,
    escape_drawtext_string,
    get_position_coords,
)


@pytest.fixture
def sample_video_mp4(tmp_path: Path) -> Path:
    """Gera um vídeo MP4 real de 1.0 segundo (320x240) usando gerador lavfi do FFmpeg."""
    ffmpeg = get_ffmpeg_exe()
    out = tmp_path / "sample_video.mp4"
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", "color=c=blue:s=320x240:d=1.0",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(out)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert res.returncode == 0
    assert out.is_file()
    return out


@pytest.fixture
def sample_logo_png(tmp_path: Path) -> Path:
    """Gera um logotipo PNG de 40x40 com canal alfa."""
    out = tmp_path / "logo.png"
    img = Image.new("RGBA", (40, 40), (255, 0, 0, 180))
    img.save(out)
    return out


def test_escape_drawtext_string():
    """Valida o escape de caracteres especiais do filtro drawtext."""
    raw = "Preço: 100% 'Teste'\\OK"
    escaped = escape_drawtext_string(raw)
    assert "\\:" in escaped
    assert "\\%" in escaped
    assert "\\\\" in escaped


def test_get_position_coords():
    """Valida a resolução de coordenadas para diferentes âncoras."""
    # Para texto
    x, y = get_position_coords("top_left", 10, 20, is_text=True)
    assert x == "10"
    assert y == "20"

    x, y = get_position_coords("bottom_right", 15, 25, is_text=True)
    assert "w-text_w-15" in x
    assert "h-text_h-25" in y

    # Para imagem
    x, y = get_position_coords("center", 0, 0, is_text=False)
    assert "(main_w-overlay_w)/2" in x
    assert "(main_h-overlay_h)/2" in y


def test_apply_video_watermark_text_real(tmp_path: Path, sample_video_mp4: Path):
    """Testa aplicação de texto sobre vídeo real com FFmpeg."""
    out_video = tmp_path / "out_text.mp4"
    res = apply_video_watermark(
        input_path=sample_video_mp4,
        output_path=out_video,
        watermark_type="text",
        text="Amostra Oficial",
        position="bottom_right",
        opacity=0.9,
        font_size=18
    )
    assert res == out_video
    assert out_video.is_file()
    assert out_video.stat().st_size > 0

    info = get_media_info(out_video)
    video_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    assert len(video_streams) == 1
    assert video_streams[0]["width"] == 320
    assert video_streams[0]["height"] == 240


def test_apply_video_watermark_image_real(tmp_path: Path, sample_video_mp4: Path, sample_logo_png: Path):
    """Testa aplicação de imagem PNG transparente sobre vídeo real com FFmpeg."""
    out_video = tmp_path / "out_img.mp4"
    res = apply_video_watermark(
        input_path=sample_video_mp4,
        output_path=out_video,
        watermark_type="image",
        image_path=sample_logo_png,
        position="top_right",
        opacity=0.75
    )
    assert res == out_video
    assert out_video.is_file()
    assert out_video.stat().st_size > 0

    info = get_media_info(out_video)
    video_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    assert len(video_streams) == 1


def test_apply_video_watermark_errors(tmp_path: Path, sample_video_mp4: Path):
    """Valida rejeição de entradas inválidas."""
    with pytest.raises(FileNotFoundError):
        apply_video_watermark(
            input_path=tmp_path / "inexistente.mp4",
            output_path=tmp_path / "out.mp4",
            watermark_type="text",
            text="Oi"
        )

    with pytest.raises(ValueError):
        apply_video_watermark(
            input_path=sample_video_mp4,
            output_path=tmp_path / "out.mp4",
            watermark_type="text",
            text="   "  # Vazio
        )

    with pytest.raises(FileNotFoundError):
        apply_video_watermark(
            input_path=sample_video_mp4,
            output_path=tmp_path / "out.mp4",
            watermark_type="image",
            image_path=tmp_path / "logo_inexistente.png"
        )
