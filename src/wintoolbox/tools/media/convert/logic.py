"""
Lógica pura para conversão universal, extração de áudio e compressão de mídia via FFmpeg.
Suporta 50 formatos de entrada (incluindo MOV/HEVC/M4V/CAF de iPhone, AVCHD MTS/M2TS, VOB, MXF,
OPUS, AIFF, AC3), 26 formatos de saída, seleção de codecs modernos (H.264, H.265/HEVC com tag Apple hvc1,
AV1, VP9, ProRes, Stream Copy), WebP/GIF animados e aceleração por GPU (NVENC, AMF, QSV) com fallback CPU.
"""
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from wintoolbox.core.hardware import get_ffmpeg_video_encoder_params
from wintoolbox.tools.media.ffmpeg_utils import (
    get_ffmpeg_exe,
    get_media_duration,
)

# 50 extensões de vídeo e áudio aceitas na entrada
SUPPORTED_VIDEO_INPUTS: List[str] = [
    ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".flv", ".f4v", ".wmv", ".asf",
    ".ts", ".mts", ".m2ts", ".mpg", ".mpeg", ".mpe", ".mpv", ".m2v", ".vob",
    ".3gp", ".3g2", ".ogv", ".divx", ".dv", ".mxf", ".rm", ".rmvb",
]

SUPPORTED_AUDIO_INPUTS: List[str] = [
    ".mp3", ".wav", ".aac", ".flac", ".ogg", ".oga", ".opus",
    ".m4a", ".m4b", ".m4r", ".wma", ".aiff", ".aif", ".caf",
    ".ac3", ".eac3", ".dts", ".amr", ".ape", ".wv", ".mp2", ".weba", ".alac",
]

SUPPORTED_MEDIA_INPUTS: List[str] = SUPPORTED_VIDEO_INPUTS + SUPPORTED_AUDIO_INPUTS

VIDEO_FORMATS: List[str] = [
    "mp4", "mkv", "mov", "webm", "avi", "wmv", "ts",
    "flv", "m4v", "mpg", "3gp", "ogv", "gif", "webp",
]

AUDIO_FORMATS: List[str] = [
    "mp3", "m4a", "aac", "opus", "ogg", "flac",
    "wav", "aiff", "ac3", "wma", "caf", "mp2",
]

ALL_OUTPUT_FORMATS: List[str] = VIDEO_FORMATS + AUDIO_FORMATS
ANIMATED_FORMATS = {"gif", "webp"}

# Contêineres onde múltiplos codecs de vídeo podem ser escolhidos livremente pelo usuário
FLEXIBLE_CODEC_CONTAINERS = {"mp4", "mkv", "mov", "m4v", "ts"}

VALID_AUDIO_BITRATES = {"96k", "128k", "160k", "192k", "256k", "320k"}


def _normalize_audio_bitrate(bitrate: str) -> str:
    b = (bitrate or "192k").strip().lower()
    if not b.endswith("k"):
        b = f"{b}k"
    return b if b in VALID_AUDIO_BITRATES else "192k"


def _build_audio_encoder_args(target_format: str, audio_bitrate: str = "192k") -> List[str]:
    """Retorna os parâmetros de codec de áudio ideais para um formato de áudio dedicado."""
    ab = _normalize_audio_bitrate(audio_bitrate)
    if target_format == "mp3":
        return ["-c:a", "libmp3lame", "-b:a", ab]
    if target_format in ("aac", "m4a"):
        return ["-c:a", "aac", "-b:a", ab]
    if target_format == "opus":
        return ["-c:a", "libopus", "-b:a", ab]
    if target_format == "ogg":
        return ["-c:a", "libvorbis", "-b:a", ab]
    if target_format == "flac":
        return ["-c:a", "flac"]
    if target_format == "wav":
        return ["-c:a", "pcm_s16le"]
    if target_format == "aiff":
        return ["-c:a", "pcm_s16be"]
    if target_format == "ac3":
        return ["-c:a", "ac3", "-b:a", ab]
    if target_format == "wma":
        return ["-c:a", "wmav2", "-b:a", ab]
    if target_format == "caf":
        return ["-c:a", "alac"]
    if target_format == "mp2":
        return ["-c:a", "mp2", "-b:a", ab]
    return ["-c:a", "aac", "-b:a", ab]


