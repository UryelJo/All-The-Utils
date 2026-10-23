"""
Lógica pura para extração de quadros e miniaturas de vídeo via ffmpeg.
"""
import subprocess
from pathlib import Path
from typing import List

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe


def extract_video_frames(
    video_path: Path,
    output_dir: Path,
    mode: str = "interval",
    interval_sec: float = 5.0,
    timestamp: str = "00:00:01",
    img_format: str = "png",
    prefix: str = ""
) -> List[Path]:
    """
    Extrai quadros ou gera mosaicos de um arquivo de vídeo via ffmpeg.
    """
    video_path = Path(video_path).resolve()
    if not video_path.is_file():
        raise FileNotFoundError(f"Vídeo não encontrado: {video_path}")

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg = get_ffmpeg_exe()
    ext = img_format.lower().replace(".", "")
    if not prefix:
        prefix = video_path.stem

    generated_frames: List[Path] = []

    if mode == "single":
        out_file = output_dir / f"{prefix}_frame_fixo.{ext}"
        cmd = [
            ffmpeg, "-y",
            "-ss", str(timestamp).strip(),
            "-i", str(video_path),
            "-vframes", "1",
            str(out_file)
        ]
        _run_cmd(cmd)
        if out_file.is_file():
            generated_frames.append(out_file)

    elif mode == "tile":
        out_file = output_dir / f"{prefix}_mosaico_3x3.{ext}"
        # Grade 3x3 com 9 miniaturas
        cmd = [
            ffmpeg, "-y",
            "-i", str(video_path),
            "-vf", r"select=not(mod(n\,60)),scale=320:-1,tile=3x3",
            "-frames:v", "1",
            str(out_file)
        ]
        _run_cmd(cmd)
        if out_file.is_file():
            generated_frames.append(out_file)

    else:  # interval
        pattern = output_dir / f"{prefix}_frame_%04d.{ext}"
        fps_expr = f"fps=1/{max(0.1, interval_sec)}"
        cmd = [
            ffmpeg, "-y",
            "-i", str(video_path),
            "-vf", fps_expr,
            str(pattern)
        ]
        _run_cmd(cmd)
        generated_frames = sorted(list(output_dir.glob(f"{prefix}_frame_*.{ext}")))

    return generated_frames


def _run_cmd(cmd: List[str]) -> None:
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
        raise RuntimeError(f"Erro ao extrair frames: {res.stderr[-300:]}")
