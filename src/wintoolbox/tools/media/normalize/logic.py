"""
Lógica pura da ferramenta Normalização de Volume em Lote (media.normalize).
Aplica o filtro EBU R128 (loudnorm) via FFmpeg preservando o sample rate e otimizando a saída.
"""
import json
import os
from pathlib import Path
import subprocess
from typing import Dict, List, Optional

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_ffprobe_exe

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v"}


def get_audio_sample_rate(src_path: Path, default: int = 44100) -> int:
    """
    Obtém a taxa de amostragem (sample rate) do áudio original usando ffprobe.
    Retorna o valor em Hz (ex: 44100, 48000) ou o default se não detectado.
    """
    ffprobe = get_ffprobe_exe()
    if not ffprobe:
        return default

    flags = 0x08000000 if os.name == "nt" else 0
    cmd = [
        ffprobe,
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate",
        "-of", "json",
        str(src_path),
    ]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags
        )
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            if streams and "sample_rate" in streams[0]:
                sr = int(streams[0]["sample_rate"])
                if 8000 <= sr <= 192000:
                    return sr
    except Exception:
        pass
    return default


def build_loudnorm_command(
    ffmpeg_exe: str,
    src_path: Path,
    dst_path: Path,
    target_lufs: float = -14.0,
    true_peak: float = -1.0,
    loudness_range: float = 11.0,
    sample_rate: int = 44100,
    is_video: bool = False,
) -> List[str]:
    """
    Monta a linha de comando otimizada do FFmpeg com loudnorm e trava de sample rate.
    """
    loudnorm_filter = f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={loudness_range}"

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", str(src_path),
        "-af", loudnorm_filter,
        "-ar", str(sample_rate),  # Impede que o loudnorm converta inadvertidamente para 192 kHz
    ]

    if is_video:
        # Preserva o vídeo original sem re-codificar para velocidade máxima
        cmd.extend(["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"])
    else:
        out_ext = dst_path.suffix.lower()
        if out_ext == ".mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k"])
        elif out_ext in (".m4a", ".aac"):
            cmd.extend(["-c:a", "aac", "-b:a", "256k"])
        elif out_ext == ".flac":
            cmd.extend(["-c:a", "flac"])
        elif out_ext == ".wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif out_ext == ".ogg":
            cmd.extend(["-c:a", "libvorbis", "-q:a", "6"])

    cmd.append(str(dst_path))
    return cmd


def normalize_audio_file(
    src_path: Path,
    dst_path: Path,
    target_lufs: float = -14.0,
    true_peak: float = -1.0,
    loudness_range: float = 11.0,
    output_format: str = "keep",
) -> Path:
    """
    Normaliza a sonoridade do arquivo de áudio ou vídeo para o padrão EBU R128 (loudnorm).
    Mantém o sample rate do arquivo de entrada para evitar inflação indevida de tamanho.
    """
    src_path = Path(src_path)
    dst_path = Path(dst_path)

    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {src_path}")

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = get_ffmpeg_exe()

    ext = src_path.suffix.lower()
    is_video = ext in VIDEO_EXTENSIONS

    # Ajuste de extensão no destino conforme o formato escolhido
    if output_format != "keep" and not is_video:
        dst_path = dst_path.with_suffix(f".{output_format.lstrip('.')}")

    # Detecta sample rate original para travar no ffmpeg
    sample_rate = get_audio_sample_rate(src_path, default=44100)

    cmd = build_loudnorm_command(
        ffmpeg_exe=ffmpeg,
        src_path=src_path,
        dst_path=dst_path,
        target_lufs=target_lufs,
        true_peak=true_peak,
        loudness_range=loudness_range,
        sample_rate=sample_rate,
        is_video=is_video,
    )

    flags = 0x08000000 if os.name == "nt" else 0
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags
    )

    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg falhou ao normalizar volume:\n{res.stderr[-500:]}")

    return dst_path
