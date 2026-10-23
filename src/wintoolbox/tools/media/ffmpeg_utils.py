"""
Utilitários de suporte ao ffmpeg e ffprobe para o módulo de mídia do All the Utils.
Garante que binários locais do static-ffmpeg ou do sistema sejam encontrados automaticamente.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _bundled_binary(name: str) -> Optional[str]:
    """
    ffmpeg/ffprobe empacotados com o app (build.py --with-ffmpeg) ou colocados na pasta
    'ffmpeg' ao lado do executável. No .exe o static-ffmpeg não funciona: ele baixa os
    binários para dentro do site-packages, que não existe no pacote.
    """
    roots = []
    if hasattr(sys, "_MEIPASS"):
        roots.append(Path(getattr(sys, "_MEIPASS")))
    roots.append(Path(sys.executable).resolve().parent)
    for root in roots:
        for candidate in (root / "ffmpeg" / f"{name}.exe", root / f"{name}.exe"):
            if candidate.is_file():
                return str(candidate)
    return None


def get_ffmpeg_exe() -> str:
    """Retorna o caminho executável do ffmpeg disponível no sistema."""
    path = _bundled_binary("ffmpeg") or shutil.which("ffmpeg")
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
    path = _bundled_binary("ffprobe") or shutil.which("ffprobe")
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
