"""
Inicialização e ciclo de vida da aplicação WinToolbox.
"""
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
from wintoolbox.ui.main_window import MainWindow
from wintoolbox.ui.theme import apply_theme

def run_gui():
    """Inicia a aplicação gráfica PySide6."""
    # Configuração de High-DPI no Qt
    app = QApplication(sys.argv)
    app.setApplicationName("All the Utils")
    app.setOrganizationName("All the Utils")

    # Carrega configurações salvas de tema
    st = load_settings()
    theme_mode = st.get("theme", "dark")
    apply_theme(app, mode=theme_mode)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