def _build_video_scale_filter(max_height: int, require_even_dims: bool = True) -> Optional[str]:
    """Gera filtro de escala preservando proporção e garantindo dimensões pares para YUV420P."""
    if max_height and max_height > 0:
        even_h = (int(max_height) // 2) * 2
        return f"scale=-2:'min({even_h},trunc(ih/2)*2)':flags=lanczos"
    if require_even_dims:
        return "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    return None


def _resolve_video_codec_for_container(target_format: str, requested_codec: str) -> str:
    """Resolve o codec efetivo respeitando as restrições técnicas de cada contêiner."""
    req = (requested_codec or "auto").strip().lower()
    if req == "copy":
        return "copy"

    if target_format == "webm":
        return req if req in ("vp9", "av1") else "vp9"
    if target_format == "avi":
        return "mpeg4"
    if target_format == "wmv":
        return "wmv2"
    if target_format == "mpg":
        return "mpeg2"
    if target_format == "ogv":
        return "theora"
    if target_format == "3gp":
        return "h264"
    if target_format == "flv":
        return "h264"

    # Para mp4, mkv, mov, m4v, ts
    if req in ("h264", "h265", "hevc", "av1", "vp9", "prores", "mpeg4"):
        if req == "prores" and target_format not in ("mov", "mkv"):
            return "h264"
        if req == "vp9" and target_format not in ("mkv", "webm", "mp4"):
            return "h264"
        return "h265" if req == "hevc" else req
    return "h264"


def convert_media_file(
    src_path: Path,
    dst_path: Path,
    target_format: str = "mp4",
    extract_audio_only: bool = False,
    target_size_mb: Optional[float] = None,
    gif_fps: int = 15,
    gif_width: int = 480,
    hw_accel: str = "auto",
    video_codec: str = "auto",
    max_height: int = 0,
    audio_bitrate: str = "192k",
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
    target_format = target_format.strip().lower().lstrip(".")
    if target_format not in ALL_OUTPUT_FORMATS:
        raise ValueError(f"Formato de saída de mídia não suportado: '{target_format}'")

    ab = _normalize_audio_bitrate(audio_bitrate)

    def _build_cmd(use_hw: str) -> List[str]:
        cmd = [ffmpeg, "-y", "-i", str(src_path)]

        # 1. Modo Vídeo para GIF Animado
        if target_format == "gif":
            fps = max(1, min(60, int(gif_fps)))
            width = max(64, int(gif_width))
            filter_str = (
                f"fps={fps},scale={width}:-1:flags=lanczos,"
                "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
            )
            cmd.extend(["-vf", filter_str, "-loop", "0", str(dst_path)])
            return cmd

        # 2. Modo Vídeo para WebP Animado (16M cores, muito mais leve que GIF)
        if target_format == "webp":
            fps = max(1, min(60, int(gif_fps)))
            width = (max(64, int(gif_width)) // 2) * 2
            filter_str = f"fps={fps},scale={width}:-2:flags=lanczos"
            cmd.extend([
                "-vf", filter_str,
                "-c:v", "libwebp_anim",
                "-loop", "0",
                "-an",
                "-q:v", "75",
                str(dst_path),
            ])
            return cmd

        # 3. Modo Apenas Áudio
        if extract_audio_only or target_format in AUDIO_FORMATS:
            cmd.append("-vn")
            cmd.extend(_build_audio_encoder_args(target_format, ab))
            cmd.append(str(dst_path))
            return cmd

        eff_codec = _resolve_video_codec_for_container(target_format, video_codec)

        # 4. Modo Remux Rápido (Stream Copy sem recodificar)
        if eff_codec == "copy" and not (target_size_mb and target_size_mb > 0) and not max_height:
            cmd.extend(["-c:v", "copy", "-c:a", "copy"])
            if target_format in ("mp4", "mov", "m4v"):
                cmd.extend(["-movflags", "+faststart"])
            cmd.append(str(dst_path))
            return cmd

        # 5. Modo Vídeo com compressão por meta de tamanho (MB)
        if target_size_mb and target_size_mb > 0:
            duration = get_media_duration(src_path)
            scale_vf = _build_video_scale_filter(max_height, require_even_dims=True)
            if scale_vf:
                cmd.extend(["-vf", scale_vf])

            codec_family = "h265" if eff_codec == "h265" else "h264"
            if duration > 0:
                audio_kbit = 128
                total_kbit = (target_size_mb * 8192) / duration
                video_kbit = max(50, int(total_kbit - audio_kbit))

                _, enc_args = get_ffmpeg_video_encoder_params(codec_family, mode=use_hw, crf_quality=24)
                cmd.extend(enc_args)
                if codec_family == "h265" and target_format in ("mp4", "mov", "m4v"):
                    cmd.extend(["-tag:v", "hvc1"])
                cmd.extend([
                    "-pix_fmt", "yuv420p",
                    "-b:v", f"{video_kbit}k",
                    "-c:a", "aac",
                    "-b:a", f"{audio_kbit}k",
                ])
            else:
                _, enc_args = get_ffmpeg_video_encoder_params(codec_family, mode=use_hw, crf_quality=28)
                cmd.extend(enc_args)
                cmd.extend(["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k"])

            if target_format in ("mp4", "mov", "m4v"):
                cmd.extend(["-movflags", "+faststart"])
            cmd.append(str(dst_path))
            return cmd

        # 6. Modo Vídeo Padrão com Seleção de Contêiner e Codec
        require_even = eff_codec != "prores"
        scale_vf = _build_video_scale_filter(max_height, require_even_dims=require_even)
        if scale_vf:
            cmd.extend(["-vf", scale_vf])

        if eff_codec in ("h264", "h265"):
            crf = 24 if eff_codec == "h265" else 22
            _, enc_args = get_ffmpeg_video_encoder_params(eff_codec, mode=use_hw, crf_quality=crf)
            cmd.extend(enc_args)
            cmd.extend(["-pix_fmt", "yuv420p"])
            if eff_codec == "h265" and target_format in ("mp4", "mov", "m4v"):
                # Tag hvc1 garante reprodução nativa no iPhone, iPad, macOS QuickTime e Windows
                cmd.extend(["-tag:v", "hvc1"])
            if target_format == "3gp":
                cmd.extend(["-c:a", "aac", "-ar", "44100", "-ac", "1", "-b:a", "96k"])
            else:
                cmd.extend(["-c:a", "aac", "-b:a", ab])

        elif eff_codec == "av1":
            cmd.extend([
                "-c:v", "libaom-av1", "-crf", "32", "-b:v", "0",
                "-cpu-used", "6", "-row-mt", "1", "-pix_fmt", "yuv420p",
            ])
            audio_c = ["-c:a", "libopus", "-b:a", ab] if target_format in ("webm", "mkv") else ["-c:a", "aac", "-b:a", ab]
            cmd.extend(audio_c)

        elif eff_codec == "vp9":
            cmd.extend([
                "-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0",
                "-row-mt", "1", "-pix_fmt", "yuv420p",
            ])
            audio_c = ["-c:a", "libopus", "-b:a", ab] if target_format in ("webm", "mkv") else ["-c:a", "aac", "-b:a", ab]
            cmd.extend(audio_c)

        elif eff_codec == "prores":
            cmd.extend(["-c:v", "prores_ks", "-profile:v", "2", "-c:a", "pcm_s16le"])

        elif eff_codec == "mpeg4":
            cmd.extend(["-c:v", "mpeg4", "-q:v", "4", "-pix_fmt", "yuv420p"])
            if target_format == "avi":
                cmd.extend(["-c:a", "libmp3lame", "-b:a", ab])
            else:
                cmd.extend(["-c:a", "aac", "-b:a", ab])

        elif eff_codec == "wmv2":
            cmd.extend(["-c:v", "wmv2", "-q:v", "4", "-pix_fmt", "yuv420p", "-c:a", "wmav2", "-b:a", ab])

        elif eff_codec == "mpeg2":
            cmd.extend(["-c:v", "mpeg2video", "-q:v", "4", "-pix_fmt", "yuv420p", "-c:a", "mp2", "-b:a", ab])

        elif eff_codec == "theora":
            cmd.extend(["-c:v", "libtheora", "-q:v", "7", "-pix_fmt", "yuv420p", "-c:a", "libvorbis", "-b:a", ab])

        if target_format in ("mp4", "mov", "m4v"):
            cmd.extend(["-movflags", "+faststart"])

        cmd.append(str(dst_path))
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
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    if res.returncode != 0:
        raise RuntimeError(f"Erro na conversão ffmpeg: {res.stderr[-350:]}")

    if not dst_path.is_file() or dst_path.stat().st_size == 0:
        raise RuntimeError("O ffmpeg finalizou mas o arquivo de saída não foi gerado ou está vazio.")

    return dst_path
