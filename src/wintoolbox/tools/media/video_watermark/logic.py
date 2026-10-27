"""
Lógica pura para aplicação de marcas d'água (texto e imagem) em vídeos utilizando FFmpeg.
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_info


def get_position_coords(
    position: str,
    margin_x: int,
    margin_y: int,
    is_text: bool = False
) -> Tuple[str, str]:
    """
    Retorna as expressões de coordenadas (x, y) no formato do FFmpeg para a posição selecionada.
    """
    pos = position.lower().strip()

    if is_text:
        # Variáveis disponíveis no filtro drawtext do FFmpeg
        w_var = "w"
        h_var = "h"
        tw_var = "text_w"
        th_var = "text_h"

        positions = {
            "top_left": (f"{margin_x}", f"{margin_y}"),
            "top_right": (f"{w_var}-{tw_var}-{margin_x}", f"{margin_y}"),
            "bottom_left": (f"{margin_x}", f"{h_var}-{th_var}-{margin_y}"),
            "bottom_right": (f"{w_var}-{tw_var}-{margin_x}", f"{h_var}-{th_var}-{margin_y}"),
            "center": (f"({w_var}-{tw_var})/2", f"({h_var}-{th_var})/2"),
            "top_center": (f"({w_var}-{tw_var})/2", f"{margin_y}"),
            "bottom_center": (f"({w_var}-{tw_var})/2", f"{h_var}-{th_var}-{margin_y}"),
        }
    else:
        # Variáveis disponíveis no filtro overlay do FFmpeg
        mw_var = "main_w"
        mh_var = "main_h"
        ow_var = "overlay_w"
        oh_var = "overlay_h"

        positions = {
            "top_left": (f"{margin_x}", f"{margin_y}"),
            "top_right": (f"{mw_var}-{ow_var}-{margin_x}", f"{margin_y}"),
            "bottom_left": (f"{margin_x}", f"{mh_var}-{oh_var}-{margin_y}"),
            "bottom_right": (f"{mw_var}-{ow_var}-{margin_x}", f"{mh_var}-{oh_var}-{margin_y}"),
            "center": (f"({mw_var}-{ow_var})/2", f"({mh_var}-{oh_var})/2"),
            "top_center": (f"({mw_var}-{ow_var})/2", f"{margin_y}"),
            "bottom_center": (f"({mw_var}-{ow_var})/2", f"{mh_var}-{oh_var}-{margin_y}"),
        }

    return positions.get(pos, positions["bottom_right"])


def escape_drawtext_string(text: str) -> str:
    """Escapa caracteres reservados do filtro drawtext do FFmpeg."""
    # Escape de barras invertidas, dois pontos, aspas simples e porcentagens
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\''")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    return text


def apply_video_watermark(
    input_path: Path,
    output_path: Path,
    watermark_type: str = "text",
    text: str = "",
    image_path: Optional[Path] = None,
    position: str = "bottom_right",
    opacity: float = 0.8,
    font_size: int = 24,
    font_color: str = "white",
    margin_x: int = 20,
    margin_y: int = 20
) -> Path:
    """
    Aplica uma marca d'água de texto ou imagem sobre o vídeo de entrada.
    """
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()

    if not input_path.is_file():
        raise FileNotFoundError(f"Vídeo de entrada não encontrado: {input_path}")

    opacity = max(0.05, min(1.0, float(opacity)))
    ffmpeg = get_ffmpeg_exe()

    # Verifica se há fluxo de áudio no vídeo para copiar
    info = get_media_info(input_path)
    has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if watermark_type == "image":
        if not image_path:
            raise ValueError("O caminho da imagem de marca d'água é obrigatório.")
        image_path = Path(image_path).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"Imagem de marca d'água não encontrada: {image_path}")

        pos_x, pos_y = get_position_coords(position, margin_x, margin_y, is_text=False)
        filter_complex = (
            f"[1:v]format=rgba,colorchannelmixer=aa={opacity:.2f}[wm];"
            f"[0:v][wm]overlay={pos_x}:{pos_y}"
        )

        cmd = [
            ffmpeg, "-y",
            "-i", str(input_path),
            "-i", str(image_path),
            "-filter_complex", filter_complex,
            "-c:v", "libx264",
            "-crf", "22",
            "-preset", "fast",
        ]
    elif watermark_type == "text":
        if not text.strip():
            raise ValueError("O texto da marca d'água não pode ser vazio.")

        pos_x, pos_y = get_position_coords(position, margin_x, margin_y, is_text=True)
        safe_text = escape_drawtext_string(text)
        vf = (
            f"drawtext=text='{safe_text}':"
            f"fontsize={font_size}:"
            f"fontcolor={font_color}@{opacity:.2f}:"
            f"x={pos_x}:y={pos_y}"
        )

        cmd = [
            ffmpeg, "-y",
            "-i", str(input_path),
            "-vf", vf,
            "-c:v", "libx264",
            "-crf", "22",
            "-preset", "fast",
        ]
    else:
        raise ValueError(f"Tipo de marca d'água não suportado: {watermark_type}")

    if has_audio:
        cmd.extend(["-c:a", "copy"])

    cmd.append(str(output_path))

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

    if proc.returncode != 0:
        raise RuntimeError(f"Erro ao aplicar marca d'água no vídeo: {proc.stderr}")

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("Arquivo de saída não foi gerado ou está vazio.")

    return output_path
