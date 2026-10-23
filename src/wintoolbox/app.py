"""
Inicialização e ciclo de vida da aplicação WinToolbox.
"""
import ctypes
import gc
import sys
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from wintoolbox.core.logging_setup import (
    install_dialog_logging, install_qt_message_handler, setup_logging, uninstall_qt_message_handler
)
from wintoolbox.core.registry import get_all_tools
from wintoolbox.core.settings import load_settings
from wintoolbox.core.tasks import shutdown_tasks
from wintoolbox.core.single_instance import SingleInstanceServer, send_to_running_instance
from wintoolbox.ui.icons import get_app_icon
from wintoolbox.ui.main_window import MainWindow
from wintoolbox.ui.theme import apply_theme

def run_gui():
    """Inicia a aplicação gráfica PySide6."""
    # Antes de qualquer coisa: a central de logs captura inclusive falhas da inicialização
    setup_logging()
    install_qt_message_handler()
    install_dialog_logging()
    # Garante que a Barra de Tarefas do Windows exiba o ícone próprio do app em vez do python.exe
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AllTheUtils.WinToolbox.App.1")
    except Exception:
        pass
    app = QApplication(sys.argv)

    # Instância única: se o app já está aberto (ex: na bandeja), entrega os arquivos a ele
    if send_to_running_instance(sys.argv[1:]):
        sys.exit(0)
    instance_server = SingleInstanceServer(app)
    # Mutex nomeado: o instalador (AppMutex no installer.iss) detecta o app aberto
    _app_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "AllTheUtilsWinToolboxRunning")  # noqa: F841

    app.setApplicationName("All the Utils")
    app.setOrganizationName("All the Utils")
    app.setWindowIcon(get_app_icon())

    # Carrega configurações salvas de tema e cor de destaque
    st = load_settings()
    theme_mode = st.get("theme", "dark")
    accent_override = st.get("accent_override", "")
    apply_theme(app, mode=theme_mode, accent_override=accent_override)

    # Carrega as categorias pelo registro: uma dependência opcional ausente desativa
    # só a sua categoria em vez de impedir a abertura do app inteiro.
    get_all_tools()

    window = MainWindow()
    instance_server.message_received.connect(window.handle_external_args)
    window.show()
    app.aboutToQuit.connect(shutdown_tasks)
    app.aboutToQuit.connect(uninstall_qt_message_handler)

    exit_code = app.exec()

    # Destrói a janela com o Python ainda ativo. Deixar ~80 telas em cache (event filters,
    # sinais e timers em Python) para a finalização do interpretador causava 0xC0000005
    # intermitente ao fechar o app.
    if window.hotkey_mgr:
        window.hotkey_mgr.stop()
    window.tray_manager.tray.hide()
    window.deleteLater()
    del window
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()
    sys.exit(exit_code)
