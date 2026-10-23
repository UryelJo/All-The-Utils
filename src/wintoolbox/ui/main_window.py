"""
Janela Principal da Aplicação (MainWindow).
Sidebar modular e colapsável por categorias, busca instantânea, menus de contexto,
Lazy Loading, Bandeja do Sistema, Atalho Global e Drag & Drop.
"""
from pathlib import Path
import sys
from typing import Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QFont,
    QKeySequence, QShortcut
)
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMenu, QPushButton, QScrollArea, QStackedWidget,
    QStatusBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin
from wintoolbox.core.hotkey import GlobalHotkeyManager
from wintoolbox.core.registry import BaseTool, FileTool, Tool, get_all_tools, get_categories, get_tool
from wintoolbox.core.settings import (
    add_favorite_tool, add_recent_tool, is_favorite,
    load_settings, remove_favorite_tool
)
from wintoolbox.ui.pages.history_page import HistoryPage
from wintoolbox.ui.pages.home_page import HomePage
from wintoolbox.ui.pages.settings_page import SettingsPage
from wintoolbox.ui.tray import SystemTrayManager
from wintoolbox.ui.widgets.command_palette import CommandPaletteDialog
from wintoolbox.ui.widgets.tool_page import FileToolPage

CATEGORY_ICONS = {
    "Imagens": "🖼️",
    "Arquivos e Pastas": "📁",
    "Rede e Internet": "🌐",
    "Documentos e PDF": "📄",
    "Texto e Redação": "📝",
    "Codificação e Hash": "🔐",
    "Dados e Estruturas": "📊",
    "Áudio e Vídeo": "🎬",
    "Sistema Windows": "🛠️",
    "Compactação": "📦",
}


