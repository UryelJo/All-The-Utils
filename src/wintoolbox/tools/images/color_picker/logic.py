"""
Lógica pura para captura e conversão de cores em formatos universais (HEX, RGB, HSL, CMYK, HSV).
Isolada de qualquer interface gráfica.
"""
import colorsys
import ctypes
from ctypes import wintypes
from typing import Dict, Optional, Tuple


def rgb_to_formats(r: int, g: int, b: int) -> Dict[str, str]:
    """
    Converte uma tripla RGB (0-255) em múltiplos formatos de código de cores.
    """
    r_norm = max(0, min(255, r))
    g_norm = max(0, min(255, g))
    b_norm = max(0, min(255, b))

    # HEX
    hex_code = f"#{r_norm:02X}{g_norm:02X}{b_norm:02X}"

    # RGB
    rgb_str = f"rgb({r_norm}, {g_norm}, {b_norm})"

    # HSL
    r_f, g_f, b_f = r_norm / 255.0, g_norm / 255.0, b_norm / 255.0
    h, l, s = colorsys.rgb_to_hls(r_f, g_f, b_f)
    hsl_str = f"hsl({int(h * 360)}, {int(s * 100)}%, {int(l * 100)}%)"

    # HSV
    h_v, s_v, v = colorsys.rgb_to_hsv(r_f, g_f, b_f)
    hsv_str = f"hsv({int(h_v * 360)}, {int(s_v * 100)}%, {int(v * 100)}%)"

    # CMYK
    if r_norm == 0 and g_norm == 0 and b_norm == 0:
        cmyk_str = "cmyk(0%, 0%, 0%, 100%)"
    else:
        k = 1.0 - max(r_f, g_f, b_f)
        c = (1.0 - r_f - k) / (1.0 - k) if (1.0 - k) > 0 else 0
        m = (1.0 - g_f - k) / (1.0 - k) if (1.0 - k) > 0 else 0
        y = (1.0 - b_f - k) / (1.0 - k) if (1.0 - k) > 0 else 0
        cmyk_str = f"cmyk({int(c * 100)}%, {int(m * 100)}%, {int(y * 100)}%, {int(k * 100)}%)"

    return {
        "hex": hex_code,
        "rgb": rgb_str,
        "hsl": hsl_str,
        "hsv": hsv_str,
        "cmyk": cmyk_str,
    }


def get_cursor_pos_physical() -> Tuple[int, int]:
    """Posição do cursor em pixels físicos (o QCursor.pos() do Qt 6 é lógico/escala DPI)."""
    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def get_pixel_color_at_screen(x: Optional[int] = None, y: Optional[int] = None) -> Tuple[int, int, int]:
    """
    Captura a cor do pixel na coordenada FÍSICA (x, y) via GDI32; sem coordenadas, usa o cursor.
    """
    try:
        if x is None or y is None:
            x, y = get_cursor_pos_physical()
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        # Sem restype o ctypes trunca o HDC para int de 32 bits no Python 64-bit
        user32.GetDC.restype = wintypes.HDC
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        gdi32.GetPixel.restype = wintypes.DWORD
        gdi32.GetPixel.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]

        hdc = user32.GetDC(None)
        try:
            color_ref = gdi32.GetPixel(hdc, x, y)
        finally:
            user32.ReleaseDC(None, hdc)

        if color_ref == 0xFFFFFFFF:  # CLR_INVALID (fora da área visível)
            return 0, 0, 0
        # GetPixel retorna COLORREF (0x00BBGGRR)
        r = color_ref & 0xFF
        g = (color_ref >> 8) & 0xFF
        b = (color_ref >> 16) & 0xFF
        return r, g, b
    except Exception:
        return 0, 0, 0
