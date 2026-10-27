"""
Lógica pura do Gerenciador de Trilhas e Remux de Mídia (MKV/MP4).
Permite selecionar, extrair, reordenar e remover faixas de vídeo, áudio e legenda sem recodificação.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
import os
from pathlib import Path
import subprocess
from typing import Any, Callable, Dict, List, Optional
from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_info


def list_media_streams(file_path: Path) -> List[Dict[str, Any]]:
    """
    Lista todas as trilhas (streams) de um arquivo de mídia com metadados para seleção.
    """
    file_path = Path(file_path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    raw_info = get_media_info(file_path)
    streams = raw_info.get("streams", [])

    result: List[Dict[str, Any]] = []
    for s in streams:
        idx = s.get("index", 0)
        c_type = s.get("codec_type", "desconhecido")
        codec = s.get("codec_name", "")
        tags = s.get("tags", {})
        lang = tags.get("language", "und")
        title = tags.get("title", "")

        details = ""
        if c_type == "video":
            details = f"{s.get('width', 0)}x{s.get('height', 0)}"
        elif c_type == "audio":
            channels = s.get("channels", 2)
            sr = s.get("sample_rate", 44100)
            details = f"{channels} canais, {sr} Hz"
        elif c_type == "subtitle":
            details = "Legenda"

        result.append({
            "index": idx,
            "type": c_type,
            "codec": codec,
            "language": lang,
            "title": title,
            "details": details,
        })

    return result


def remux_streams(
    input_path: Path,
    output_path: Path,
    stream_indexes_to_keep: List[int],
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Gera um novo contêiner contendo apenas as trilhas especificadas, sem recodificar (-c copy).
    """
    input_path = Path(input_path).resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    if not stream_indexes_to_keep:
        raise ValueError("Selecione ao menos uma trilha para manter no remux.")

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = get_ffmpeg_exe()

    cmd = [ffmpeg, "-y", "-i", str(input_path)]
    for idx in stream_indexes_to_keep:
        cmd.extend(["-map", f"0:{idx}"])

    cmd.extend(["-c", "copy", str(output_path)])

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
        raise RuntimeError(f"Falha no remux de mídia: {res.stderr}")

    if progress_cb:
        progress_cb(100)

    return output_path


def extract_stream_to_file(
    input_path: Path,
    output_path: Path,
    stream_index: int,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Extrai uma única trilha de áudio ou legenda para um arquivo separado.
    """
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = get_ffmpeg_exe()

    cmd = [
        ffmpeg, "-y",
        "-i", str(input_path),
        "-map", f"0:{stream_index}",
        "-c", "copy",
        str(output_path),
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
        raise RuntimeError(f"Falha ao extrair trilha: {res.stderr}")

    if progress_cb:
        progress_cb(100)

    return output_path
