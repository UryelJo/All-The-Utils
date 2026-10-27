"""
Lógica pura para geração de Folhas de Contato de Vídeo (Video Contact Sheet / Thumbnail Grid).
Captura frames sequenciais uniformes via FFmpeg e compõe uma grade gráfica profissional com Pillow.
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_info


def format_timecode(seconds: float) -> str:
    """Formata segundos em HH:MM:SS."""
    secs_int = int(round(seconds))
    hrs = secs_int // 3600
    mins = (secs_int % 3600) // 60
    secs = secs_int % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"


def extract_video_frame(ffmpeg_exe: str, video_path: Path, timestamp: float, output_img: Path) -> bool:
    """Extrai um único frame no timestamp indicado com FFmpeg."""
    cmd = [
        ffmpeg_exe, "-y",
        "-ss", f"{timestamp:.3f}",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_img)
    ]
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )
    return res.returncode == 0 and output_img.is_file() and output_img.stat().st_size > 0


def generate_contact_sheet(
    video_path: Path,
    output_path: Path,
    rows: int = 4,
    cols: int = 4,
    sheet_width: int = 1920,
    show_metadata: bool = True,
    show_timecode: bool = True
) -> Path:
    """
    Gera uma folha de contato completa para um arquivo de vídeo.
    """
    video_path = Path(video_path).resolve()
    output_path = Path(output_path).resolve()

    if not video_path.is_file():
        raise FileNotFoundError(f"Arquivo de vídeo não encontrado: {video_path}")

    if rows < 1 or cols < 1:
        raise ValueError("Linhas e colunas devem ser maiores ou iguais a 1.")

    info = get_media_info(video_path)
    fmt = info.get("format", {})
    duration = float(fmt.get("duration", 0.0))
    size_bytes = int(fmt.get("size", video_path.stat().st_size))
    size_mb = size_bytes / (1024 * 1024)

    # Identifica resolução do vídeo
    video_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    if not video_streams:
        raise ValueError("Nenhum fluxo de vídeo encontrado no arquivo.")

    v_stream = video_streams[0]
    vid_w = int(v_stream.get("width", 1920))
    vid_h = int(v_stream.get("height", 1080))
    v_codec = v_stream.get("codec_name", "desconhecido")

    audio_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    a_codec = audio_streams[0].get("codec_name", "nenhum") if audio_streams else "sem áudio"

    total_frames = rows * cols
    if duration <= 0:
        duration = 1.0

    # Instantes de amostragem uniformes
    timestamps: List[float] = [
        (duration / (total_frames + 1)) * (i + 1)
        for i in range(total_frames)
    ]

    margin = 6
    # Largura de cada miniatura
    thumb_w = (sheet_width - (cols + 1) * margin) // cols
    aspect = vid_h / vid_w if vid_w > 0 else 9 / 16
    thumb_h = max(10, int(thumb_w * aspect))

    header_height = 90 if show_metadata else margin
    sheet_height = header_height + (rows * thumb_h) + ((rows + 1) * margin)

    # Cria canvas base com fundo escuro
    canvas = Image.new("RGB", (sheet_width, sheet_height), color=(24, 24, 27))
    draw = ImageDraw.Draw(canvas)

    # Tenta obter uma fonte padrão legível
    font = ImageFont.load_default()

    # Desenha cabeçalho de metadados
    if show_metadata:
        header_text_1 = (
            f"Arquivo: {video_path.name}  |  Tamanho: {size_mb:.2f} MB  |  "
            f"Duração: {format_timecode(duration)} ({duration:.2f}s)"
        )
        header_text_2 = (
            f"Resolução: {vid_w}x{vid_h}  |  Vídeo: {v_codec}  |  Áudio: {a_codec}  |  "
            f"Grade: {cols}x{rows} ({total_frames} capturas)"
        )

        draw.text((margin * 2, margin * 2), header_text_1, fill=(240, 240, 240), font=font)
        draw.text((margin * 2, margin * 2 + 25), header_text_2, fill=(180, 180, 180), font=font)
        draw.line(
            [(margin, header_height - 2), (sheet_width - margin, header_height - 2)],
            fill=(60, 60, 65),
            width=1
        )

    ffmpeg = get_ffmpeg_exe()

    # Extrai os frames em pasta temporária e monta na grade
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        for idx, ts in enumerate(timestamps):
            r = idx // cols
            c = idx % cols

            pos_x = margin + c * (thumb_w + margin)
            pos_y = header_height + margin + r * (thumb_h + margin)

            frame_img_path = temp_dir_path / f"frame_{idx:03d}.jpg"
            success = extract_video_frame(ffmpeg, video_path, ts, frame_img_path)

            if success:
                try:
                    with Image.open(frame_img_path) as frame:
                        resized = frame.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                        canvas.paste(resized, (pos_x, pos_y))
                except Exception:
                    draw.rectangle([pos_x, pos_y, pos_x + thumb_w, pos_y + thumb_h], fill=(40, 40, 40))
            else:
                draw.rectangle([pos_x, pos_y, pos_x + thumb_w, pos_y + thumb_h], fill=(40, 40, 40))

            # Desenha timecode no canto inferior direito da miniatura
            if show_timecode:
                tc_str = format_timecode(ts)
                tc_w = len(tc_str) * 6 + 10
                tc_h = 16
                tc_box_x = pos_x + thumb_w - tc_w - 4
                tc_box_y = pos_y + thumb_h - tc_h - 4

                # Fundo translúcido escuro
                draw.rectangle(
                    [tc_box_x, tc_box_y, tc_box_x + tc_w, tc_box_y + tc_h],
                    fill=(0, 0, 0)
                )
                draw.text(
                    (tc_box_x + 5, tc_box_y + 2),
                    tc_str,
                    fill=(255, 255, 255),
                    font=font
                )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=92)

    return output_path
