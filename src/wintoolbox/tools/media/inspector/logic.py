"""
Lógica pura de inspeção aprofundada de arquivos multimídia (áudio, vídeo, contêineres).
Extrai metadados completos estilo MediaInfo via ffprobe em formato estruturado.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
from datetime import timedelta
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from wintoolbox.tools.media.ffmpeg_utils import get_media_info


def format_duration_timecode(seconds: float) -> str:
    """Converte segundos em formato legível HH:MM:SS.mmm."""
    if seconds <= 0:
        return "00:00:00"
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def inspect_media_file(file_path: Path) -> Dict[str, Any]:
    """
    Realiza a inspeção detalhada de um arquivo de mídia retornando categorias estruturadas:
    Geral, Trilhas de Vídeo, Trilhas de Áudio e Trilhas de Legenda.
    """
    file_path = Path(file_path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    raw_info = get_media_info(file_path)
    fmt = raw_info.get("format", {})
    streams = raw_info.get("streams", [])

    duration_sec = float(fmt.get("duration", 0.0))
    size_bytes = int(fmt.get("size", file_path.stat().st_size))
    bitrate = int(fmt.get("bit_rate", 0))

    general = {
        "file_name": file_path.name,
        "file_path": str(file_path),
        "format_name": fmt.get("format_name", "Desconhecido"),
        "format_long_name": fmt.get("format_long_name", ""),
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "duration_seconds": duration_sec,
        "duration_formatted": format_duration_timecode(duration_sec),
        "overall_bitrate_kbps": round(bitrate / 1000, 1) if bitrate else 0,
        "tags": fmt.get("tags", {}),
    }

    video_streams: List[Dict[str, Any]] = []
    audio_streams: List[Dict[str, Any]] = []
    subtitle_streams: List[Dict[str, Any]] = []

    for s in streams:
        codec_type = s.get("codec_type")
        idx = s.get("index", 0)
        codec_name = s.get("codec_name", "")
        codec_long_name = s.get("codec_long_name", "")

        if codec_type == "video":
            w = s.get("width", 0)
            h = s.get("height", 0)
            fps_str = s.get("r_frame_rate", "0/1")
            fps = 0.0
            try:
                num, den = fps_str.split("/")
                fps = round(float(num) / float(den), 2) if float(den) > 0 else 0.0
            except Exception:
                pass

            v_bitrate = int(s.get("bit_rate", 0)) if s.get("bit_rate") else 0
            video_streams.append({
                "index": idx,
                "codec": codec_name,
                "codec_long_name": codec_long_name,
                "profile": s.get("profile", ""),
                "width": w,
                "height": h,
                "resolution": f"{w}x{h}",
                "aspect_ratio": s.get("display_aspect_ratio", ""),
                "fps": fps,
                "pixel_format": s.get("pix_fmt", ""),
                "bitrate_kbps": round(v_bitrate / 1000, 1) if v_bitrate else 0,
                "tags": s.get("tags", {}),
            })

        elif codec_type == "audio":
            sample_rate = int(s.get("sample_rate", 0))
            channels = int(s.get("channels", 0))
            channel_layout = s.get("channel_layout", "")
            a_bitrate = int(s.get("bit_rate", 0)) if s.get("bit_rate") else 0
            tags = s.get("tags", {})
            lang = tags.get("language", "und")

            audio_streams.append({
                "index": idx,
                "codec": codec_name,
                "codec_long_name": codec_long_name,
                "channels": channels,
                "channel_layout": channel_layout,
                "sample_rate_hz": sample_rate,
                "bitrate_kbps": round(a_bitrate / 1000, 1) if a_bitrate else 0,
                "language": lang,
                "title": tags.get("title", ""),
            })

        elif codec_type == "subtitle":
            tags = s.get("tags", {})
            subtitle_streams.append({
                "index": idx,
                "codec": codec_name,
                "language": tags.get("language", "und"),
                "title": tags.get("title", ""),
            })

    return {
        "general": general,
        "video_streams": video_streams,
        "audio_streams": audio_streams,
        "subtitle_streams": subtitle_streams,
        "raw_json": raw_info,
    }


def generate_text_report(info: Dict[str, Any]) -> str:
    """Gera um relatório formatado em texto puro estilo MediaInfo."""
    gen = info.get("general", {})
    lines = [
        "============================================================",
        f" RELATÓRIO TÉCNICO DE MÍDIA — {gen.get('file_name', '')}",
        "============================================================",
        "",
        "[GERAL]",
        f"  Caminho: {gen.get('file_path', '')}",
        f"  Formato: {gen.get('format_name', '')} ({gen.get('format_long_name', '')})",
        f"  Tamanho: {gen.get('size_mb', 0)} MB ({gen.get('size_bytes', 0):,} bytes)",
        f"  Duração: {gen.get('duration_formatted', '')} ({gen.get('duration_seconds', 0):.2f} s)",
        f"  Bitrate Geral: {gen.get('overall_bitrate_kbps', 0)} kb/s",
        "",
    ]

    for v in info.get("video_streams", []):
        lines.extend([
            f"[VÍDEO #{v.get('index', 0)}]",
            f"  Codec: {v.get('codec', '').upper()} ({v.get('codec_long_name', '')})",
            f"  Perfil: {v.get('profile', 'N/A')}",
            f"  Resolução: {v.get('resolution', '')} (Aspect: {v.get('aspect_ratio', 'N/A')})",
            f"  Taxa de Quadros: {v.get('fps', 0)} fps",
            f"  Formato de Pixels: {v.get('pixel_format', '')}",
            f"  Bitrate: {v.get('bitrate_kbps', 0)} kb/s",
            "",
        ])

    for a in info.get("audio_streams", []):
        lines.extend([
            f"[ÁUDIO #{a.get('index', 0)}]",
            f"  Codec: {a.get('codec', '').upper()} ({a.get('codec_long_name', '')})",
            f"  Canais: {a.get('channels', 0)} canais ({a.get('channel_layout', '')})",
            f"  Amostragem: {a.get('sample_rate_hz', 0)} Hz",
            f"  Bitrate: {a.get('bitrate_kbps', 0)} kb/s",
            f"  Idioma: {a.get('language', 'und')}",
            "",
        ])

    for s in info.get("subtitle_streams", []):
        lines.extend([
            f"[LEGENDA #{s.get('index', 0)}]",
            f"  Codec: {s.get('codec', '').upper()}",
            f"  Idioma: {s.get('language', 'und')}",
            f"  Título: {s.get('title', 'N/A')}",
            "",
        ])

    return "\n".join(lines)
