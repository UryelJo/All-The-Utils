"""
Inicialização e ciclo de vida da aplicação WinToolbox.
"""
import ctypes
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import wintoolbox.tools.images
import wintoolbox.tools.system
import wintoolbox.tools.network
import wintoolbox.tools.text
import wintoolbox.tools.encode
import wintoolbox.tools.data
import wintoolbox.tools.files
import wintoolbox.tools.archive
import wintoolbox.tools.pdf
import wintoolbox.tools.media

from wintoolbox.core.settings import load_settings
from wintoolbox.ui.icons import get_app_icon
from wintoolbox.ui.main_window import MainWindow
from wintoolbox.ui.theme import apply_theme

def run_gui():
    """Inicia a aplicação gráfica PySide6."""
    # Garante que a Barra de Tarefas do Windows exiba o ícone próprio do app em vez do python.exe
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AllTheUtils.WinToolbox.App.1")
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName("All the Utils")
    app.setOrganizationName("All the Utils")
    app.setWindowIcon(get_app_icon())

    # Carrega configurações salvas de tema e cor de destaque
    st = load_settings()
    theme_mode = st.get("theme", "dark")
    accent_override = st.get("accent_override", "")
    apply_theme(app, mode=theme_mode, accent_override=accent_override)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
