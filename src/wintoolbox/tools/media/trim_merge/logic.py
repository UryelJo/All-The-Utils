"""
Lógica pura para corte e junção rápida de vídeos e áudios via ffmpeg.
"""
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe


def trim_media(
    src_path: Path,
    dst_path: Path,
    start_time: str,
    end_time: Optional[str] = None,
    reencode: bool = False
) -> Path:
    """
    Corta um trecho de vídeo ou áudio usando stream copy ou reencodagem.
    """
    src_path = Path(src_path).resolve()
    dst_path = Path(dst_path).resolve()
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {src_path}")

    ffmpeg = get_ffmpeg_exe()

    cmd = [ffmpeg, "-y", "-ss", str(start_time).strip()]
    if end_time and str(end_time).strip():
        cmd.extend(["-to", str(end_time).strip()])

    cmd.extend(["-i", str(src_path)])

    if reencode:
        cmd.extend(["-c:v", "libx264", "-crf", "22", "-c:a", "aac"])
    else:
        cmd.extend(["-c", "copy"])

    cmd.append(str(dst_path))

    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

    if res.returncode != 0:
        raise RuntimeError(f"Erro ao cortar mídia via ffmpeg: {res.stderr[-300:]}")

    if not dst_path.is_file() or dst_path.stat().st_size == 0:
        raise RuntimeError("O arquivo de corte gerado está vazio ou não foi gravado.")

    return dst_path


def merge_media_files(
    file_list: List[Path],
    dst_path: Path,
    reencode: bool = False
) -> Path:
    """
    Junta múltiplos arquivos de áudio/vídeo utilizando concat demuxer do ffmpeg.
    """
    if not file_list or len(file_list) < 2:
        raise ValueError("São necessários pelo menos 2 arquivos para realizar a junção.")

    dst_path = Path(dst_path).resolve()
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = get_ffmpeg_exe()

    # Cria arquivo temporário de lista para o concat demuxer
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f_list:
        list_file_path = Path(f_list.name)
        for p in file_list:
            resolved_str = str(Path(p).resolve()).replace("\\", "/")
            f_list.write(f"file '{resolved_str}'\n")

    try:
        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file_path)
        ]

        if reencode:
            cmd.extend(["-c:v", "libx264", "-c:a", "aac"])
        else:
            cmd.extend(["-c", "copy"])

        cmd.append(str(dst_path))

        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

        if res.returncode != 0:
            raise RuntimeError(f"Erro ao juntar mídias via ffmpeg: {res.stderr[-300:]}")

        if not dst_path.is_file() or dst_path.stat().st_size == 0:
            raise RuntimeError("O arquivo unificado gerado está vazio.")

        return dst_path
    finally:
        try:
            list_file_path.unlink(missing_ok=True)
        except Exception:
            pass
