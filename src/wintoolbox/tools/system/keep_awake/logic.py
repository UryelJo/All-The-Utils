"""
Lógica pura para controle do estado de energia e suspensão do Windows (Keep Awake).

Utiliza a API nativa do kernel do Windows (SetThreadExecutionState) para impedir
que o sistema hiberne, suspenda ou desligue a tela durante tarefas longas,
apresentações e downloads.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
import ctypes
import sys
import time
from typing import Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.keep_awake.logic")

# Flags oficiais Win32 SetThreadExecutionState
ES_CONTINUOUS: int = 0x80000000
ES_SYSTEM_REQUIRED: int = 0x00000001
ES_DISPLAY_REQUIRED: int = 0x00000002
ES_AWAYMODE_REQUIRED: int = 0x00000040


def calculate_execution_flags(keep_display: bool = True, keep_system: bool = True) -> int:
    """Calcula a máscara binária de flags para o kernel do Windows."""
    flags = ES_CONTINUOUS
    if keep_system:
        flags |= ES_SYSTEM_REQUIRED
    if keep_display:
        flags |= ES_DISPLAY_REQUIRED
    return flags


def apply_keep_awake(keep_display: bool = True, keep_system: bool = True) -> bool:
    """
    Informa ao Windows para manter o sistema e/ou a tela acordados.

    Returns:
        True se a chamada da API do Windows teve sucesso (retorno != 0).
    """
    if sys.platform != "win32":
        _log.warning("Keep Awake suportado apenas na plataforma Windows.")
        return False

    flags = calculate_execution_flags(keep_display, keep_system)
    try:
        ret = ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(flags))
        return ret != 0
    except Exception as e:
        _log.error(f"Erro ao definir SetThreadExecutionState: {e}")
        return False


def release_keep_awake() -> bool:
    """
    Restaura o comportamento padrão de suspensão e energia do sistema operacional.
    """
    if sys.platform != "win32":
        return False

    try:
        # ES_CONTINUOUS sem outras flags restaura o timer normal de inatividade
        ret = ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(ES_CONTINUOUS))
        return ret != 0
    except Exception as e:
        _log.error(f"Erro ao restaurar SetThreadExecutionState: {e}")
        return False


def format_remaining_seconds(seconds_left: int) -> str:
    """Formata segundos restantes em string legível hh:mm:ss."""
    if seconds_left <= 0:
        return "00:00:00"
    hours = seconds_left // 3600
    minutes = (seconds_left % 3600) // 60
    secs = seconds_left % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
