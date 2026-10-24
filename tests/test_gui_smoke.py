"""
Testes da interface gráfica modernizada (Fluent 2.0) com pytest-qt.
Valida MainWindow, Sidebar retrátil, Topbar/Breadcrumbs, Temas (Dark/Light/System),
Tela Inicial personalizável, Smart Drop Router, Busca Fuzzy e Micro-Componentes.
"""
from pathlib import Path
from PySide6.QtWidgets import QApplication

from wintoolbox.core.settings import get_home_layout, update_home_layout, add_favorite_tool
from wintoolbox.ui.icons import (
    get_app_icon, get_app_icon_path, get_app_pixmap,
    get_category_icon, make_fluent_icon, normalize_text
)
from wintoolbox.ui.main_window import MainWindow
from wintoolbox.ui.theme import apply_theme, build_tokens
from wintoolbox.ui.widgets.command_palette import CommandPaletteDialog
from wintoolbox.ui.widgets.setting_card import SettingCard
from wintoolbox.ui.widgets.smart_drop_dialog import find_compatible_tools_for_paths
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.toggle_switch import ToggleSwitch


def test_main_window_startup(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.windowTitle() == "All the Utils"
    assert not window.windowIcon().isNull()
    assert not window.tray_manager.tray.icon().isNull()
    assert get_app_icon_path() is not None
    assert not get_app_icon().isNull()
    assert not get_app_pixmap(32).isNull()
    assert window.tree_nav.topLevelItemCount() >= 5

    # Testa filtro instantâneo da sidebar (inclusive sem acento)
    window._filter_navigation("icone")
    window._filter_navigation("")

    # Testa navegação programática e Breadcrumb / Botão Voltar
    window.navigate_to("images.convert")
    assert window.stack.currentWidget() is not None
    assert "Conversor de Imagens" in window.lbl_breadcrumb.text()
    assert window.btn_back.isEnabled() is True

    window.navigate_to("system.tools")
    assert window.stack.currentWidget() is not None

    window.navigate_back()
    assert "Conversor de Imagens" in window.lbl_breadcrumb.text()

    window.navigate_to("system.monitor")
    assert window.stack.currentWidget() is not None

    window.navigate_to("settings")
    assert window.stack.currentWidget() is not None

    window.navigate_to("history")
    assert window.stack.currentWidget() is not None


def test_sidebar_collapse_and_theme_toggle(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.sidebar.width() in (260, 300)
    window.toggle_sidebar()
    assert window.sidebar.width() in (56, 60)
    window.toggle_sidebar()
    assert window.sidebar.width() in (260, 300)

    # Testa modos de organização da Sidebar: Categorias, Favoritos e A-Z
    window._set_sidebar_mode("az")
    assert window.tree_nav.topLevelItemCount() >= 50

    add_favorite_tool("images.convert")
    add_favorite_tool("system.tools")
    window._set_sidebar_mode("favorites")
    assert window.tree_nav.topLevelItemCount() == 2

    window._set_sidebar_mode("categories")
    assert window.tree_nav.topLevelItemCount() >= 5

    # Testa filtro de tipo na Sidebar (Lote vs Painel)
    window._set_sidebar_type_filter("batch")
    window._set_sidebar_type_filter("panel")
    window._set_sidebar_type_filter("all")

    # Testa busca por extensão de arquivo na Sidebar
    window._filter_navigation(".pdf")
    window._filter_navigation("")

    # Testa alternância de temas Dark / Light / System e cor de destaque
    app = QApplication.instance()
    apply_theme(app, mode="light", accent_override="#10b981")
    tokens_light = build_tokens("light", "#10b981")
    assert tokens_light.is_dark is False
    assert tokens_light.accent == "#10b981"

    apply_theme(app, mode="dark", accent_override="")
    tokens_dark = build_tokens("dark", "")
    assert tokens_dark.is_dark is True


def test_home_page_customization_and_density(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("home")

    # Alterna densidade para compacto e restaura confortável
    window.home_page._set_density("compact")
    assert get_home_layout()["card_density"] == "compact"

    window.home_page._set_density("comfortable")
    assert get_home_layout()["card_density"] == "comfortable"

    # Testa filtro de categoria por chip e busca na Home
    window.home_page._on_category_selected("Imagens")
    window.home_page._on_search_changed("webp")
    window.home_page._on_search_changed("")
    window.home_page._on_category_selected("ALL")

    # Testa personalização de visibilidade dos módulos da Home
    update_home_layout({"show_smart_drop": False, "show_system_health": False})
    window.home_page.refresh_home()
    assert window.home_page.smart_drop_banner.isHidden() is True
    assert window.home_page.health_banner.isHidden() is True

    update_home_layout({"show_smart_drop": True, "show_system_health": True})
    window.home_page.refresh_home()
    assert window.home_page.smart_drop_banner.isHidden() is False


def test_smart_drop_router_and_fuzzy_command_palette(qtbot, tmp_path: Path):
    pdf_file = tmp_path / "documento.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 dummy")
    tools_pdf = find_compatible_tools_for_paths([pdf_file])
    tool_ids = [t.id for t in tools_pdf]
    assert "pdf.compress" in tool_ids
    assert "pdf.split_merge" in tool_ids

    # Testa Command Palette com busca fuzzy / sem acentos
    dlg = CommandPaletteDialog()
    qtbot.addWidget(dlg)
    dlg._filter_tools("icone")
    assert dlg.list_results.count() >= 1
    dlg._filter_tools("")
    assert dlg.list_results.count() >= 50


def test_fluent_micro_components(qtbot):
    sw = ToggleSwitch("Ativar recurso")
    qtbot.addWidget(sw)
    assert sw.isChecked() is False
    sw.setChecked(True)
    assert sw.isChecked() is True

    card = SettingCard("settings", "Título de Teste", "Descrição secundária", sw)
    qtbot.addWidget(card)
    assert card.lbl_title.text() == "Título de Teste"

    toast = show_toast(card, "Sucesso", "Operação concluída", kind="success", duration_ms=500)
    assert toast is not None
    toast_err = show_toast(card, "Erro", "Falha de teste", is_error=True, duration_ms=500)
    assert toast_err is not None

    assert normalize_text("Conversão de Áudio e Vídeo") == "conversao de audio e video"
    assert not make_fluent_icon("home").isNull()
    assert not get_category_icon("Imagens").isNull()


def test_all_registered_tools_build_view(qtbot):
    """Garante que a UI de cada uma das 120 ferramentas registradas inicializa sem erros de construtor ou QWidget."""
    from wintoolbox.core.registry import get_all_tools
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    for tool in get_all_tools():
        window.navigate_to(tool.id)
        assert window.stack.currentWidget() is not None, f"Falha ao inicializar view da ferramenta {tool.id}"

