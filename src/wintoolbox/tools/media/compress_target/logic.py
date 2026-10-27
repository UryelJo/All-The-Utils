"""
Lógica pura de compressão de vídeo para atingir meta exata de tamanho em Megabytes (MB).
Calcula matematicamente a taxa de bits ideal e executa compressão via FFmpeg em uma ou duas passadas.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Dict, Optional
from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_duration


def calculate_target_bitrate_kbps(
    target_mb: float,
    duration_seconds: float,
    audio_bitrate_kbps: int = 128,
) -> int:
    """
    Calcula o bitrate de vídeo necessário (em kbps) para atingir o tamanho final desejado.
    Aplica margem de segurança de 4% para overhead de contêiner MP4 (moov atom, etc).
    """
    if duration_seconds <= 0:
        return 1000

    target_bits = target_mb * 8 * 1024 * 1024 * 0.96
    total_target_bps = target_bits / duration_seconds
    audio_bps = audio_bitrate_kbps * 1000
    video_bps = total_target_bps - audio_bps

    # Limite mínimo razoável de 100 kbps
    video_kbps = int(max(100_000, video_bps) / 1000)
    return video_kbps


def compress_to_target_size(
    input_path: Path,
    output_path: Path,
    target_mb: float = 25.0,
    audio_bitrate_kbps: int = 128,
    two_pass: bool = False,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Comprime o vídeo com o FFmpeg para convergir no tamanho especificado em MB.
    """
    input_path = Path(input_path).resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    duration = get_media_duration(input_path)
    if duration <= 0:
        duration = 10.0  # Fallback caso não seja detectado

    video_kbps = calculate_target_bitrate_kbps(
        target_mb=target_mb,
        duration_seconds=duration,
        audio_bitrate_kbps=audio_bitrate_kbps,
    )

    ffmpeg = get_ffmpeg_exe()

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    if two_pass:
        pass_log = output_path.parent / f"ffmpeg2pass_{output_path.stem}"
        # Passada 1
        cmd_p1 = [
            ffmpeg, "-y", "-i", str(input_path),
            "-c:v", "libx264", "-b:v", f"{video_kbps}k",
            "-pass", "1", "-passlogfile", str(pass_log),
            "-an", "-f", "null", "NUL" if os.name == "nt" else "/dev/null",
        ]
        subprocess.run(cmd_p1, capture_output=True, startupinfo=startupinfo, check=True)

        if progress_cb:
            progress_cb(50)

        # Passada 2
        cmd_p2 = [
            ffmpeg, "-y", "-i", str(input_path),
            "-c:v", "libx264", "-b:v", f"{video_kbps}k",
            "-pass", "2", "-passlogfile", str(pass_log),
            "-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k",
            "-preset", "medium",
            str(output_path),
        ]
        subprocess.run(cmd_p2, capture_output=True, startupinfo=startupinfo, check=True)

        # Limpa logs da passada dupla
        for log_f in output_path.parent.glob(f"ffmpeg2pass_{output_path.stem}*"):
            try:
                log_f.unlink(missing_ok=True)
            except Exception:
                pass
    else:
        # Passada única rápida
        cmd = [
            ffmpeg, "-y", "-i", str(input_path),
            "-c:v", "libx264", "-b:v", f"{video_kbps}k",
            "-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k",
            "-preset", "faster",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, startupinfo=startupinfo, check=True)

    if progress_cb:
        progress_cb(100)

    return output_path
