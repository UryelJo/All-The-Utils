"""
Testes unitários para a ferramenta Folha de Contato de Vídeo (media.contact_sheet).
Valida extração física de frames com FFmpeg e composição determinística com Pillow.
"""
import subprocess
import pytest
from pathlib import Path
from PIL import Image

from wintoolbox.tools.media.contact_sheet.logic import (
    format_timecode,
    generate_contact_sheet,
)
from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe


@pytest.fixture
def sample_video_3s(tmp_path: Path) -> Path:
    """Gera um vídeo MP4 real de 3.0 segundos (320x240) com FFmpeg lavfi."""
    ffmpeg = get_ffmpeg_exe()
    out = tmp_path / "video_3s.mp4"
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=3.0:size=320x240:rate=10",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(out)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert res.returncode == 0
    assert out.is_file()
    return out


def test_format_timecode():
    """Valida formatação precisa de timecode."""
    assert format_timecode(0.0) == "00:00:00"
    assert format_timecode(65.0) == "00:01:05"
    assert format_timecode(3661.0) == "01:01:01"


def test_generate_contact_sheet_real(tmp_path: Path, sample_video_3s: Path):
    """Testa geração de folha de contato 2x2 com leitura real do JPEG resultante."""
    out_sheet = tmp_path / "contact_sheet.jpg"
    res = generate_contact_sheet(
        video_path=sample_video_3s,
        output_path=out_sheet,
        rows=2,
        cols=2,
        sheet_width=640,
        show_metadata=True,
        show_timecode=True
    )

    assert res == out_sheet
    assert out_sheet.is_file()
    assert out_sheet.stat().st_size > 0

    # Validação Black-Box com leitor real de imagem (Pillow)
    with Image.open(out_sheet) as img:
        assert img.format in ["JPEG", "MPO"]
        # Largura deve coincidir exatamente com a informada
        assert img.size[0] == 640
        # Altura deve conter cabeçalho + as duas linhas de miniaturas
        assert img.size[1] > 200


def test_generate_contact_sheet_errors(tmp_path: Path, sample_video_3s: Path):
    """Valida tratamento de erros para caminhos inexistentes ou parâmetros inválidos."""
    with pytest.raises(FileNotFoundError):
        generate_contact_sheet(
            video_path=tmp_path / "inexistente.mp4",
            output_path=tmp_path / "out.jpg"
        )

    with pytest.raises(ValueError):
        generate_contact_sheet(
            video_path=sample_video_3s,
            output_path=tmp_path / "out.jpg",
            rows=0,
            cols=2
        )
