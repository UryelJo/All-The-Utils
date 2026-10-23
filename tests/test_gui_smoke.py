"""
Teste de fumaça da interface gráfica com pytest-qt.
Garante que a janela principal constrói, exibe e navega sem exceções de UI.
"""
from wintoolbox.ui.main_window import MainWindow


def test_main_window_startup(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.windowTitle() == "All the Utils"
    assert window.tree_nav.topLevelItemCount() >= 5

    # Testa filtro instantâneo da sidebar
    window._filter_navigation("pdf")
    # Deve encontrar itens e auto-expandir categorias correspondentes
    window._filter_navigation("")

    # Testa navegação programática para as páginas
    window.navigate_to("images.convert")
    assert window.stack.currentWidget() is not None

    window.navigate_to("system.tools")
    assert window.stack.currentWidget() is not None

    window.navigate_to("system.monitor")
    assert window.stack.currentWidget() is not None

    window.navigate_to("settings")
    assert window.stack.currentWidget() is not None
