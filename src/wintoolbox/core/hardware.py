"""
Módulo central de detecção de hardware, aceleração por GPU e paralelismo.
Identifica placas de vídeo (NVIDIA, AMD, Intel), suporte a encoders de hardware
no FFmpeg (NVENC, AMF, QSV) e dimensionamento de threads para a máquina.
"""
from dataclasses import dataclass, field
import functools
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class GpuDeviceInfo:
    name: str
    vendor: str  # "nvidia", "amd", "intel", "other"
    vram_mb: Optional[int] = None
    driver_version: Optional[str] = None


@dataclass
class HardwareCapabilities:
    gpus: List[GpuDeviceInfo] = field(default_factory=list)
    has_nvenc: bool = False
    has_amf: bool = False
    has_qsv: bool = False
    recommended_mode: str = "cpu"  # "nvenc", "amf", "qsv", "cpu"
    recommended_label: str = "Processador (CPU)"
    cpu_cores: int = 4
    optimal_batch_workers: int = 4


def detect_gpus() -> List[GpuDeviceInfo]:
    """Detecta as placas de vídeo instaladas no sistema operacional Windows."""
    gpus: List[GpuDeviceInfo] = []
    seen_names = set()

    # 1. Tenta consulta direta via nvidia-smi para dados ricos de GPUs NVIDIA
    if shutil.which("nvidia-smi"):
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=3
            )
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        name, drv, vram = parts[0], parts[1], parts[2]
                        try:
                            vram_val = int(float(vram))
                        except Exception:
                            vram_val = None
                        gpus.append(GpuDeviceInfo(name=name, vendor="nvidia", vram_mb=vram_val, driver_version=drv))
                        seen_names.add(name.lower())
        except Exception:
            pass

    # 2. Consulta via WMI / PowerShell (detecta AMD Radeon, Intel Iris/Arc e outros)
    try:
        cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"]
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=4
        )
        if res.returncode == 0:
            for line in res.stdout.strip().splitlines():
                name = line.strip()
                if not name or name.lower() in seen_names or "virtual" in name.lower() or "basic" in name.lower():
                    continue

                low = name.lower()
                vendor = "other"
                if "nvidia" in low or "geforce" in low or "rtx" in low or "gtx" in low:
                    vendor = "nvidia"
                elif "amd" in low or "radeon" in low:
                    vendor = "amd"
                elif "intel" in low or "arc" in low or "iris" in low or "uhd" in low:
                    vendor = "intel"

                gpus.append(GpuDeviceInfo(name=name, vendor=vendor))
                seen_names.add(low)
    except Exception:
        pass

    return gpus


@functools.lru_cache(maxsize=1)
def get_hardware_capabilities() -> HardwareCapabilities:
    """Coleta e armazena em cache os recursos de hardware e encoders disponíveis."""
    gpus = detect_gpus()
    cpu_cores = os.cpu_count() or 4
    # Para lote de I/O e CPU, dimensiona workers de forma equilibrada sem travar a máquina
    optimal_batch = max(2, min(cpu_cores, 8))

    has_nvenc = False
    has_amf = False
    has_qsv = False

    # Valida encoders presentes no binário do ffmpeg
    try:
        from wintoolbox.tools.media.ffmpeg_utils import get_ffmpeg_exe
        ffmpeg_bin = get_ffmpeg_exe()
        res = subprocess.run(
            [ffmpeg_bin, "-encoders"],
            capture_output=True,
            text=True,
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=4
        )
        out = res.stdout.lower()
        has_nvenc = "h264_nvenc" in out
        has_amf = "h264_amf" in out
        has_qsv = "h264_qsv" in out
    except Exception:
        pass

    # Determina a aceleração por hardware prioritária
    recommended_mode = "cpu"
    recommended_label = "Processador (CPU)"

    has_nvidia_gpu = any(g.vendor == "nvidia" for g in gpus)
    has_amd_gpu = any(g.vendor == "amd" for g in gpus)
    has_intel_gpu = any(g.vendor == "intel" for g in gpus)

    if has_nvidia_gpu and has_nvenc:
        nv_gpu = next(g for g in gpus if g.vendor == "nvidia")
        recommended_mode = "nvenc"
        recommended_label = f"NVIDIA NVENC ({nv_gpu.name})"
    elif has_amd_gpu and has_amf:
        amd_gpu = next(g for g in gpus if g.vendor == "amd")
        recommended_mode = "amf"
        recommended_label = f"AMD AMF ({amd_gpu.name})"
    elif has_intel_gpu and has_qsv:
        intel_gpu = next(g for g in gpus if g.vendor == "intel")
        recommended_mode = "qsv"
        recommended_label = f"Intel QuickSync ({intel_gpu.name})"

    return HardwareCapabilities(
        gpus=gpus,
        has_nvenc=has_nvenc,
        has_amf=has_amf,
        has_qsv=has_qsv,
        recommended_mode=recommended_mode,
        recommended_label=recommended_label,
        cpu_cores=cpu_cores,
        optimal_batch_workers=optimal_batch,
    )


def get_ffmpeg_video_encoder_params(
    target_codec: str = "h264",
    mode: str = "auto",
    crf_quality: int = 22,
) -> Tuple[str, List[str]]:
    """
    Retorna o encoder de vídeo ideal e seus parâmetros de aceleração.
    Suporta: 'auto', 'nvenc', 'amf', 'qsv', 'cpu'.
    """
    caps = get_hardware_capabilities()
    selected_mode = caps.recommended_mode if mode == "auto" else mode

    is_h265 = target_codec.lower() in ("h265", "hevc")

    # 1. NVIDIA NVENC (RTX/GTX)
    if selected_mode == "nvenc" and caps.has_nvenc:
        encoder = "hevc_nvenc" if is_h265 else "h264_nvenc"
        # NVENC usa preset de performance p1 a p7 ou medium/fast, e -cq (Constant Quality)
        args = ["-c:v", encoder, "-preset", "p4", "-cq", str(crf_quality), "-b:v", "0"]
        return encoder, args

    # 2. AMD AMF (Radeon)
    if selected_mode == "amf" and caps.has_amf:
        encoder = "hevc_amf" if is_h265 else "h264_amf"
        args = ["-c:v", encoder, "-quality", "speed", "-rc", "cqp", "-qp_i", str(crf_quality), "-qp_p", str(crf_quality)]
        return encoder, args

    # 3. Intel Quick Sync Video (QSV)
    if selected_mode == "qsv" and caps.has_qsv:
        encoder = "hevc_qsv" if is_h265 else "h264_qsv"
        args = ["-c:v", encoder, "-preset", "medium", "-global_quality", str(crf_quality)]
        return encoder, args

    # 4. Fallback Padrão CPU (libx264 / libx265)
    encoder = "libx265" if is_h265 else "libx264"
    args = ["-c:v", encoder, "-preset", "medium", "-crf", str(crf_quality)]
    return encoder, args
