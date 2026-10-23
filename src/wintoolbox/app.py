"""
Inicialização e ciclo de vida da aplicação WinToolbox.
"""
import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Importa as ferramentas para disparar os decoradores @register
import wintoolbox.tools.images.convert
import wintoolbox.tools.system.tools
import wintoolbox.tools.system.monitor
import wintoolbox.tools.network
import wintoolbox.tools.text
import wintoolbox.tools.encode
import wintoolbox.tools.data
import wintoolbox.tools.files
import wintoolbox.tools.archive

from wintoolbox.core.settings import load_settings
from wintoolbox.ui.main_window import MainWindow
from wintoolbox.ui.theme import apply_theme

def run_gui():
    """Inicia a aplicação gráfica PySide6."""
    # Configuração de High-DPI no Qt
    app = QApplication(sys.argv)
    app.setApplicationName("WinToolbox")
    app.setOrganizationName("WinToolbox")

    # Carrega configurações salvas de tema
    st = load_settings()
    theme_mode = st.get("theme", "dark")
    apply_theme(app, mode=theme_mode)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
