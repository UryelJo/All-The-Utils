"""
Design System Fluent 2.0 para Windows 11 no PySide6.
Suporta Tokens Semânticos (Dark, Light e Automático do Sistema), Cor de Destaque
nativa do Windows (DWM) ou personalizada, sem estilos hardcoded nos componentes.
"""
import winreg
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from wintoolbox.core.settings import load_settings

# Cores de destaque predefinidas para escolha opcional do usuário
ACCENT_PRESETS: List[Tuple[str, str]] = [
    ("", "Automático (Cor do Windows)"),
    ("#0078d4", "Azul Fluent (Padrão)"),
    ("#6366f1", "Índigo Moderno"),
    ("#10b981", "Verde Esmeralda"),
    ("#f59e0b", "Âmbar Solar"),
    ("#ec4899", "Rosa Vibrante"),
    ("#8b5cf6", "Roxo Real"),
]


@dataclass
class ThemeTokens:
    """Tokens semânticos do tema ativo."""
    is_dark: bool
    accent: str
    accent_subtle: str
    bg_main: str
    bg_sidebar: str
    bg_topbar: str
    bg_card: str
    bg_card_hover: str
    bg_input: str
    bg_terminal: str
    border_color: str
    border_subtle: str
    text_primary: str
    text_secondary: str
    text_muted: str
    item_hover: str
    item_selected: str
    status_success: str
    status_warning: str
    status_danger: str


_ACTIVE_TOKENS: Optional[ThemeTokens] = None


def get_windows_accent_color() -> str:
    """Lê a cor de destaque configurada no Windows (DWM AccentColor)."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\DWM"
        )
        val, _ = winreg.QueryValueEx(key, "AccentColor")
        winreg.CloseKey(key)
        r = val & 0xFF
        g = (val >> 8) & 0xFF
        b = (val >> 16) & 0xFF
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return "#0078d4"


def get_windows_system_theme() -> str:
    """Detecta se o Windows está em modo escuro ou claro para aplicativos."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if int(val) == 1 else "dark"
    except Exception:
        return "dark"


def resolve_effective_mode(mode: str) -> str:
    """Resolve 'system' para 'dark' ou 'light'."""
    if mode == "system":
        return get_windows_system_theme()
    return "light" if mode == "light" else "dark"


def build_tokens(mode: str = "dark", accent_override: str = "") -> ThemeTokens:
    """Constrói os tokens semânticos de acordo com o modo e a cor de destaque."""
    effective = resolve_effective_mode(mode)
    accent = accent_override.strip() if accent_override and accent_override.strip() else get_windows_accent_color()

    if effective == "dark":
        return ThemeTokens(
            is_dark=True,
            accent=accent,
            accent_subtle="#172b42",
            bg_main="#141417",
            bg_sidebar="#101013",
            bg_topbar="#18181c",
            bg_card="#1d1d22",
            bg_card_hover="#26262d",
            bg_input="#24242b",
            bg_terminal="#101012",
            border_color="#2e2e36",
            border_subtle="#232329",
            text_primary="#f4f4f6",
            text_secondary="#a1a1aa",
            text_muted="#71717a",
            item_hover="#27272f",
            item_selected=accent,
            status_success="#10b981",
            status_warning="#f59e0b",
            status_danger="#ef4444",
        )
    else:
        return ThemeTokens(
            is_dark=False,
            accent=accent,
            accent_subtle="#e0f2fe",
            bg_main="#f6f7f9",
            bg_sidebar="#eef0f4",
            bg_topbar="#ffffff",
            bg_card="#ffffff",
            bg_card_hover="#f1f5f9",
            bg_input="#ffffff",
            bg_terminal="#f8fafc",
            border_color="#e2e8f0",
            border_subtle="#edf2f7",
            text_primary="#0f172a",
            text_secondary="#475569",
            text_muted="#64748b",
            item_hover="#e2e8f0",
            item_selected=accent,
            status_success="#059669",
            status_warning="#d97706",
            status_danger="#dc2626",
        )


def get_current_tokens() -> ThemeTokens:
    """Retorna os tokens do tema atualmente aplicado."""
    global _ACTIVE_TOKENS
    if _ACTIVE_TOKENS is None:
        st = load_settings()
        _ACTIVE_TOKENS = build_tokens(
            mode=st.get("theme", "dark"),
            accent_override=st.get("accent_override", "")
        )
    return _ACTIVE_TOKENS


