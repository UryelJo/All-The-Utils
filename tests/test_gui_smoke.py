"""
Teste de fumaça da interface gráfica com pytest-qt.
Garante que a janela principal constrói e exibe sem exceções de UI.
"""
from wintoolbox.ui.main_window import MainWindow

def test_main_window_startup(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.windowTitle() == "Windows Toolbox"
    assert window.nav_list.count() >= 4  # Início + 3 ferramentas

    # Testa navegação programática para as páginas
    window.navigate_to("images.convert")
    assert window.stack.currentWidget() is not None

    window.navigate_to("system.tools")
    assert window.stack.currentWidget() is not None

    window.navigate_to("system.monitor")
    assert window.stack.currentWidget() is not None
