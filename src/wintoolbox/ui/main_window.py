"""
Janela Principal da Aplicação (MainWindow).
Sidebar modular, navegação dinâmica, barra de status e paleta de comandos Ctrl+K.
"""
from typing import Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QPushButton, QStackedWidget, QStatusBar, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin
from wintoolbox.core.registry import BaseTool, FileTool, Tool, get_all_tools, get_categories, get_tool
from wintoolbox.core.settings import load_settings, save_settings
from wintoolbox.ui.pages.home_page import HomePage
from wintoolbox.ui.theme import apply_theme
from wintoolbox.ui.widgets.command_palette import CommandPaletteDialog
from wintoolbox.ui.widgets.tool_page import FileToolPage

class MainWindow(QMainWindow):
    """Janela principal do WinToolbox."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Windows Toolbox")
        self.resize(1020, 680)
        self.setMinimumSize(880, 580)

        self._view_cache: Dict[str, QWidget] = {}
        self._build_ui()
        self._setup_shortcuts()

        # Abre a página inicial por padrão
        self.navigate_to("home")

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar Lateral
        sidebar = QFrame()
        sidebar.setFixedWidth(230)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-right: 1px solid #333333;
            }
        """)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 16, 12, 16)
        sb_layout.setSpacing(10)

        # Logo / Título
        lbl_app = QLabel("WinToolbox")
        lbl_app.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff; padding: 4px;")
        sb_layout.addWidget(lbl_app)

        # Botão de Busca Rápida (Ctrl+K)
        btn_search = QPushButton("Buscar... (Ctrl+K)")
        btn_search.setStyleSheet("text-align: left; padding: 6px 10px; font-size: 12px; color: #aaaaaa;")
        btn_search.clicked.connect(self._open_command_palette)
        sb_layout.addWidget(btn_search)

        # Lista de Navegação
        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                color: #cccccc;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 4px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #2e2e32;
            }
            QListWidget::item:selected {
                background-color: #094771;
                color: #ffffff;
                font-weight: 600;
            }
        """)
        self.nav_list.itemClicked.connect(self._on_nav_item_clicked)
        sb_layout.addWidget(self.nav_list, stretch=1)

        # Popula os itens da navegação
        item_home = QListWidgetItem("Início")
        item_home.setData(Qt.UserRole, "home")
        self.nav_list.addItem(item_home)

        # Ferramentas registradas
        for tool in get_all_tools():
            item = QListWidgetItem(tool.name)
            item.setData(Qt.UserRole, tool.id)
            self.nav_list.addItem(item)

        # Seletor de Tema no rodapé da sidebar
        lbl_theme = QLabel("Aparência:")
        lbl_theme.setProperty("class", "secondary")
        sb_layout.addWidget(lbl_theme)

        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems(["Escuro", "Claro"])
        self.cmb_theme.currentTextChanged.connect(self._on_theme_changed)
        sb_layout.addWidget(self.cmb_theme)

        main_layout.addWidget(sidebar)

        # 2. Área Central de Conteúdo (Stack)
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, stretch=1)

        # Registra página inicial no stack
        self.home_page = HomePage()
        self.home_page.tool_requested.connect(self.navigate_to)
        self.stack.addWidget(self.home_page)
        self._view_cache["home"] = self.home_page

        # 3. Barra de Status Inferior
        status = QStatusBar(self)
        status.setStyleSheet("background-color: #1e1e1e; border-top: 1px solid #333333; font-size: 11px;")
        self.setStatusBar(status)

        admin_text = "Administrador" if is_admin() else "Usuário Padrão"
        self.lbl_status = QLabel(f"Modo: {admin_text} | Windows 64-bit | Pronto")
        self.lbl_status.setProperty("class", "secondary")
        status.addWidget(self.lbl_status)

    def _setup_shortcuts(self):
        # Atalho Ctrl+K para busca
        shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        shortcut.activated.connect(self._open_command_palette)

    def _open_command_palette(self):
        dlg = CommandPaletteDialog(self)
        dlg.tool_selected.connect(self.navigate_to)
        dlg.exec()

    def navigate_to(self, view_id: str):
        if view_id not in self._view_cache:
            tool = get_tool(view_id)
            if not tool:
                return

            if isinstance(tool, FileTool):
                page = FileToolPage(tool, self)
            elif isinstance(tool, Tool):
                page = tool.build_view(self)
            else:
                return

            self._view_cache[view_id] = page
            self.stack.addWidget(page)

        # Exibe a página no stack
        page_widget = self._view_cache[view_id]
        self.stack.setCurrentWidget(page_widget)

        # Sincroniza a seleção na sidebar
        for i in range(self.nav_list.count()):
            item = self.nav_list.item(i)
            if item.data(Qt.UserRole) == view_id:
                self.nav_list.setCurrentItem(item)
                break

    def _on_nav_item_clicked(self, item: QListWidgetItem):
        view_id = item.data(Qt.UserRole)
        if view_id:
            self.navigate_to(view_id)

    def _on_theme_changed(self, text: str):
        mode = "dark" if text == "Escuro" else "light"
        from PySide6.QtWidgets import QApplication
        apply_theme(QApplication.instance(), mode)
        st = load_settings()
        st["theme"] = mode
        save_settings(st)
