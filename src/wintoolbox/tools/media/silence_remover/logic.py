"""
Lógica pura de remoção automática de trechos de silêncio em arquivos de áudio e vídeo via FFmpeg.
Utiliza o filtro acústico silenceremove para cortar pausas e silêncios prolongados.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Dict, Optional
from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_duration


def remove_silence_from_media(
    input_path: Path,
    output_path: Path,
    threshold_db: float = -35.0,
    min_silence_sec: float = 0.8,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Remove pausas mortas e silêncios contínuos do arquivo de áudio ou vídeo.
    threshold_db: volume em decibéis abaixo do qual é considerado silêncio (ex: -35dB ou -40dB).
    min_silence_sec: duração mínima em segundos de silêncio para disparar o corte.
    """
    input_path = Path(input_path).resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = get_ffmpeg_exe()

    # Filtro FFmpeg silenceremove
    # stop_periods=-1: continua varrendo e cortando todos os silêncios ao longo de todo o arquivo
    af_filter = (
        f"silenceremove=stop_periods=-1:stop_duration={min_silence_sec}:stop_threshold={threshold_db}dB"
    )

    is_audio_only = input_path.suffix.lower() in [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"]

    cmd = [ffmpeg, "-y", "-i", str(input_path)]

    if is_audio_only:
        cmd.extend(["-af", af_filter, str(output_path)])
    else:
        # Para vídeos, sincroniza o áudio filtrado mantendo a faixa de vídeo correspondente
        cmd.extend([
            "-af", af_filter,
            "-c:v", "copy",
            str(output_path),
        ])

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
        raise RuntimeError(f"Erro ao remover silêncios via FFmpeg: {res.stderr}")

    if progress_cb:
        progress_cb(100)

    return output_path
