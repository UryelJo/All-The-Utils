"""
Lógica pura de controle de janelas do Windows (Sempre no Topo, Transparência e Posicionamento).
Usa ctypes / Win32 API nativa sem bibliotecas externas.
"""
import ctypes
from ctypes import wintypes
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("automation.window_manager")

# Constantes Win32
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
LWA_ALPHA = 0x00000002

SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_CXWORKAREA = 16
SM_CYWORKAREA = 17


def list_open_windows() -> List[Dict[str, Any]]:
    """Enumera todas as janelas abertas visíveis com título na área de trabalho."""
    windows: List[Dict[str, Any]] = []

    def enum_proc(hwnd, lparam):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.strip()

                # Ignora certas janelas de sistema sem interesse para o usuário
                if title and title not in ("Program Manager", "Default IME", "MSCTFIME UI"):
                    # Verifica se está no modo topmost
                    ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    is_topmost = bool(ex_style & 0x00000008)  # WS_EX_TOPMOST

                    windows.append({
                        "hwnd": hwnd,
                        "title": title,
                        "is_topmost": is_topmost
                    })
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_proc), 0)

    # Ordena por título alfabético
    windows.sort(key=lambda w: w["title"].lower())
    return windows


def set_window_always_on_top(hwnd: int, enable: bool) -> bool:
    """Coloca ou retira uma janela do modo 'Sempre no Topo'."""
    flag = HWND_TOPMOST if enable else HWND_NOTOPMOST
    ret = ctypes.windll.user32.SetWindowPos(
        hwnd, flag, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    )
    return bool(ret)


def set_window_transparency(hwnd: int, opacity_percent: int) -> bool:
    """Ajusta a opacidade da janela de 10% a 100%."""
    pct = max(10, min(100, int(opacity_percent)))
    alpha = int((pct / 100.0) * 255)

    # Garante o estilo estendido WS_EX_LAYERED
    ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if not (ex_style & WS_EX_LAYERED):
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED)

    # Aplica transparência
    ret = ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)
    return bool(ret)


def snap_window(hwnd: int, position: str) -> bool:
    """
    Redimensiona e posiciona a janela na área útil da tela.
    position: 'left', 'right', 'top', 'bottom', 'center' ou 'maximize'.
    """
    rect = wintypes.RECT()
    # SPI_GETWORKAREA = 0x0030
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)

    work_x = rect.left
    work_y = rect.top
    work_w = rect.right - rect.left
    work_h = rect.bottom - rect.top

    pos = position.lower().strip()

    if pos == "left":
        x, y, w, h = work_x, work_y, work_w // 2, work_h
    elif pos == "right":
        x, y, w, h = work_x + (work_w // 2), work_y, work_w // 2, work_h
    elif pos == "top":
        x, y, w, h = work_x, work_y, work_w, work_h // 2
    elif pos == "bottom":
        x, y, w, h = work_x, work_y + (work_h // 2), work_w, work_h // 2
    elif pos == "center":
        w, h = int(work_w * 0.7), int(work_h * 0.7)
        x = work_x + (work_w - w) // 2
        y = work_y + (work_h - h) // 2
    else:  # maximize
        x, y, w, h = work_x, work_y, work_w, work_h

    ret = ctypes.windll.user32.MoveWindow(hwnd, x, y, w, h, True)
    return bool(ret)