class MainWindow(QMainWindow):
    """Janela principal do All the Utils com sidebar em árvore colapsável."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("All the Utils")
        self.resize(1160, 740)
        self.setMinimumSize(940, 600)
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

        # 1. Sidebar Lateral com largura confortável de 280px
        sidebar = QFrame()
        sidebar.setObjectName("sidebarFrame")
        sidebar.setFixedWidth(280)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(14, 16, 14, 16)
        sb_layout.setSpacing(10)

        # Cabeçalho com Branding
        header_box = QVBoxLayout()
        header_box.setSpacing(2)

        lbl_app = QLabel("All the Utils")
        lbl_app.setStyleSheet("background: transparent; font-size: 17px; font-weight: 700; color: #ffffff;")
        header_box.addWidget(lbl_app)

        lbl_subtitle = QLabel("Caixa de Ferramentas Windows")
        lbl_subtitle.setStyleSheet("background: transparent; font-size: 11px; color: #8f8f9d;")
        header_box.addWidget(lbl_subtitle)
        sb_layout.addLayout(header_box)

        # Barra de Filtro / Busca Instantânea
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("🔍 Filtrar ferramentas... (Ctrl+K)")
        self.txt_filter.textChanged.connect(self._filter_navigation)
        sb_layout.addWidget(self.txt_filter)

        # Árvore de Navegação com Categorias Colapsáveis
        self.tree_nav = QTreeWidget()
        self.tree_nav.setObjectName("sidebarTree")
        self.tree_nav.setHeaderHidden(True)
        self.tree_nav.setAnimated(True)
        self.tree_nav.setIndentation(14)
        self.tree_nav.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_nav.customContextMenuRequested.connect(self._show_sidebar_context_menu)
        self.tree_nav.itemClicked.connect(self._on_tree_item_clicked)
        self.tree_nav.count = self.tree_nav.topLevelItemCount
        self.nav_list = self.tree_nav
        sb_layout.addWidget(self.tree_nav, stretch=1)

        self._populate_navigation()

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
        status.setStyleSheet("background-color: #1a1a1c; border-top: 1px solid #323238; font-size: 11px;")
        self.setStatusBar(status)

        admin_badge = "🛡️ Administrador" if is_admin() else "Usuário Padrão"
        tools_count = len(get_all_tools())
        self.lbl_status = QLabel(f"Modo: {admin_badge} | {tools_count} ferramentas ativas | Windows 64-bit | Pronto")
        self.lbl_status.setProperty("class", "secondary")
        status.addWidget(self.lbl_status)

    def _populate_navigation(self):
        """Popula a árvore com páginas do sistema, favoritos e categorias colapsáveis."""
        self.tree_nav.clear()

        # 1. Itens Fixos Principais
        item_home = QTreeWidgetItem(self.tree_nav)
        item_home.setText(0, "🏠  Início")
        item_home.setData(0, Qt.UserRole, "home")

        st = load_settings()
        favs = st.get("favorites", [])
        if favs:
            item_fav_cat = QTreeWidgetItem(self.tree_nav)
            item_fav_cat.setText(0, f"⭐  Favoritos ({len(favs)})")
            item_fav_cat.setData(0, Qt.UserRole, "category_favs")
            item_fav_cat.setFont(0, QFont("Segoe UI", 10, QFont.Bold))

            for fid in favs:
                tool = get_tool(fid)
                if tool:
                    child = QTreeWidgetItem(item_fav_cat)
                    child.setText(0, f"⭐ {tool.name}")
                    child.setData(0, Qt.UserRole, tool.id)
                    child.setToolTip(0, tool.description)
            item_fav_cat.setExpanded(True)

        item_hist = QTreeWidgetItem(self.tree_nav)
        item_hist.setText(0, "📜  Histórico de Tarefas")
        item_hist.setData(0, Qt.UserRole, "history")

        item_cfg = QTreeWidgetItem(self.tree_nav)
        item_cfg.setText(0, "⚙️  Configurações")
        item_cfg.setData(0, Qt.UserRole, "settings")

        # 2. Divisor de Categorias
        item_sep = QTreeWidgetItem(self.tree_nav)
        item_sep.setText(0, "─── FERRAMENTAS ───")
        item_sep.setFlags(Qt.NoItemFlags)
        item_sep.setForeground(0, Qt.darkGray)

        # 3. Categorias de Ferramentas Colapsáveis
        categories = get_categories()
        for cat_name, tools in categories.items():
            icon = CATEGORY_ICONS.get(cat_name, "📁")
            cat_item = QTreeWidgetItem(self.tree_nav)
            cat_item.setText(0, f"{icon}  {cat_name} ({len(tools)})")
            cat_item.setData(0, Qt.UserRole, f"category_{cat_name}")
            font = QFont("Segoe UI", 10, QFont.DemiBold)
            cat_item.setFont(0, font)

            for t in tools:
                child = QTreeWidgetItem(cat_item)
                child.setText(0, t.name)
                child.setData(0, Qt.UserRole, t.id)
                child.setToolTip(0, t.description)

            # Por padrão, deixa colapsado para visual limpo
            cat_item.setExpanded(False)

    def _filter_navigation(self, query: str):
        """Filtra dinamicamente as ferramentas e auto-expande categorias com correspondências."""
        q = query.strip().lower()
        if not q:
            # Restaura visual padrão
            for i in range(self.tree_nav.topLevelItemCount()):
                top = self.tree_nav.topLevelItem(i)
                top.setHidden(False)
                for j in range(top.childCount()):
                    top.child(j).setHidden(False)
                # Mantém categorias colapsadas por padrão exceto favoritos
                if top.data(0, Qt.UserRole) != "category_favs":
                    top.setExpanded(False)
            return

        for i in range(self.tree_nav.topLevelItemCount()):
            top = self.tree_nav.topLevelItem(i)
            # Se for item fixo (sem filhos)
            if top.childCount() == 0:
                top.setHidden(q not in top.text(0).lower())
                continue

            has_matching_children = False
            for j in range(top.childCount()):
                child = top.child(j)
                name_match = q in child.text(0).lower()
                tid = child.data(0, Qt.UserRole) or ""
                id_match = q in tid.lower()

                matches = name_match or id_match
                child.setHidden(not matches)
                if matches:
                    has_matching_children = True

            top.setHidden(not has_matching_children)
            if has_matching_children:
                top.setExpanded(True)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        # Se for uma categoria, alterna expandir/recolher
        if str(data).startswith("category_"):
            item.setExpanded(not item.isExpanded())
            return

        # Se for ferramenta ou página do sistema
        self.navigate_to(str(data))

    def _show_sidebar_context_menu(self, pos):
        """Exibe menu de contexto rico ao clicar com botão direito na sidebar."""
        item = self.tree_nav.itemAt(pos)
        menu = QMenu(self)

        if item:
            data = str(item.data(0, Qt.UserRole) or "")
            if data.startswith("category_"):
                # Menu de categoria
                a_expand_all = menu.addAction("Expandir Todas as Categorias")
                a_collapse_all = menu.addAction("Recolher Todas as Categorias")
                act = menu.exec(self.tree_nav.mapToGlobal(pos))
                if act == a_expand_all:
                    self.tree_nav.expandAll()
                elif act == a_collapse_all:
                    self.tree_nav.collapseAll()
                return

            if data not in ("home", "history", "settings") and not data.startswith("category_"):
                # Menu de ferramenta
                tool = get_tool(data)
                if tool:
                    fav_text = "❌ Remover dos Favoritos" if is_favorite(data) else "⭐ Adicionar aos Favoritos"
                    a_fav = menu.addAction(fav_text)
                    a_open = menu.addAction(f"Abrir '{tool.name}'")
                    menu.addSeparator()
                    a_copy_name = menu.addAction("Copiar Nome da Ferramenta")
                    a_copy_id = menu.addAction("Copiar Identificador (ID)")

                    act = menu.exec(self.tree_nav.mapToGlobal(pos))
                    if act == a_fav:
                        if is_favorite(data):
                            remove_favorite_tool(data)
                        else:
                            add_favorite_tool(data)
                        self._populate_navigation()
                    elif act == a_open:
                        self.navigate_to(data)
                    elif act == a_copy_name:
                        QApplication.clipboard().setText(tool.name)
                    elif act == a_copy_id:
                        QApplication.clipboard().setText(tool.id)
                    return

        # Menu padrão no espaço vazio
        a_exp = menu.addAction("Expandir Todas as Categorias")
        a_col = menu.addAction("Recolher Todas as Categorias")
        act = menu.exec(self.tree_nav.mapToGlobal(pos))
        if act == a_exp:
            self.tree_nav.expandAll()
        elif act == a_col:
            self.tree_nav.collapseAll()

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

        # Sincroniza a seleção na árvore da sidebar e auto-expande a categoria pai
        for i in range(self.tree_nav.topLevelItemCount()):
            top = self.tree_nav.topLevelItem(i)
            if top.data(0, Qt.UserRole) == view_id:
                self.tree_nav.setCurrentItem(top)
                break
            for j in range(top.childCount()):
                child = top.child(j)
                if child.data(0, Qt.UserRole) == view_id:
                    top.setExpanded(True)
                    self.tree_nav.setCurrentItem(child)
                    break

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
                "All the Utils",
                "O aplicativo continua em execução na bandeja do sistema."
            )
        else:
            if self.hotkey_mgr:
                self.hotkey_mgr.stop()
            event.accept()