def apply_theme(app: Optional[QApplication], mode: Optional[str] = None, accent_override: Optional[str] = None):
    """
    Aplica o tema e a folha de estilos global (QSS) refinada à aplicação.
    """
    global _ACTIVE_TOKENS
    st = load_settings()
    if mode is None:
        mode = st.get("theme", "dark")
    if accent_override is None:
        accent_override = st.get("accent_override", "")

    t = build_tokens(mode=mode, accent_override=accent_override)
    _ACTIVE_TOKENS = t

    if app is None:
        app = QApplication.instance()
    if app is None:
        return

    font = QFont("Segoe UI", 10)
    font.setPointSize(10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)

    hero_grad_start = t.bg_card
    hero_grad_end = t.bg_card
    hero_border = t.border_color
    selected_bg = "#25252c" if t.is_dark else "#e2e8f0"

    badge_batch_bg = "#1e293b" if t.is_dark else "#f1f5f9"
    badge_batch_fg = "#93c5fd" if t.is_dark else "#1d4ed8"
    badge_panel_bg = "#1c2824" if t.is_dark else "#f1f5f9"
    badge_panel_fg = "#86efac" if t.is_dark else "#15803d"

    qss = f"""
    QMainWindow, QWidget#centralWidget, QStackedWidget {{
        background-color: {t.bg_main};
        color: {t.text_primary};
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
        color: {t.text_primary};
        font-family: 'Segoe UI Variable Text', 'Segoe UI', -apple-system, sans-serif;
    }}

    QLabel {{
        background-color: transparent;
        background: transparent;
        color: {t.text_primary};
    }}

    QCheckBox, QRadioButton {{
        background-color: transparent;
        background: transparent;
        color: {t.text_primary};
        spacing: 8px;
    }}

    /* Cartões e Superfícies Sólidas */
    QFrame[class="card"], QFrame.card, .card {{
        background-color: {t.bg_card};
        border: 1px solid {t.border_color};
        border-radius: 8px;
    }}
    QFrame[class="card"] QLabel, QFrame.card QLabel, .card QLabel {{
        background-color: transparent;
    }}

    /* Cards Interativos de Ferramenta (Home Page) */
    QFrame[class="tool-card"], QFrame.tool-card {{
        background-color: {t.bg_card};
        border: 1px solid {t.border_color};
        border-radius: 8px;
    }}
    QFrame[class="tool-card"]:hover, QFrame.tool-card:hover {{
        background-color: {t.bg_card_hover};
        border: 1px solid {t.border_color};
    }}

    /* Hero Banner / Cabeçalho da Home */
    QFrame#heroCard {{
        background-color: {t.bg_card};
        border: 1px solid {t.border_color};
        border-radius: 8px;
    }}

    /* Dropzone Visual (Smart Drop & Batch Input Vazio) */
    QFrame[class="dropzone"], QFrame.dropzone {{
        background-color: {t.bg_sidebar};
        border: 2px dashed {t.border_color};
        border-radius: 10px;
    }}
    QFrame[class="dropzone"]:hover, QFrame.dropzone:hover,
    QFrame[class="dropzone-active"], QFrame.dropzone-active {{
        background-color: {t.accent_subtle};
        border: 2px dashed {t.accent};
    }}

    /* Sidebar Lateral e Topbar Contextual */
    QFrame#sidebarFrame {{
        background-color: {t.bg_sidebar};
        border-right: 1px solid {t.border_color};
    }}

    QFrame#topbarFrame {{
        background-color: {t.bg_topbar};
        border-bottom: 1px solid {t.border_color};
    }}

    QStatusBar {{
        background-color: {t.bg_sidebar};
        border-top: 1px solid {t.border_color};
        color: {t.text_secondary};
        font-size: 11px;
    }}

    /* Paleta de Comandos (Ctrl+K) */
    QFrame#commandPaletteContainer {{
        background-color: {t.bg_card};
        border: 1px solid {t.accent};
        border-radius: 10px;
    }}

    /* Botões Padrão */
    QPushButton {{
        background-color: {t.bg_input};
        color: {t.text_primary};
        border: 1px solid {t.border_color};
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 500;
        min-height: 24px;
    }}
    QPushButton:hover {{
        background-color: {t.item_hover};
        border-color: {t.text_muted};
    }}
    QPushButton:pressed {{
        background-color: {t.border_color};
    }}
    QPushButton:disabled {{
        color: {t.text_muted};
        background-color: {t.bg_main};
        border-color: {t.border_subtle};
    }}

    /* Botão Primário de Destaque */
    QPushButton[class="primary"], QPushButton.primary {{
        background-color: {t.accent};
        color: #ffffff;
        border: 1px solid {t.accent};
        font-weight: 600;
    }}
    QPushButton[class="primary"]:hover, QPushButton.primary:hover {{
        border-color: #ffffff;
    }}

    /* Botão Ghost / Transparente (Topbar, Ícones, Estrela) */
    QPushButton[class="ghost"], QPushButton.ghost {{
        background-color: transparent;
        border: 1px solid transparent;
        color: {t.text_secondary};
        padding: 4px 8px;
        min-height: 22px;
    }}
    QPushButton[class="ghost"]:hover, QPushButton.ghost:hover {{
        background-color: {t.item_hover};
        color: {t.text_primary};
        border-radius: 6px;
    }}

    /* Chips de Filtro de Categoria */
    QPushButton[class="chip"], QPushButton.chip {{
        background-color: {t.bg_card};
        color: {t.text_secondary};
        border: 1px solid {t.border_color};
        border-radius: 14px;
        padding: 4px 12px;
        font-size: 12px;
        font-weight: 500;
        min-height: 20px;
    }}
    QPushButton[class="chip"]:hover, QPushButton.chip:hover {{
        background-color: {t.item_hover};
        color: {t.text_primary};
    }}
    QPushButton[class="chip"]:checked, QPushButton.chip:checked {{
        background-color: {t.accent};
        color: #ffffff;
        border-color: {t.accent};
        font-weight: 600;
    }}

    /* Badges Semânticos */
    QLabel[class="badge-batch"], QLabel.badge-batch {{
        background-color: {badge_batch_bg};
        color: {badge_batch_fg};
        font-size: 10px;
        font-weight: 600;
        border-radius: 4px;
        padding: 2px 7px;
    }}
    QLabel[class="badge-panel"], QLabel.badge-panel {{
        background-color: {badge_panel_bg};
        color: {badge_panel_fg};
        font-size: 10px;
        font-weight: 600;
        border-radius: 4px;
        padding: 2px 7px;
    }}
    QLabel[class="ext-chip"], QLabel.ext-chip {{
        background-color: {t.bg_input};
        color: {t.text_secondary};
        border: 1px solid {t.border_color};
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
    }}

    /* Entradas de Texto e Seletores */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateTimeEdit {{
        background-color: {t.bg_input};
        color: {t.text_primary};
        border: 1px solid {t.border_color};
        border-radius: 6px;
        padding: 5px 10px;
        font-size: 13px;
        min-height: 24px;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus {{
        border: 1px solid {t.accent};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {t.bg_card};
        color: {t.text_primary};
        border: 1px solid {t.border_color};
        selection-background-color: {t.accent};
        selection-color: #ffffff;
    }}

    /* Terminal / Painel de Log */
    QPlainTextEdit, QTextEdit {{
        background-color: {t.bg_terminal};
        color: {t.text_primary};
        border: 1px solid {t.border_color};
        border-radius: 6px;
        padding: 6px;
    }}

    /* Árvore de Navegação da Sidebar */
    QTreeWidget#sidebarTree {{
        background-color: transparent;
        color: {t.text_primary};
        border: none;
        outline: none;
        font-size: 13px;
    }}
    QTreeWidget#sidebarTree::item {{
        padding: 6px 8px;
        border-radius: 6px;
        margin: 1px 2px;
    }}
    QTreeWidget#sidebarTree::item:hover {{
        background-color: {t.item_hover};
    }}
    QTreeWidget#sidebarTree::item:selected {{
        background-color: {selected_bg};
        color: #ffffff;
        font-weight: 600;
    }}

    /* Botões de Navegação da Sidebar (Início, Histórico, Configurações) */
    QPushButton[class="nav-item"], QPushButton.nav-item {{
        background-color: transparent;
        color: {t.text_secondary};
        border: 1px solid transparent;
        border-radius: 6px;
        text-align: left;
        padding: 6px 10px;
        font-size: 13px;
        font-weight: 500;
        min-height: 24px;
    }}
    QPushButton[class="nav-item"]:hover, QPushButton.nav-item:hover {{
        background-color: {t.item_hover};
        color: {t.text_primary};
    }}
    QPushButton[class="nav-item"][active="true"], QPushButton.nav-item[active="true"] {{
        background-color: {selected_bg};
        color: {t.text_primary};
        font-weight: 600;
    }}

    QPushButton[class="nav-icon-btn"], QPushButton.nav-icon-btn {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 4px;
        min-height: 32px;
        min-width: 32px;
        max-height: 36px;
        max-width: 36px;
    }}
    QPushButton[class="nav-icon-btn"]:hover, QPushButton.nav-icon-btn:hover {{
        background-color: {t.item_hover};
    }}
    QPushButton[class="nav-icon-btn"][active="true"], QPushButton.nav-icon-btn[active="true"] {{
        background-color: {selected_bg};
    }}

    /* Tabelas e Listas */
    QTableWidget, QTableView, QListWidget {{
        background-color: {t.bg_card};
        color: {t.text_primary};
        border: 1px solid {t.border_color};
        border-radius: 6px;
        gridline-color: {t.border_subtle};
        selection-background-color: {t.item_selected};
        selection-color: #ffffff;
        alternate-background-color: {t.bg_main};
    }}
    QHeaderView::section {{
        background-color: {t.bg_sidebar};
        color: {t.text_secondary};
        border: none;
        border-bottom: 1px solid {t.border_color};
        padding: 6px 10px;
        font-size: 12px;
        font-weight: 600;
    }}

    /* Abas (QTabWidget) */
    QTabWidget::pane {{
        border: 1px solid {t.border_color};
        border-radius: 8px;
        background-color: {t.bg_card};
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: {t.bg_input};
        color: {t.text_secondary};
        border: 1px solid {t.border_color};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 8px 16px;
        margin-right: 4px;
        font-size: 13px;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        background-color: {t.bg_card};
        color: {t.text_primary};
        font-weight: 600;
        border-bottom: 2px solid {t.accent};
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {t.item_hover};
        color: {t.text_primary};
    }}

    /* Menus de Contexto */
    QMenu {{
        background-color: {t.bg_card};
        color: {t.text_primary};
        border: 1px solid {t.border_color};
        border-radius: 8px;
        padding: 5px;
    }}
    QMenu::item {{
        padding: 6px 24px 6px 12px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {t.accent};
        color: #ffffff;
    }}
    QMenu::separator {{
        height: 1px;
        background: {t.border_color};
        margin: 4px 8px;
    }}

    /* Tooltips */
    QToolTip {{
        background-color: {t.bg_card};
        color: {t.text_primary};
        border: 1px solid {t.border_color};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
    }}

    /* Barra de Progresso */
    QProgressBar {{
        background-color: {t.bg_input};
        border: 1px solid {t.border_color};
        border-radius: 5px;
        text-align: center;
        font-size: 11px;
        color: {t.text_primary};
        height: 16px;
    }}
    QProgressBar::chunk {{
        background-color: {t.accent};
        border-radius: 4px;
    }}

    /* Scrollbars Modernas (Fluent Style) */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.border_color};
        min-height: 24px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t.text_muted};
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
        background: {t.border_color};
        min-width: 24px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {t.text_muted};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* Classes de Tipografia */
    QLabel[class="secondary"], QLabel.secondary {{
        color: {t.text_secondary};
        font-size: 12px;
        background: transparent;
    }}
    QLabel[class="muted"], QLabel.muted {{
        color: {t.text_muted};
        font-size: 11px;
        background: transparent;
    }}
    QLabel[class="section-title"], QLabel.section-title {{
        color: {t.text_primary};
        font-size: 14px;
        font-weight: 700;
        background: transparent;
    }}
    QLabel[class="title"], QLabel.title {{
        color: {t.text_primary};
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.2px;
        background: transparent;
    }}
    """
    app.setStyleSheet(qss)
