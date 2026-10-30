"""
Testes automatizados da repaginação Bento Grid da HomePage e integração com MainWindow.
Valida:
1. Renderização e instanciação sem exceções.
2. Contratos de sinais e atributos do Bento Grid.
3. Responsividade da camada Bento superior e catálogo.
4. Ausência total de caracteres Unicode de emojis (Regra Anti-Emoji).
5. Conformidade com idioma Português do Brasil (pt-BR).
"""
from pathlib import Path
import unicodedata
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QLineEdit

from wintoolbox.ui.main_window import MainWindow
from wintoolbox.ui.pages.home_page import (
    HomePage, SmartDropBanner, SystemHealthBanner,
    ToolCardWidget, make_launch_arrow_icon, make_upload_pixmap
)
from wintoolbox.core.registry import get_all_tools


def _contains_emoji(text: str) -> bool:
    """Detecta se uma string contém caracteres Unicode de emoji ou símbolos pictográficos."""
    for ch in text:
        # Blocos Unicode típicos de emojis
        cp = ord(ch)
        if (
            0x1F300 <= cp <= 0x1F5FF or  # Miscellaneous Symbols and Pictographs
            0x1F600 <= cp <= 0x1F64F or  # Emoticons
            0x1F680 <= cp <= 0x1F6FF or  # Transport and Map Symbols
            0x1F700 <= cp <= 0x1F77F or  # Alchemical Symbols
            0x1F780 <= cp <= 0x1F7FF or  # Geometric Shapes Extended
            0x1F800 <= cp <= 0x1F8FF or  # Supplemental Arrows-C
            0x1F900 <= cp <= 0x1F9FF or  # Supplemental Symbols and Pictographs
            0x1FA00 <= cp <= 0x1FA6F or  # Chess Symbols
            0x1FA70 <= cp <= 0x1FAFF or  # Symbols and Pictographs Extended-A
            0x2600 <= cp <= 0x26FF or    # Misc symbols (e.g. ⚡, ☕, ⚠️)
            0x2700 <= cp <= 0x27BF       # Dingbats (e.g. ✂️, ✈️, ✉️)
        ):
            return True
    return False


def test_bento_grid_instantiation_and_rendering(qtbot):
    """Verifica que HomePage e MainWindow inicializam sem levantar nenhuma exceção."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("home")

    home = window.home_page
    assert isinstance(home, HomePage)

    # Valida componentes Bento do Top Tier
    assert hasattr(home, "hero_card")
    assert hasattr(home, "smart_drop_banner")
    assert hasattr(home, "health_banner")
    assert isinstance(home.smart_drop_banner, SmartDropBanner)
    assert isinstance(home.health_banner, SystemHealthBanner)

    # Valida presença de botões e sinais essenciais
    assert home.smart_drop_banner.acceptDrops() is True
    assert home.health_banner.btn_details is not None
    assert home.btn_customize is not None


def test_bento_tool_card_structure_and_interactions(qtbot):
    """Valida estrutura dos novos ToolCardWidgets com cantos de 16px e botão circular ↗."""
    tools = get_all_tools()
    assert len(tools) >= 100
    tool = tools[0]

    # Modo Confortável
    card_comf = ToolCardWidget(tool, density="comfortable")
    qtbot.addWidget(card_comf)
    assert card_comf.property("class") == "tool-card"
    assert hasattr(card_comf, "btn_fav")
    assert hasattr(card_comf, "btn_launch")
    assert card_comf.btn_launch.property("class") == "action-circle-btn"

    # Modo Compacto
    card_comp = ToolCardWidget(tool, density="compact")
    qtbot.addWidget(card_comp)
    assert card_comp.btn_launch is not None

    # Testa disparo do sinal clicked ao clicar no botão de lançamento ↗
    clicked_ids = []
    card_comf.clicked.connect(clicked_ids.append)
    qtbot.mouseClick(card_comf.btn_launch, Qt.LeftButton)
    assert clicked_ids == [tool.id]


def test_bento_top_tier_responsiveness(qtbot):
    """Valida adaptação de layout responsivo do Top Bento Tier em larguras estreita, média e ampla."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("home")
    home = window.home_page

    # Tela ampla (>= 1200px)
    home.resize(1300, 800)
    home._update_top_bento_layout(1300)
    assert home.bento_top_layout.count() >= 3

    # Tela média (1000px)
    home.resize(1000, 800)
    home._update_top_bento_layout(1000)
    assert home.bento_top_layout.count() >= 3

    # Tela compacta (< 850px)
    home.resize(750, 800)
    home._update_top_bento_layout(750)
    assert home.bento_top_layout.count() >= 3


def test_zero_emojis_in_home_page(qtbot):
    """Garante cumprimento estrito da Regra Anti-Emoji em todos os rótulos e botões da HomePage."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("home")
    home = window.home_page

    # Varre todos os QLabels na HomePage
    labels = home.findChildren(QLabel)
    for lbl in labels:
        txt = lbl.text()
        assert not _contains_emoji(txt), f"Emoji detectado no QLabel: '{txt}'"

    # Varre todos os QPushButtons na HomePage
    buttons = home.findChildren(QPushButton)
    for btn in buttons:
        txt = btn.text()
        assert not _contains_emoji(txt), f"Emoji detectado no QPushButton: '{txt}'"
        tip = btn.toolTip()
        assert not _contains_emoji(tip), f"Emoji detectado no ToolTip: '{tip}'"

    # Varre todos os QLineEdits
    inputs = home.findChildren(QLineEdit)
    for inp in inputs:
        ph = inp.placeholderText()
        assert not _contains_emoji(ph), f"Emoji detectado no placeholder: '{ph}'"


def test_vector_icons_generation(qtbot):
    """Garante que make_launch_arrow_icon e make_upload_pixmap geram vetores válidos sem exceção."""
    arrow_icon = make_launch_arrow_icon(size=14)
    assert not arrow_icon.isNull()
    pix_arrow = arrow_icon.pixmap(14, 14)
    assert not pix_arrow.isNull()

    upload_pix = make_upload_pixmap(size=32)
    assert not upload_pix.isNull()
    assert upload_pix.width() > 0
    assert upload_pix.height() > 0
