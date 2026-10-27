"""
Testes unitários para o Conta-Gotas de Tela com captura global e overlay flutuante.
"""
from PySide6.QtCore import QPoint
import pytest

from wintoolbox.core.registry import get_tool
from wintoolbox.tools.images.color_picker.logic import (
    VK_ESCAPE, VK_LBUTTON, VK_RBUTTON, VK_RETURN, VK_SPACE,
    is_key_pressed, rgb_to_formats
)
from wintoolbox.tools.images.color_picker.tool import (
    ColorPickerTool, ColorPickerView, FloatingMagnifierOverlay
)


def test_is_key_pressed_vk_codes():
    """Valida que a verificação de teclas Win32 responde com booleano válido."""
    res_space = is_key_pressed(VK_SPACE)
    assert isinstance(res_space, bool)

    res_lbutton = is_key_pressed(VK_LBUTTON)
    assert isinstance(res_lbutton, bool)

    res_esc = is_key_pressed(VK_ESCAPE)
    assert isinstance(res_esc, bool)


def test_floating_magnifier_overlay_lifecycle(qtbot):
    """Garante que o overlay flutuante seja instanciado com as flags corretas sem roubar foco."""
    overlay = FloatingMagnifierOverlay()
    qtbot.addWidget(overlay)

    # Verifica se não rouba foco de outros aplicativos (essencial para WhatsApp e browsers)
    flags = overlay.windowFlags()
    from PySide6.QtCore import Qt
    assert bool(flags & Qt.WindowDoesNotAcceptFocus)
    assert bool(flags & Qt.FramelessWindowHint)
    assert bool(flags & Qt.WindowStaysOnTopHint)

    # Atualiza o magnifier
    overlay.update_magnifier(QPoint(100, 100), "#25D366")
    assert overlay._hex_code == "#25D366"


def test_color_picker_view_build_and_toggle(qtbot):
    """Valida inicialização da UI do ColorPicker e disparo do modo Conta-Gotas."""
    tool = ColorPickerTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    assert isinstance(view, ColorPickerView)
    assert view.btn_toggle_picker is not None
    assert view.chk_auto_copy.isChecked() is True
    assert view.chk_sound.isChecked() is True

    # Inicia captura
    view._start_screen_picker()
    assert view._picking_active is True
    assert view._picker_timer.isActive() is True
    assert view._overlay.isVisible() is True

    # Para captura
    view._stop_screen_picker()
    assert view._picking_active is False
    assert view._picker_timer.isActive() is False
    assert view._overlay.isHidden() is True
