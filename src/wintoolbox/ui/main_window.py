"""
Janela Principal da Aplicação (MainWindow).
Sidebar modular com Favoritos e Recentes, Lazy Loading, Bandeja, Atalho Global e Drag & Drop.
"""
import sys
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QPushButton, QStackedWidget, QStatusBar, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin
from wintoolbox.core.hotkey import GlobalHotkeyManager
from wintoolbox.core.registry import BaseTool, FileTool, Tool, get_all_tools, get_categories, get_tool
from wintoolbox.core.settings import add_recent_tool, load_settings
from wintoolbox.ui.pages.history_page import HistoryPage
from wintoolbox.ui.pages.home_page import HomePage
from wintoolbox.ui.pages.settings_page import SettingsPage
from wintoolbox.ui.tray import SystemTrayManager
from wintoolbox.ui.widgets.command_palette import CommandPaletteDialog
from wintoolbox.ui.widgets.tool_page import FileToolPage

class MainWindow(QMainWindow):
    """Janela principal do WinToolbox."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("All the Utils")
        self.resize(1040, 700)
        self.setMinimumSize(880, 580)
        self.setAcceptDrops(True)

        self._view_cache: Dict[str, QWidget] = {}
        self._build_ui()
        self._setup_shortcuts()
        self._setup_system_tray()
        self._setup_global_hotkey()

        # Abre a página inicial por padrão
        self.navigate_to("home")

        # Processa arquivos passados via linha de comando ou SendTo
        self._process_startup_args()

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
        sb_layout.setSpacing(8)

        # Título
        lbl_app = QLabel("All the Utils")
        lbl_app.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff; padding: 4px;")
        sb_layout.addWidget(lbl_app)

        # Botão de Busca Rápida (Ctrl+K)
        btn_search = QPushButton("Buscar... (Ctrl+K)")
        btn_search.setStyleSheet("text-align: left; padding: 6px 10px; font-size: 12px; color: #aaaaaa;")
        btn_search.clicked.connect(self._open_command_palette)
        sb_layout.addWidget(btn_search)

        # Lista de Navegação Principal
        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                color: #cccccc;
            }
            QListWidget::item {
                padding: 7px 10px;
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

        self._populate_navigation()

        main_layout.addWidget(sidebar)

        # 2. Área Central de Conteúdo (Stack)
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, stretch=1)

        # Registra página inicial no stack (carregamento leve inicial)
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

    def _populate_navigation(self):
        """Popula a navegação lateral com Início, Favoritos, Ferramentas, Histórico e Configurações."""
        self.nav_list.clear()

        # Início
        item_home = QListWidgetItem("Início")
        item_home.setData(Qt.UserRole, "home")
        self.nav_list.addItem(item_home)

        st = load_settings()

        # Favoritos
        favs = st.get("favorites", [])
        if favs:
            item_fav_hdr = QListWidgetItem("★ FAVORITOS")
            item_fav_hdr.setFlags(Qt.NoItemFlags)
            item_fav_hdr.setForeground(Qt.darkGray)
            self.nav_list.addItem(item_fav_hdr)

            for fid in favs:
                t = get_tool(fid)
                if t:
                    it = QListWidgetItem(f"  {t.name}")
                    it.setData(Qt.UserRole, t.id)
                    self.nav_list.addItem(it)

        # Todas as ferramentas
        item_tools_hdr = QListWidgetItem("FERRAMENTAS")
        item_tools_hdr.setFlags(Qt.NoItemFlags)
        item_tools_hdr.setForeground(Qt.darkGray)
        self.nav_list.addItem(item_tools_hdr)

        for tool in get_all_tools():
            it = QListWidgetItem(f"  {tool.name}")
            it.setData(Qt.UserRole, tool.id)
            self.nav_list.addItem(it)

        # Páginas do Sistema
        item_sys_hdr = QListWidgetItem("SISTEMA")
        item_sys_hdr.setFlags(Qt.NoItemFlags)
        item_sys_hdr.setForeground(Qt.darkGray)
        self.nav_list.addItem(item_sys_hdr)

        item_hist = QListWidgetItem("  Histórico de Tarefas")
        item_hist.setData(Qt.UserRole, "history")
        self.nav_list.addItem(item_hist)

        item_cfg = QListWidgetItem("  Configurações")
        item_cfg.setData(Qt.UserRole, "settings")
        self.nav_list.addItem(item_cfg)

    def _setup_shortcuts(self):
        shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        shortcut.activated.connect(self._open_command_palette)

    def _setup_system_tray(self):
        self.tray_manager = SystemTrayManager(
            on_show_window=self.restore_window,
            on_open_tool=self.navigate_to,
            on_search=self._open_command_palette
        )

    def _setup_global_hotkey(self):
        st = load_settings()
        if st.get("global_hotkey_enabled", True):
            self.hotkey_mgr = GlobalHotkeyManager(callback=self.restore_window)
            self.hotkey_mgr.start()
        else:
            self.hotkey_mgr = None

    def restore_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _open_command_palette(self):
        dlg = CommandPaletteDialog(self)
        dlg.tool_selected.connect(self.navigate_to)
        dlg.exec()

    def navigate_to(self, view_id: str):
        """Lazy loading: só instancia e carrega a tela no momento em que é solicitada."""
        if view_id == "history":
            if "history" not in self._view_cache:
                hp = HistoryPage(self)
                self._view_cache["history"] = hp
                self.stack.addWidget(hp)
            self._view_cache["history"].refresh()
        elif view_id == "settings":
            if "settings" not in self._view_cache:
                sp = SettingsPage(self)
                sp.settings_changed.connect(self._on_settings_updated)
                self._view_cache["settings"] = sp
                self.stack.addWidget(sp)
        elif view_id != "home" and view_id not in self._view_cache:
            tool = get_tool(view_id)
            if not tool:
                return

            if isinstance(tool, FileTool):
                page = FileToolPage(tool, self)
                page.favorite_toggled.connect(lambda tid, is_fav: self._populate_navigation())
                page.task_completed.connect(self._on_task_completed)
            elif isinstance(tool, Tool):
                page = tool.build_view(self)
            else:
                return

            self._view_cache[view_id] = page
            self.stack.addWidget(page)
            add_recent_tool(view_id)

        # Exibe a página solicitada
        if view_id in self._view_cache:
            self.stack.setCurrentWidget(self._view_cache[view_id])

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

    def _on_task_completed(self, title: str, message: str, is_error: bool):
        self.tray_manager.notify(title, message, is_error)

    def _on_settings_updated(self):
        self._populate_navigation()
        self.tray_manager.refresh_menu()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        """Drop global: arrastar arquivos soltos em qualquer lugar da janela principal."""
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if Path(u.toLocalFile()).exists()]
        if not paths:
            return

        # Identifica se são imagens para abrir direto o conversor
        image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".ico", ".tiff"}
        has_images = any(p.is_dir() or p.suffix.lower() in image_exts for p in paths)

        if has_images:
            self.navigate_to("images.convert")
            page = self._view_cache.get("images.convert")
            if isinstance(page, FileToolPage):
                page.add_paths(paths)

    def _process_startup_args(self):
        """Recebe caminhos passados pelo Windows via 'Enviar para' ou terminal."""
        if len(sys.argv) > 1:
            paths = [Path(arg) for arg in sys.argv[1:] if Path(arg).exists()]
            if paths:
                self.navigate_to("images.convert")
                page = self._view_cache.get("images.convert")
                if isinstance(page, FileToolPage):
                    page.add_paths(paths)

    def closeEvent(self, event: QCloseEvent):
        st = load_settings()
        if st.get("minimize_to_tray", True):
            event.ignore()
            self.hide()
            self.tray_manager.notify(
                "WinToolbox",
                "O aplicativo continua em execução na bandeja do sistema."
            )
        else:
            if self.hotkey_mgr:
                self.hotkey_mgr.stop()
            event.accept()
