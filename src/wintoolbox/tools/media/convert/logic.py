"""
Lógica pura para conversão, extração de áudio e compressão de mídia via ffmpeg.
Suporta aceleração por hardware por GPU (NVIDIA NVENC, AMD AMF, Intel QSV) com fallback para CPU.
"""
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from wintoolbox.core.hardware import get_ffmpeg_video_encoder_params
from wintoolbox.tools.media.ffmpeg_utils import (
    get_ffmpeg_exe, get_media_duration
)

AUDIO_FORMATS = ["mp3", "wav", "aac", "flac", "ogg", "m4a"]
VIDEO_FORMATS = ["mp4", "mkv", "webm", "avi", "mov", "gif"]
ALL_OUTPUT_FORMATS = VIDEO_FORMATS + AUDIO_FORMATS


def convert_media_file(
    src_path: Path,
    dst_path: Path,
    target_format: str = "mp4",
    extract_audio_only: bool = False,
    target_size_mb: Optional[float] = None,
    gif_fps: int = 15,
    gif_width: int = 480,
    hw_accel: str = "auto",
) -> Path:
    """
    Executa a conversão de vídeo/áudio utilizando o executável ffmpeg
    com suporte a aceleração por hardware (GPU) e fallback automático para CPU.
    """
    src_path = Path(src_path).resolve()
    dst_path = Path(dst_path).resolve()
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo de origem não encontrado: {src_path}")

    ffmpeg = get_ffmpeg_exe()
    target_format = target_format.lower().replace(".", "")

    def _build_cmd(use_hw: str) -> List[str]:
        cmd = [ffmpeg, "-y", "-i", str(src_path)]

        # 1. Modo Vídeo para GIF
        if target_format == "gif":
            filter_str = f"fps={gif_fps},scale={gif_width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
            cmd.extend(["-vf", filter_str, str(dst_path)])

        # 2. Modo Apenas Áudio
        elif extract_audio_only or target_format in AUDIO_FORMATS:
            cmd.extend(["-vn"])
            if target_format == "mp3":
                cmd.extend(["-c:a", "libmp3lame", "-q:a", "2"])
            elif target_format in ("aac", "m4a"):
                cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            elif target_format == "flac":
                cmd.extend(["-c:a", "flac"])
            elif target_format == "wav":
                cmd.extend(["-c:a", "pcm_s16le"])
            cmd.append(str(dst_path))

        # 3. Modo Vídeo com compressão por meta de tamanho (MB)
        elif target_size_mb and target_size_mb > 0:
            duration = get_media_duration(src_path)
            if duration > 0:
                audio_kbit = 128
                total_kbit = (target_size_mb * 8192) / duration
                video_kbit = max(50, int(total_kbit - audio_kbit))

                _, enc_args = get_ffmpeg_video_encoder_params("h264", mode=use_hw, crf_quality=24)
                cmd.extend(enc_args)
                cmd.extend([
                    "-b:v", f"{video_kbit}k",
                    "-c:a", "aac",
                    "-b:a", f"{audio_kbit}k",
                    str(dst_path)
                ])
            else:
                _, enc_args = get_ffmpeg_video_encoder_params("h264", mode=use_hw, crf_quality=28)
                cmd.extend(enc_args)
                cmd.extend(["-c:a", "aac", str(dst_path)])

        # 4. Modo Vídeo Padrão
        else:
            if target_format in ("mp4", "mkv"):
                _, enc_args = get_ffmpeg_video_encoder_params("h264", mode=use_hw, crf_quality=22)
                cmd.extend(enc_args)
                cmd.extend(["-c:a", "aac", "-b:a", "192k", str(dst_path)])
            elif target_format == "webm":
                cmd.extend(["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-c:a", "libopus", str(dst_path)])
            else:
                cmd.extend(["-c:v", "copy", "-c:a", "copy", str(dst_path)])

        return cmd

    # Tentativa com aceleração selecionada
    cmd = _build_cmd(hw_accel)
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

    # Se falhou e estávamos usando aceleração por GPU, tenta fallback para CPU
    if res.returncode != 0 and hw_accel != "cpu":
        cmd_cpu = _build_cmd("cpu")
        res = subprocess.run(
            cmd_cpu,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

    if res.returncode != 0:
        raise RuntimeError(f"Erro na conversão ffmpeg: {res.stderr[-300:]}")

    if not dst_path.is_file() or dst_path.stat().st_size == 0:
        raise RuntimeError("O ffmpeg finalizou mas o arquivo de saída não foi gerado ou está vazio.")

    return dst_path
