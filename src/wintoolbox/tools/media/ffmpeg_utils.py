"""
Utilitários de suporte ao ffmpeg e ffprobe para o módulo de mídia do All the Utils.
Garante que binários locais do static-ffmpeg ou do sistema sejam encontrados automaticamente.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_ffmpeg_exe() -> str:
    """Retorna o caminho executável do ffmpeg disponível no sistema."""
    path = shutil.which("ffmpeg")
    if path:
        return path

    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        path = shutil.which("ffmpeg")
        if path:
            return path
    except Exception:
        pass

    raise RuntimeError("Executável 'ffmpeg' não encontrado no sistema nem via static-ffmpeg.")


def get_ffprobe_exe() -> str:
    """Retorna o caminho executável do ffprobe disponível no sistema."""
    path = shutil.which("ffprobe")
    if path:
        return path

    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        path = shutil.which("ffprobe")
        if path:
            return path
    except Exception:
        pass

    raise RuntimeError("Executável 'ffprobe' não encontrado no sistema nem via static-ffmpeg.")


def get_media_info(file_path: Path) -> Dict[str, Any]:
    """Obtém metadados detalhados de áudio/vídeo via ffprobe em JSON."""
    ffprobe = get_ffprobe_exe()
    file_path = Path(file_path).resolve()

    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path)
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

    if result.returncode != 0:
        raise RuntimeError(f"Erro ao obter informações de mídia: {result.stderr}")

    try:
        return json.loads(result.stdout)
    except Exception as e:
        raise ValueError(f"Falha ao interpretar saída do ffprobe: {e}")


def get_media_duration(file_path: Path) -> float:
    """Retorna a duração da mídia em segundos."""
    try:
        info = get_media_info(file_path)
        fmt = info.get("format", {})
        return float(fmt.get("duration", 0.0))
    except Exception:
        return 0.0
