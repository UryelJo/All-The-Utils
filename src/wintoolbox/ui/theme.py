"""
Design System Fluent para Windows 11 no PySide6.
Visual sóbrio, limpo, moderno, com suporte a cores de destaque dinâmicas do sistema e tipografia Segoe UI.
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
        return "#0078d4"  # Azul padrão Fluent do Windows


def apply_theme(app: QApplication, mode: str = "dark"):
    """
    Aplica o tema e a folha de estilos global (QSS) refinada à aplicação.
    """
    accent = get_windows_accent_color()

    # Configuração de fonte padrão Segoe UI Variable / Segoe UI
    font = QFont("Segoe UI Variable Text", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)

    if mode == "dark":
        bg_main = "#1c1c1f"
        bg_sidebar = "#18181b"
        bg_card = "#242428"
        bg_input = "#2c2c32"
        border_color = "#38383e"
        text_primary = "#f4f4f5"
        text_secondary = "#a1a1aa"
        item_hover = "#323238"
        item_selected = "#0067b8"
    else:
        bg_main = "#f4f4f6"
        bg_sidebar = "#eaebee"
        bg_card = "#ffffff"
        bg_input = "#ffffff"
        border_color = "#dcdcde"
        text_primary = "#18181b"
        text_secondary = "#71717a"
        item_hover = "#e4e4e7"
        item_selected = "#0078d4"

    qss = f"""
    QMainWindow, QWidget#centralWidget, QStackedWidget {{
        background-color: {bg_main};
        color: {text_primary};
        font-family: 'Segoe UI Variable Text', 'Segoe UI', -apple-system, sans-serif;
    }}

    QScrollArea {{
        background-color: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}

    QWidget {{
        color: {text_primary};
        font-family: 'Segoe UI Variable Text', 'Segoe UI', -apple-system, sans-serif;
    }}

    /* Labels e Textos sempre com fundo transparente para evitar faixas pretas */
    QLabel {{
        background-color: transparent;
        background: transparent;
        color: {text_primary};
    }}

    QCheckBox, QRadioButton {{
        background-color: transparent;
        background: transparent;
        color: {text_primary};
    }}

    QFrame[class="card"], QFrame.card, .card {{
        background-color: {bg_card};
        border: 1px solid {border_color};
        border-radius: 8px;
    }}
    QFrame[class="card"] QLabel, QFrame.card QLabel, .card QLabel {{
        background-color: transparent;
        background: transparent;
    }}


    /* Sidebar Específica */
    QFrame#sidebarFrame {{
        background-color: {bg_sidebar};
        border-right: 1px solid {border_color};
    }}

    /* Botões */
    QPushButton {{
        background-color: {bg_input};
        color: {text_primary};
        border: 1px solid {border_color};
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 500;
        min-height: 24px;
    }}
    QPushButton:hover {{
        background-color: {item_hover};
        border-color: #4a4a52;
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
        filter: brightness(1.15);
    }}

    /* Entradas de texto, combobox e spinboxes */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateTimeEdit {{
        background-color: {bg_input};
        color: {text_primary};
        border: 1px solid {border_color};
        border-radius: 6px;
        padding: 5px 10px;
        font-size: 13px;
        min-height: 24px;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus {{
        border: 1px solid {accent};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}

    /* Árvore de Navegação da Sidebar (QTreeWidget) */
    QTreeWidget#sidebarTree {{
        background-color: transparent;
        color: {text_primary};
        border: none;
        outline: none;
        font-size: 13px;
    }}
    QTreeWidget#sidebarTree::item {{
        padding: 7px 10px;
        border-radius: 6px;
        margin: 1px 2px;
    }}
    QTreeWidget#sidebarTree::item:hover {{
        background-color: {item_hover};
    }}
    QTreeWidget#sidebarTree::item:selected {{
        background-color: {item_selected};
        color: #ffffff;
        font-weight: 600;
    }}

    /* Tabelas e Árvores em geral */
    QTableWidget, QTableView, QListWidget {{
        background-color: {bg_card};
        color: {text_primary};
        border: 1px solid {border_color};
        border-radius: 6px;
        gridline-color: {border_color};
        selection-background-color: {item_selected};
        selection-color: #ffffff;
    }}
    QHeaderView::section {{
        background-color: {bg_main};
        color: {text_secondary};
        border: none;
        border-bottom: 1px solid {border_color};
        padding: 6px 10px;
        font-size: 12px;
        font-weight: 600;
    }}

    /* Abas (QTabWidget) */
    QTabWidget::pane {{
        border: 1px solid {border_color};
        border-radius: 8px;
        background-color: {bg_card};
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: {bg_input};
        color: {text_secondary};
        border: 1px solid {border_color};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 8px 16px;
        margin-right: 4px;
        font-size: 13px;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        background-color: {bg_card};
        color: {text_primary};
        font-weight: 600;
        border-bottom: 2px solid {accent};
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {item_hover};
        color: {text_primary};
    }}

    /* Menus de Contexto Pop-up */
    QMenu {{
        background-color: {bg_card};
        color: {text_primary};
        border: 1px solid {border_color};
        border-radius: 6px;
        padding: 5px;
    }}
    QMenu::item {{
        padding: 6px 24px 6px 12px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {accent};
        color: #ffffff;
    }}
    QMenu::separator {{
        height: 1px;
        background: {border_color};
        margin: 4px 8px;
    }}

    /* Tooltips */
    QToolTip {{
        background-color: #2b2b30;
        color: #f4f4f5;
        border: 1px solid #484852;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
    }}

    /* Barra de Progresso */
    QProgressBar {{
        background-color: {bg_input};
        border: 1px solid {border_color};
        border-radius: 4px;
        text-align: center;
        font-size: 11px;
        height: 16px;
    }}
    QProgressBar::chunk {{
        background-color: {accent};
        border-radius: 3px;
    }}

    /* Scrollbars Modernas e Discretas (Fluent Style) */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {border_color};
        min-height: 24px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #52525b;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: {border_color};
        min-width: 24px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: #52525b;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* Tipografia de Cabeçalhos */
    QLabel[class="secondary"], QLabel.secondary {{
        color: {text_secondary};
        font-size: 12px;
        background-color: transparent;
        background: transparent;
    }}
    QLabel[class="title"], QLabel.title {{
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.2px;
        background-color: transparent;
        background: transparent;
    }}
    """
    app.setStyleSheet(qss)
