"""
Lógica pura de automação de cliques do mouse no Windows via ctypes / Win32 API.
Isolada de bibliotecas gráficas.
"""
import ctypes
import time
from typing import Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("automation.autoclicker")

# Constantes de eventos de mouse do Windows
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor_position() -> Tuple[int, int]:
    """Retorna as coordenadas atuais (X, Y) do cursor do mouse na tela."""
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def set_cursor_position(x: int, y: int) -> None:
    """Move o cursor do mouse para as coordenadas especificadas."""
    ctypes.windll.user32.SetCursorPos(int(x), int(y))


def perform_mouse_click(
    button: str = "left",
    click_type: str = "single",
    coords: Optional[Tuple[int, int]] = None
) -> None:
    """
    Executa um clique de mouse simulado pelo sistema operacional.
    button: 'left', 'right' ou 'middle'.
    click_type: 'single' ou 'double'.
    """
    if coords is not None:
        set_cursor_position(coords[0], coords[1])

    b = button.lower().strip()
    if b == "right":
        down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
    elif b == "middle":
        down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
    else:
        down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

    # Clique 1
    ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)

    if click_type == "double":
        time.sleep(0.04)
        ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)
