"""
Lógica para alteração de velocidade de reprodução de áudio e vídeo com ffmpeg.
Suporta aceleração e desaceleração com ou sem preservação de tom de voz (pitch).
"""
import math
import subprocess
from pathlib import Path
from typing import List, Optional

from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe, get_media_info


def build_atempo_filters(speed: float) -> str:
    """
    Constrói a cadeia de filtros atempo do ffmpeg.
    O filtro atempo aceita fatores entre 0.5 e 2.0.
    Para velocidades fora deste intervalo, múltiplos filtros atempo devem ser encadeados.
    """
    if speed <= 0:
        raise ValueError("A velocidade deve ser maior que zero.")

    filters: List[str] = []
    remaining = speed

    if remaining > 1.0:
        while remaining > 2.0:
            filters.append("atempo=2.0")
            remaining /= 2.0
        filters.append(f"atempo={remaining:.4f}")
    elif remaining < 1.0:
        while remaining < 0.5:
            filters.append("atempo=0.5")
            remaining /= 0.5
        filters.append(f"atempo={remaining:.4f}")
    else:
        filters.append("atempo=1.0")

    return ",".join(filters)


def change_media_speed(
    input_path: Path,
    output_path: Path,
    speed: float,
    preserve_pitch: bool = True
) -> Path:
    """
    Altera a velocidade de um arquivo de mídia (vídeo e/ou áudio).

    Args:
        input_path: Arquivo original.
        output_path: Arquivo de destino.
        speed: Fator de velocidade (ex: 0.5 para metade da velocidade, 2.0 para o dobro).
        preserve_pitch: Se True, mantém o tom original da voz/som.
                        Se False, altera o tom proporcionalmente (efeito fita/vinil).
    """
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()

    if not input_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    if speed <= 0:
        raise ValueError("A velocidade deve ser estritamente positiva.")

    info = get_media_info(input_path)
    streams = info.get("streams", [])
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    if not has_video and not has_audio:
        raise ValueError("Nenhum fluxo de áudio ou vídeo detectado no arquivo.")

    ffmpeg = get_ffmpeg_exe()
    cmd: List[str] = [ffmpeg, "-y", "-i", str(input_path)]

    # Filtro de vídeo (setpts)
    if has_video:
        # PTS é multiplicado pelo inverso da velocidade: 1 / speed
        pts_factor = 1.0 / speed
        cmd.extend(["-filter:v", f"setpts={pts_factor:.6f}*PTS"])

    # Filtro de áudio
    if has_audio:
        if preserve_pitch:
            af_filter = build_atempo_filters(speed)
        else:
            # Encontra a taxa de amostragem original ou usa 44100
            sample_rate = 44100
            for s in streams:
                if s.get("codec_type") == "audio" and "sample_rate" in s:
                    try:
                        sample_rate = int(s["sample_rate"])
                        break
                    except (ValueError, TypeError):
                        pass
            resample_rate = int(round(sample_rate * speed))
            af_filter = f"asetrate={resample_rate},aresample={sample_rate}"

        cmd.extend(["-filter:a", af_filter])

    output_path.parent.mkdir(parents=True, exist_ok=True)
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
        raise RuntimeError(f"Erro ao processar velocidade com FFmpeg: {proc.stderr}")

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("Arquivo de saída não foi gerado ou está vazio.")

    return output_path
