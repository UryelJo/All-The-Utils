"""
Lógica pura para geração visual de espectrogramas e formas de onda (Waveforms) de áudio via FFmpeg.
Utiliza os filtros nativos showspectrumpic e showwavespic.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Dict, Optional
from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe


def generate_spectrogram(
    input_path: Path,
    output_png_path: Path,
    width: int = 1024,
    height: int = 512,
    color_map: str = "magma",  # magma, fire, channel, intensity, rainbow
    scale: str = "log",        # lin, sqrt, cbrt, log, 4thrt, 5thrt
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Gera uma imagem de espectrograma de frequências acústicas (Hz vs Tempo) em PNG.
    """
    input_path = Path(input_path).resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    output_png_path = Path(output_png_path).resolve()
    output_png_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = get_ffmpeg_exe()

    lavfi_filter = f"showspectrumpic=s={width}x{height}:color={color_map}:scale={scale}:legend=1"

    cmd = [
        ffmpeg, "-y",
        "-i", str(input_path),
        "-lavfi", lavfi_filter,
        str(output_png_path),
    ]

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        startupinfo=startupinfo,
        check=False,
    )

    if res.returncode != 0:
        raise RuntimeError(f"Erro ao gerar espectrograma: {res.stderr}")

    if progress_cb:
        progress_cb(100)

    return output_png_path


def generate_waveform(
    input_path: Path,
    output_png_path: Path,
    width: int = 1024,
    height: int = 300,
    color_hex: str = "0x0078D4",
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Gera uma imagem de forma de onda (Waveform de amplitude vs tempo) em PNG.
    """
    input_path = Path(input_path).resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    output_png_path = Path(output_png_path).resolve()
    output_png_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = get_ffmpeg_exe()

    lavfi_filter = f"showwavespic=s={width}x{height}:colors={color_hex}"

    cmd = [
        ffmpeg, "-y",
        "-i", str(input_path),
        "-lavfi", lavfi_filter,
        str(output_png_path),
    ]

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        startupinfo=startupinfo,
        check=False,
    )

    if res.returncode != 0:
        raise RuntimeError(f"Erro ao gerar forma de onda: {res.stderr}")

    if progress_cb:
        progress_cb(100)

    return output_png_path
