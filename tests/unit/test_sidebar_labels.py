"""
Testes unitários para a simplificação de títulos da Sidebar e remoção da tag [Lote].
"""
from wintoolbox.core.registry import get_all_tools, get_tool
from wintoolbox.ui.main_window import MainWindow
from wintoolbox.ui.sidebar_labels import SIDEBAR_SHORT_LABELS, get_sidebar_tool_label


def test_all_registered_tools_have_compact_sidebar_labels():
    """Todas as ferramentas registradas devem ter rótulo conciso (<= 26 chars) e sem tag [Lote]."""
    tools = get_all_tools()
    assert len(tools) > 200

    for tool in tools:
        label = get_sidebar_tool_label(tool)
        assert label.strip() != "", f"Rótulo vazio para {tool.id}"
        assert "[Lote]" not in label, f"Tag [Lote] indevida no rótulo de {tool.id}"
        assert len(label) <= 26, f"Rótulo muito longo ({len(label)} chars) na sidebar para {tool.id}: '{label}'"
        assert tool.id in SIDEBAR_SHORT_LABELS, f"Ferramenta '{tool.id}' ausente de SIDEBAR_SHORT_LABELS"


def test_original_tool_names_preserved_outside_sidebar():
    """O nome completo da ferramenta (tool.name) deve permanecer intacto fora da sidebar."""
    img_conv = get_tool("images.convert")
    assert img_conv is not None
    assert img_conv.name == "Conversor de Imagens"
    assert get_sidebar_tool_label(img_conv) == "Conversor de Formatos"

    calc_inv = get_tool("calc.investments")
    assert calc_inv is not None
    assert "Simulador de Investimentos" in calc_inv.name
    assert get_sidebar_tool_label(calc_inv) == "Renda Fixa (CDB/Tesouro)"


def test_main_window_sidebar_format_removes_lote_tag(qtbot):
    """MainWindow._format_tool_label não deve incluir '[Lote]' e deve usar o rótulo simplificado."""
    win = MainWindow()
    qtbot.addWidget(win)

    img_conv = get_tool("images.convert")
    assert img_conv is not None
    assert win._format_tool_label(img_conv) == "Conversor de Formatos"
    assert "[Lote]" not in win._format_tool_label(img_conv)
    assert win._format_tool_label(img_conv, include_category=True) == "Conversor de Formatos (Imagens)"

    tooltip = win._build_tool_tooltip(img_conv)
    assert "Conversor de Imagens" in tooltip
    assert "Processamento em Lote" in tooltip

