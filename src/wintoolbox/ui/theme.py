"""
Design System Fluent para Windows 11 no PySide6.
Visual sóbrio, limpo, sem cara de IA, sem emojis, tipografia Segoe UI.
"""
import winreg
from typing import Optional
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication

def get_windows_accent_color() -> str:
    """Lê a cor de destaque configurada no Windows (DWM AccentColor)."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\DWM"
        )
        val, _ = winreg.QueryValueEx(key, "AccentColor")
        winreg.CloseKey(key)
        # AccentColor vem como 0xAABBGGRR
        r = val & 0xFF
        g = (val >> 8) & 0xFF
        b = (val >> 16) & 0xFF
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return "#0078d4"  # Azul padrão do Windows

def apply_theme(app: QApplication, mode: str = "dark"):
    """
    Aplica o tema e a folha de estilos global (QSS) à aplicação.
    """
    accent = get_windows_accent_color()

    # Configuração de fonte padrão Segoe UI Variable / Segoe UI
    font = QFont("Segoe UI Variable Text", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)

    if mode == "dark":
        bg_main = "#1e1e1e"
        bg_card = "#252526"
        bg_input = "#2d2d30"
        border_color = "#3e3e42"
        text_primary = "#f1f1f1"
        text_secondary = "#9d9d9d"
        item_hover = "#37373d"
        item_selected = "#094771"
    else:
        bg_main = "#f3f3f3"
        bg_card = "#ffffff"
        bg_input = "#ffffff"
        border_color = "#e5e5e5"
        text_primary = "#1b1b1b"
        text_secondary = "#616161"
        item_hover = "#f0f0f0"
        item_selected = "#e0eef9"

    qss = f"""
    QMainWindow, QWidget {{
        background-color: {bg_main};
        color: {text_primary};
        font-family: 'Segoe UI Variable Text', 'Segoe UI', -apple-system, sans-serif;
    }}

    QFrame.card {{
        background-color: {bg_card};
        border: 1px solid {border_color};
        border-radius: 6px;
    }}

    /* Botões */
    QPushButton {{
        background-color: {bg_input};
        color: {text_primary};
        border: 1px solid {border_color};
        border-radius: 4px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 500;
        min-height: 24px;
    }}
    QPushButton:hover {{
        background-color: {item_hover};
    }}
    QPushButton:pressed {{
        background-color: {border_color};
    }}
    QPushButton:disabled {{
        color: {text_secondary};
        background-color: {bg_main};
        border-color: {border_color};
    }}

    /* Botão de destaque principal */
    QPushButton.primary {{
        background-color: {accent};
        color: #ffffff;
        border: 1px solid {accent};
        font-weight: 600;
    }}
    QPushButton.primary:hover {{
        opacity: 0.9;
        filter: brightness(1.1);
    }}

    /* Entradas de texto e combobox */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {bg_input};
        color: {text_primary};
        border: 1px solid {border_color};
        border-radius: 4px;
        padding: 5px 8px;
        font-size: 13px;
        min-height: 22px;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border: 1px solid {accent};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}

    /* Tabelas e Árvores */
    QTableWidget, QTableView, QListWidget {{
        background-color: {bg_card};
        color: {text_primary};
        border: 1px solid {border_color};
        border-radius: 4px;
        gridline-color: {border_color};
        selection-background-color: {item_selected};
        selection-color: {text_primary};
    }}
    QHeaderView::section {{
        background-color: {bg_main};
        color: {text_secondary};
        border: none;
        border-bottom: 1px solid {border_color};
        padding: 6px;
        font-size: 12px;
        font-weight: 600;
    }}

    /* Barra de Progresso */
    QProgressBar {{
        background-color: {bg_input};
        border: 1px solid {border_color};
        border-radius: 3px;
        text-align: center;
        font-size: 11px;
        height: 14px;
    }}
    QProgressBar::chunk {{
        background-color: {accent};
        border-radius: 2px;
    }}

    /* Scrollbars discretas */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {border_color};
        min-height: 20px;
        border-radius: 4px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* Labels secundárias */
    QLabel.secondary {{
        color: {text_secondary};
        font-size: 12px;
    }}
    QLabel.title {{
        font-size: 18px;
        font-weight: 600;
    }}
    """
    app.setStyleSheet(qss)
