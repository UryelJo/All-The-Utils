"""
Testes unitários para o módulo central de hardware e aceleração por GPU (core/hardware.py).
Valida detecção de GPUs, encoders FFmpeg e estratégias de paralelismo.
"""
import os
from wintoolbox.core.hardware import (
    detect_gpus,
    get_hardware_capabilities,
    get_ffmpeg_video_encoder_params,
)


def test_detect_gpus():
    """Valida que a detecção de GPUs roda sem exceções e retorna uma lista."""
    gpus = detect_gpus()
    assert isinstance(gpus, list)
    # No ambiente do usuário, deve detectar ao menos uma GPU
    for g in gpus:
        assert g.name
        assert g.vendor in ("nvidia", "amd", "intel", "other")


def test_hardware_capabilities():
    """Valida as capacidades de hardware e dimensionamento de workers."""
    caps = get_hardware_capabilities()
    assert caps.cpu_cores >= 1
    assert caps.optimal_batch_workers >= 2
    assert caps.optimal_batch_workers <= max(caps.cpu_cores, 8)
    assert caps.recommended_mode in ("nvenc", "amf", "qsv", "cpu")
    assert isinstance(caps.recommended_label, str)


def test_video_encoder_params():
    """Valida os parâmetros de linha de comando para encoders de vídeo."""
    # Teste de modo CPU forçado
    enc_cpu, args_cpu = get_ffmpeg_video_encoder_params("h264", mode="cpu", crf_quality=22)
    assert enc_cpu == "libx264"
    assert "-c:v" in args_cpu
    assert "libx264" in args_cpu

    # Teste de modo automático
    enc_auto, args_auto = get_ffmpeg_video_encoder_params("h264", mode="auto", crf_quality=22)
    assert enc_auto in ("h264_nvenc", "h264_amf", "h264_qsv", "libx264")
    assert "-c:v" in args_auto

    # Teste HEVC / H.265
    enc_hevc, args_hevc = get_ffmpeg_video_encoder_params("hevc", mode="cpu", crf_quality=26)
    assert enc_hevc == "libx265"
