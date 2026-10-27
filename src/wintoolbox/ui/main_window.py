"""
Janela Principal da Aplicação (MainWindow) - App Shell Fluent 2.0.
Sidebar estruturada em 3 zonas (Topo Fixo com Busca Fuzzy/Extensões e Modos de Visão,
Árvore/Lista Organizada por Categorias/Favoritos/A-Z + Filtro Lote/Painel, e Dock Inferior Fixo),
100% livre de emojis.
"""
from pathlib import Path
import sys
from typing import Dict, List, Optional
from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import (
    QCloseEvent, QDragEnterEvent, QDropEvent, QFont,
    QKeySequence, QShortcut
)
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMenu, QPushButton, QScrollArea, QStackedWidget,
    QStatusBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
)
from rapidfuzz import fuzz

from wintoolbox.core.elevation import is_admin
from wintoolbox.core.hotkey import GlobalHotkeyManager
from wintoolbox.core.registry import BaseTool, FileTool, Tool, get_all_tools, get_categories, get_tool
from wintoolbox.core.search import calculate_tool_relevance
from wintoolbox.core.settings import (
    add_favorite_tool, add_recent_tool, get_home_layout, is_favorite,
    load_settings, remove_favorite_tool, save_settings
)
from wintoolbox.ui.icons import (
    get_app_icon, get_app_pixmap, get_category_icon, make_fluent_icon, normalize_text
)
from wintoolbox.ui.pages.debug_page import DebugPage
from wintoolbox.ui.pages.history_page import HistoryPage
from wintoolbox.ui.pages.home_page import HomePage
from wintoolbox.ui.pages.settings_page import SettingsPage
from wintoolbox.ui.theme import apply_theme, get_current_tokens
from wintoolbox.ui.tray import SystemTrayManager
from wintoolbox.ui.widgets.command_palette import CommandPaletteDialog
from wintoolbox.ui.widgets.smart_drop_dialog import SmartDropDialog, find_compatible_tools_for_paths
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_page import FileToolPage


class MainWindow(QMainWindow):
    """Janela principal do All the Utils com Sidebar avançada em 3 zonas e Topbar contextual."""

    # Emitido pela thread do atalho global; a conexão enfileirada executa na thread da UI
    hotkey_triggered = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("All the Utils")
        self.setWindowIcon(get_app_icon())
        self.resize(1220, 770)
        self.setMinimumSize(960, 620)
        self.setAcceptDrops(True)

        self._view_cache: Dict[str, QWidget] = {}
        self._nav_history: List[str] = []
        self._current_view_id: str = "home"
        self._active_jobs: Dict[str, str] = {}
        self._sidebar_collapsed: bool = False

        # Estado de organização e filtros da Sidebar
        self._sidebar_mode: str = "categories"  # 'categories' | 'favorites' | 'az'
        self._sidebar_type_filter: str = "all"  # 'all' | 'batch' | 'panel'
        self._accordion_mode: bool = False      # Se True, abrir uma categoria recolhe as demais

        self._build_ui()
        self._setup_shortcuts()
        self._setup_system_tray()
        self._setup_global_hotkey()

        # Verifica preferência de tela inicial ao abrir o app
        hl = get_home_layout()
        last_tool = hl.get("last_opened_tool", "")
        if hl.get("startup_view") == "last_tool" and last_tool and get_tool(last_tool):
            self.navigate_to(last_tool)
        else:
            self.navigate_to("home")

        # Processa arquivos passados via linha de comando ou SendTo
        self._process_startup_args()

    def _build_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 1. Sidebar Lateral Sólida (260px expandida ↔ 56px colapsada) ──
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebarFrame")
        self.sidebar.setFixedWidth(260)
        sb_outer_layout = QVBoxLayout(self.sidebar)
        sb_outer_layout.setContentsMargins(0, 0, 0, 0)
        sb_outer_layout.setSpacing(0)

        self.sb_stack = QStackedWidget(self.sidebar)
        sb_outer_layout.addWidget(self.sb_stack)

        # ── [VISÃO 0: SIDEBAR EXPANDIDA - 260px] ──
        self.sb_expanded = QWidget()
        l_exp = QVBoxLayout(self.sb_expanded)
        l_exp.setContentsMargins(10, 10, 10, 10)
        l_exp.setSpacing(6)

        # Topo: Marca e Botão de Recolher
        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)

        self.lbl_brand_logo = QLabel()
        self.lbl_brand_logo.setPixmap(get_app_pixmap(22))
        self.lbl_brand_logo.setFixedSize(22, 22)
        brand_row.addWidget(self.lbl_brand_logo)

        self.lbl_app = QLabel("All the Utils")
        self.lbl_app.setStyleSheet("font-size: 14px; font-weight: 700; background: transparent;")
        brand_row.addWidget(self.lbl_app)
        brand_row.addStretch()

        self.btn_collapse_sb = QPushButton("<<")
        self.btn_collapse_sb.setProperty("class", "ghost")
        self.btn_collapse_sb.setFixedSize(30, 26)
        self.btn_collapse_sb.setToolTip("Recolher barra lateral (Ctrl+B)")
        self.btn_collapse_sb.clicked.connect(self.toggle_sidebar)
        brand_row.addWidget(self.btn_collapse_sb)
        l_exp.addLayout(brand_row)

        # Navegação de Topo Limpa (Início e Histórico)
        self.btn_nav_home = QPushButton("Início")
        self.btn_nav_home.setIcon(make_fluent_icon("home", size=15))
        self.btn_nav_home.setProperty("class", "nav-item")
        self.btn_nav_home.setCursor(Qt.PointingHandCursor)
        self.btn_nav_home.clicked.connect(lambda: self.navigate_to("home"))
        l_exp.addWidget(self.btn_nav_home)

        self.btn_nav_history = QPushButton("Histórico de Tarefas")
        self.btn_nav_history.setIcon(make_fluent_icon("history", size=15))
        self.btn_nav_history.setProperty("class", "nav-item")
        self.btn_nav_history.setCursor(Qt.PointingHandCursor)
        self.btn_nav_history.clicked.connect(lambda: self.navigate_to("history"))
        l_exp.addWidget(self.btn_nav_history)

        # Divisor sutil
        div1 = QFrame()
        div1.setFixedHeight(1)
        div1.setStyleSheet("background-color: rgba(128, 128, 128, 0.2);")
        l_exp.addWidget(div1)

        # Caixa de busca compacta
        self.txt_filter = QLineEdit()
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.setPlaceholderText("Filtrar ferramentas... (Ctrl+K)")
        self.txt_filter.textChanged.connect(self._filter_navigation)
        self.txt_filter.returnPressed.connect(self._activate_first_visible_tool)
        self.txt_filter.installEventFilter(self)
        l_exp.addWidget(self.txt_filter)

        self.lbl_nav_counter = QLabel("")
        self.lbl_nav_counter.setProperty("class", "secondary")
        self.lbl_nav_counter.setStyleSheet("font-size: 11px; padding: 2px 4px; color: #a1a1aa;")
        self.lbl_nav_counter.setVisible(False)
        l_exp.addWidget(self.lbl_nav_counter)

        # Árvore de ferramentas categorizadas
        self.tree_nav = QTreeWidget()
        self.tree_nav.setObjectName("sidebarTree")
        self.tree_nav.setHeaderHidden(True)
        self.tree_nav.setAnimated(True)
        self.tree_nav.setIndentation(12)
        self.tree_nav.setIconSize(QSize(14, 14))
        self.tree_nav.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_nav.customContextMenuRequested.connect(self._show_sidebar_context_menu)
        self.tree_nav.itemClicked.connect(self._on_tree_item_clicked)
        self.tree_nav.itemActivated.connect(lambda item, col: self._on_tree_item_clicked(item, col))
        self.tree_nav.count = self.tree_nav.topLevelItemCount
        self.nav_list = self.tree_nav
        l_exp.addWidget(self.tree_nav, stretch=1)

        # Rodapé fixo com Configurações
        div2 = QFrame()
        div2.setFixedHeight(1)
        div2.setStyleSheet("background-color: rgba(128, 128, 128, 0.2);")
        l_exp.addWidget(div2)

        self.btn_nav_debug = QPushButton("Depuração e Logs")
        self.btn_nav_debug.setIcon(make_fluent_icon("debug", size=15))
        self.btn_nav_debug.setProperty("class", "nav-item")
        self.btn_nav_debug.setCursor(Qt.PointingHandCursor)
        self.btn_nav_debug.setToolTip("Logs centralizados, verbosidade das bibliotecas e diagnóstico (Ctrl+Shift+D)")
        self.btn_nav_debug.clicked.connect(lambda: self.navigate_to("debug"))
        l_exp.addWidget(self.btn_nav_debug)

        self.btn_nav_settings = QPushButton("Configurações")
        self.btn_nav_settings.setIcon(make_fluent_icon("settings", size=15))
        self.btn_nav_settings.setProperty("class", "nav-item")
        self.btn_nav_settings.setCursor(Qt.PointingHandCursor)
        self.btn_nav_settings.setToolTip("Configurações, Aparência e Chaves de API")
        self.btn_nav_settings.clicked.connect(lambda: self.navigate_to("settings"))
        l_exp.addWidget(self.btn_nav_settings)

        self.sb_stack.addWidget(self.sb_expanded)

        # ── [VISÃO 1: SIDEBAR COLAPSADA - 56px] ──
        self.sb_collapsed = QWidget()
        l_col = QVBoxLayout(self.sb_collapsed)
        l_col.setContentsMargins(6, 10, 6, 10)
        l_col.setSpacing(6)
        l_col.setAlignment(Qt.AlignHCenter)

        self.btn_expand_sb = QPushButton(">>")
        self.btn_expand_sb.setProperty("class", "ghost")
        self.btn_expand_sb.setFixedSize(36, 28)
        self.btn_expand_sb.setToolTip("Expandir barra lateral (Ctrl+B)")
        self.btn_expand_sb.clicked.connect(self.toggle_sidebar)
        l_col.addWidget(self.btn_expand_sb)

        self.btn_col_home = QPushButton()
        self.btn_col_home.setIcon(make_fluent_icon("home", size=16))
        self.btn_col_home.setProperty("class", "nav-icon-btn")
        self.btn_col_home.setFixedSize(36, 36)
        self.btn_col_home.setToolTip("Painel Inicial (Início)")
        self.btn_col_home.setCursor(Qt.PointingHandCursor)
        self.btn_col_home.clicked.connect(lambda: self.navigate_to("home"))
        l_col.addWidget(self.btn_col_home)

        self.btn_col_search = QPushButton()
        self.btn_col_search.setIcon(make_fluent_icon("search", size=16))
        self.btn_col_search.setProperty("class", "nav-icon-btn")
        self.btn_col_search.setFixedSize(36, 36)
        self.btn_col_search.setToolTip("Buscar Ferramentas (Ctrl+K)")
        self.btn_col_search.setCursor(Qt.PointingHandCursor)
        self.btn_col_search.clicked.connect(self._open_command_palette)
        l_col.addWidget(self.btn_col_search)

        self.btn_col_history = QPushButton()
        self.btn_col_history.setIcon(make_fluent_icon("history", size=16))
        self.btn_col_history.setProperty("class", "nav-icon-btn")
        self.btn_col_history.setFixedSize(36, 36)
        self.btn_col_history.setToolTip("Histórico de Tarefas")
        self.btn_col_history.setCursor(Qt.PointingHandCursor)
        self.btn_col_history.clicked.connect(lambda: self.navigate_to("history"))
        l_col.addWidget(self.btn_col_history)

        div_col = QFrame()
        div_col.setFixedHeight(1)
        div_col.setFixedWidth(36)
        div_col.setStyleSheet("background-color: rgba(128, 128, 128, 0.2);")
        l_col.addWidget(div_col)

        # Área de categorias em botões compactos
        cat_scroll = QScrollArea()
        cat_scroll.setWidgetResizable(True)
        cat_scroll.setFrameShape(QScrollArea.NoFrame)
        cat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cat_scroll.setFixedWidth(44)
        cat_w = QWidget()
        self.cat_col_layout = QVBoxLayout(cat_w)
        self.cat_col_layout.setContentsMargins(0, 0, 0, 0)
        self.cat_col_layout.setSpacing(4)
        self.cat_col_layout.setAlignment(Qt.AlignHCenter)
        cat_scroll.setWidget(cat_w)
        l_col.addWidget(cat_scroll, stretch=1)

        self.btn_col_debug = QPushButton()
        self.btn_col_debug.setIcon(make_fluent_icon("debug", size=16))
        self.btn_col_debug.setProperty("class", "nav-icon-btn")
        self.btn_col_debug.setFixedSize(36, 36)
        self.btn_col_debug.setToolTip("Depuração e Logs (Ctrl+Shift+D)")
        self.btn_col_debug.setCursor(Qt.PointingHandCursor)
        self.btn_col_debug.clicked.connect(lambda: self.navigate_to("debug"))
        l_col.addWidget(self.btn_col_debug)

        self.btn_col_settings = QPushButton()
        self.btn_col_settings.setIcon(make_fluent_icon("settings", size=16))
        self.btn_col_settings.setProperty("class", "nav-icon-btn")
        self.btn_col_settings.setFixedSize(36, 36)
        self.btn_col_settings.setToolTip("Configurações do Sistema")
        self.btn_col_settings.setCursor(Qt.PointingHandCursor)
        self.btn_col_settings.clicked.connect(lambda: self.navigate_to("settings"))
        l_col.addWidget(self.btn_col_settings)

        self.sb_stack.addWidget(self.sb_collapsed)

        self._populate_navigation()
        main_layout.addWidget(self.sidebar)

        # ── 2. Coluna Direita: Topbar Contextual + Stack Central ──
        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(0)

        # Topbar Contextual limpa
        self.topbar = QFrame()
        self.topbar.setObjectName("topbarFrame")
        self.topbar.setFixedHeight(46)
        tb_layout = QHBoxLayout(self.topbar)
        tb_layout.setContentsMargins(16, 6, 16, 6)
        tb_layout.setSpacing(8)

        self.btn_back = QPushButton("Voltar")
        self.btn_back.setProperty("class", "ghost")
        self.btn_back.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.btn_back.setToolTip("Voltar para a tela anterior (Alt+Esquerda)")
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self.navigate_back)
        tb_layout.addWidget(self.btn_back)

        self.lbl_breadcrumb = QLabel("Início")
        self.lbl_breadcrumb.setStyleSheet("font-size: 13px; font-weight: 600; padding-left: 6px;")
        tb_layout.addWidget(self.lbl_breadcrumb)

        tb_layout.addStretch()

        # Pílula de Tarefas em Execução
        self.btn_active_jobs = QPushButton("")
        self.btn_active_jobs.setProperty("class", "primary")
        self.btn_active_jobs.setVisible(False)
        self.btn_active_jobs.setStyleSheet("font-size: 12px; padding: 4px 12px; border-radius: 12px;")
        self.btn_active_jobs.clicked.connect(self._jump_to_active_job)
        tb_layout.addWidget(self.btn_active_jobs)

        # Botão de Busca Rápida (Command Palette)
        self.btn_search_top = QPushButton("Busca Rápida (Ctrl+K)")
        self.btn_search_top.setMinimumWidth(180)
        self.btn_search_top.setStyleSheet("text-align: center; padding: 4px 12px; font-size: 12px;")
        self.btn_search_top.clicked.connect(self._open_command_palette)
        tb_layout.addWidget(self.btn_search_top)

        # Alternador Rápido de Tema (Escuro / Claro)
        self.btn_theme_toggle = QPushButton("Alternar Tema")
        self.btn_theme_toggle.setProperty("class", "ghost")
        self.btn_theme_toggle.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.btn_theme_toggle.setToolTip("Alternar entre Modo Escuro e Modo Claro")
        self.btn_theme_toggle.clicked.connect(self._quick_toggle_theme)
        tb_layout.addWidget(self.btn_theme_toggle)

        right_column.addWidget(self.topbar)

        # Área Central de Conteúdo (Stack)
        self.stack = QStackedWidget()
        right_column.addWidget(self.stack, stretch=1)

        main_layout.addLayout(right_column, stretch=1)

        # Registra página inicial no stack
        self.home_page = HomePage()
        self.home_page.tool_requested.connect(self.navigate_to)
        self.home_page.favorite_changed.connect(self._populate_navigation)
        self.home_page.files_dropped.connect(lambda paths: self.route_dropped_paths(paths, interactive=True))
        self.stack.addWidget(self.home_page)
        self._view_cache["home"] = self.home_page

        # ── 3. Barra de Status Inferior ──
        status = QStatusBar(self)
        self.setStatusBar(status)

        admin_badge = "Administrador" if is_admin() else "Usuário Padrão"
        tools_count = len(get_all_tools())
        self.lbl_status = QLabel(f"Modo: {admin_badge}  |  {tools_count} ferramentas ativas  |  Windows 64-bit  |  Pronto")
        self.lbl_status.setProperty("class", "secondary")
        status.addWidget(self.lbl_status)

    def eventFilter(self, obj, event) -> bool:
        """Permite descer do campo de busca direto para a árvore de resultados com a seta para baixo."""
        if obj is self.txt_filter and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Down:
                self.tree_nav.setFocus()
                return True
        return super().eventFilter(obj, event)

    def toggle_sidebar(self) -> None:
        """Alterna entre a sidebar expandida (260px) e o modo compacto (56px)."""
        self._sidebar_collapsed = not self._sidebar_collapsed
        if self._sidebar_collapsed:
            self.sidebar.setFixedWidth(56)
            self.sb_stack.setCurrentIndex(1)
        else:
            self.sidebar.setFixedWidth(260)
            self.sb_stack.setCurrentIndex(0)

    def _on_collapsed_category_clicked(self, cat_name: str) -> None:
        """Ao clicar no ícone da categoria na sidebar colapsada, expande e foca na categoria."""
        if self._sidebar_collapsed:
            self.toggle_sidebar()
        for i in range(self.tree_nav.topLevelItemCount()):
            item = self.tree_nav.topLevelItem(i)
            if item.data(0, Qt.UserRole) == f"category_{cat_name}":
                item.setExpanded(True)
                self.tree_nav.setCurrentItem(item)
                self.tree_nav.scrollToItem(item)
                break

    def _set_sidebar_mode(self, mode: str) -> None:
        """Compatibilidade: alterna modo de visualização."""
        self._sidebar_mode = mode
        self._populate_navigation()

    def _set_sidebar_type_filter(self, type_filter: str) -> None:
        """Compatibilidade: filtra por tipo."""
        self._sidebar_type_filter = type_filter
        self._populate_navigation()

    def _matches_type_filter(self, tool: BaseTool) -> bool:
        if self._sidebar_type_filter == "batch":
            return isinstance(tool, FileTool)
        if self._sidebar_type_filter == "panel":
            return not isinstance(tool, FileTool)
        return True

    def _format_tool_label(self, tool: BaseTool, include_category: bool = False) -> str:
        tool_name = (getattr(tool, "name", "") or getattr(tool, "title", "") or tool.id).strip()
        parts = [tool_name]
        if include_category:
            parts.append(f"({tool.category})")
        if isinstance(tool, FileTool):
            parts.append("[Lote]")
        return "  ".join(parts)

    def _build_tool_tooltip(self, tool: BaseTool) -> str:
        kind = "Processamento em Lote" if isinstance(tool, FileTool) else "Painel Interativo"
        lines = [
            f"{tool.name}",
            f"Categoria: {tool.category}  |  {kind}",
            f"{tool.description}",
        ]
        if isinstance(tool, FileTool) and tool.accepts:
            lines.append(f"Extensões aceitas: {', '.join(tool.accepts)}")
        return "\n".join(lines)

    def _populate_navigation(self) -> None:
        """Popula a árvore da sidebar expandida e a coluna de ícones da sidebar colapsada."""
        self.tree_nav.clear()
        st = load_settings()
        fav_ids = st.get("favorites", [])

        if getattr(self, "_sidebar_mode", "categories") == "az":
            tools = [t for t in sorted(get_all_tools(), key=lambda x: normalize_text(x.name)) if self._matches_type_filter(t)]
            for tool in tools:
                item = QTreeWidgetItem(self.tree_nav)
                item.setText(0, self._format_tool_label(tool, include_category=True))
                item.setIcon(0, get_category_icon(tool.category, size=14))
                item.setData(0, Qt.UserRole, tool.id)
                item.setToolTip(0, self._build_tool_tooltip(tool))
            return

        if getattr(self, "_sidebar_mode", "categories") == "favorites":
            fav_tools = [get_tool(fid) for fid in fav_ids if get_tool(fid) and self._matches_type_filter(get_tool(fid))]
            for tool in fav_tools:
                item = QTreeWidgetItem(self.tree_nav)
                item.setText(0, self._format_tool_label(tool, include_category=True))
                item.setIcon(0, make_fluent_icon("star_filled", "#eab308", 14))
                item.setData(0, Qt.UserRole, tool.id)
                item.setToolTip(0, self._build_tool_tooltip(tool))
            return

        # 1. Popula categorias na árvore expandida
        if fav_ids:
            fav_tools = [get_tool(fid) for fid in fav_ids if get_tool(fid) and self._matches_type_filter(get_tool(fid))]
            if fav_tools:
                item_fav_cat = QTreeWidgetItem(self.tree_nav)
                item_fav_cat.setText(0, f"Favoritos ({len(fav_tools)})")
                item_fav_cat.setIcon(0, make_fluent_icon("star_filled", "#eab308", 14))
                item_fav_cat.setData(0, Qt.UserRole, "category_favs")
                item_fav_cat.setFont(0, QFont("Segoe UI", 10, QFont.DemiBold))

                for tool in fav_tools:
                    child = QTreeWidgetItem(item_fav_cat)
                    child.setText(0, self._format_tool_label(tool))
                    child.setData(0, Qt.UserRole, tool.id)
                    child.setToolTip(0, self._build_tool_tooltip(tool))
                item_fav_cat.setExpanded(True)

        categories = get_categories()
        for cat_name, tools in categories.items():
            cat_tools = [t for t in tools if self._matches_type_filter(t)]
            if not cat_tools:
                continue

            cat_item = QTreeWidgetItem(self.tree_nav)
            cat_item.setText(0, f"{cat_name} ({len(cat_tools)})")
            cat_item.setIcon(0, get_category_icon(cat_name, size=14))
            cat_item.setData(0, Qt.UserRole, f"category_{cat_name}")
            cat_item.setFont(0, QFont("Segoe UI", 10, QFont.DemiBold))
            cat_item.setToolTip(0, f"{cat_name} ({len(cat_tools)} ferramentas)")

            for tool in cat_tools:
                child = QTreeWidgetItem(cat_item)
                child.setText(0, self._format_tool_label(tool))
                child.setData(0, Qt.UserRole, tool.id)
                child.setToolTip(0, self._build_tool_tooltip(tool))

            cat_item.setExpanded(False)

        # 2. Popula botões de categoria na sidebar colapsada
        if hasattr(self, "cat_col_layout"):
            while self.cat_col_layout.count():
                item = self.cat_col_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            for cat_name, tools in categories.items():
                btn_cat = QPushButton()
                btn_cat.setIcon(get_category_icon(cat_name, size=16))
                btn_cat.setProperty("class", "nav-icon-btn")
                btn_cat.setFixedSize(36, 36)
                btn_cat.setCursor(Qt.PointingHandCursor)
                btn_cat.setToolTip(f"{cat_name} ({len(tools)} ferramentas)")
                btn_cat.clicked.connect(lambda _, c=cat_name: self._on_collapsed_category_clicked(c))
                self.cat_col_layout.addWidget(btn_cat)

    def _tool_matches_query(self, tool: BaseTool, q: str) -> bool:
        """Verifica se a ferramenta corresponde à busca com pontuação de relevância."""
        return calculate_tool_relevance(tool, q) > 0

    def _filter_navigation(self, query: str) -> None:
        """Filtra dinamicamente as ferramentas priorizando Nome > Descrição e auto-expande categorias com resultados."""
        q = query.strip()

        if not q:
            self._populate_navigation()
            if hasattr(self, "lbl_nav_counter"):
                self.lbl_nav_counter.setVisible(False)
                self.lbl_nav_counter.setText("")
            return

        matched_count = 0
        for i in range(self.tree_nav.topLevelItemCount()):
            top = self.tree_nav.topLevelItem(i)
            # No modo A-Z, os itens de topo já são as próprias ferramentas
            if top.childCount() == 0:
                tid = str(top.data(0, Qt.UserRole) or "")
                tool = get_tool(tid)
                matches = self._tool_matches_query(tool, q) if tool else (calculate_tool_relevance(tool, q) > 0 if tool else False)
                top.setHidden(not matches)
                if matches:
                    matched_count += 1
                continue

            has_matching_children = False
            children_with_score = []
            for j in range(top.childCount()):
                child = top.child(j)
                tid = str(child.data(0, Qt.UserRole) or "")
                tool = get_tool(tid)
                score = calculate_tool_relevance(tool, q) if tool else 0
                matches = score > 0
                child.setHidden(not matches)
                if matches:
                    has_matching_children = True
                    matched_count += 1
                    children_with_score.append((child, score))

            top.setHidden(not has_matching_children)
            if has_matching_children:
                top.setExpanded(True)

        if hasattr(self, "lbl_nav_counter"):
            self.lbl_nav_counter.setText(f"{matched_count} resultado(s) para '{q}'")
            self.lbl_nav_counter.setVisible(True)

    def _activate_first_visible_tool(self) -> None:
        """Abre imediatamente a primeira ferramenta visível ao pressionar Enter na busca da sidebar."""
        for i in range(self.tree_nav.topLevelItemCount()):
            top = self.tree_nav.topLevelItem(i)
            if top.isHidden():
                continue
            if top.childCount() == 0:
                tid = str(top.data(0, Qt.UserRole) or "")
                if tid and not tid.startswith("category_"):
                    self.navigate_to(tid)
                    return
            for j in range(top.childCount()):
                child = top.child(j)
                if not child.isHidden():
                    tid = str(child.data(0, Qt.UserRole) or "")
                    if tid:
                        self.navigate_to(tid)
                        return

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        if str(data).startswith("category_"):
            if self._sidebar_collapsed:
                self.toggle_sidebar()
                item.setExpanded(True)
            else:
                will_expand = not item.isExpanded()
                if will_expand and self._accordion_mode:
                    for i in range(self.tree_nav.topLevelItemCount()):
                        other = self.tree_nav.topLevelItem(i)
                        if other is not item and other.data(0, Qt.UserRole) != "category_favs":
                            other.setExpanded(False)
                item.setExpanded(will_expand)
            return

        self.navigate_to(str(data))

    def _show_sidebar_context_menu(self, pos) -> None:
        """Exibe menu de contexto rico ao clicar com botão direito na sidebar."""
        item = self.tree_nav.itemAt(pos)
        menu = QMenu(self)

        if item:
            data = str(item.data(0, Qt.UserRole) or "")
            if data.startswith("category_"):
                a_only_this = menu.addAction("Focar Apenas Nesta Categoria (Recolher Outras)")
                a_expand_all = menu.addAction("Expandir Todas as Categorias")
                a_collapse_all = menu.addAction("Recolher Todas as Categorias")
                menu.addSeparator()
                acc_label = "Desativar Modo Acordeão" if self._accordion_mode else "Ativar Modo Acordeão (Abrir 1 por vez)"
                a_accordion = menu.addAction(acc_label)

                act = menu.exec(self.tree_nav.mapToGlobal(pos))
                if act == a_only_this:
                    for i in range(self.tree_nav.topLevelItemCount()):
                        top = self.tree_nav.topLevelItem(i)
                        top.setExpanded(top is item)
                elif act == a_expand_all:
                    self.tree_nav.expandAll()
                elif act == a_collapse_all:
                    self.tree_nav.collapseAll()
                elif act == a_accordion:
                    self._accordion_mode = not self._accordion_mode
                return

            if data not in ("home", "history", "settings", "debug") and not data.startswith("category_"):
                tool = get_tool(data)
                if tool:
                    fav_text = "Remover dos Favoritos" if is_favorite(data) else "Fixar nos Favoritos"
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
                        self.home_page.refresh_home()
                    elif act == a_open:
                        self.navigate_to(data)
                    elif act == a_copy_name:
                        QApplication.clipboard().setText(tool.name)
                    elif act == a_copy_id:
                        QApplication.clipboard().setText(tool.id)
                    return

        a_exp = menu.addAction("Expandir Todas as Categorias")
        a_col = menu.addAction("Recolher Todas as Categorias")
        menu.addSeparator()
        acc_label = "Desativar Modo Acordeão" if self._accordion_mode else "Ativar Modo Acordeão (Abrir 1 por vez)"
        a_acc = menu.addAction(acc_label)
        act = menu.exec(self.tree_nav.mapToGlobal(pos))
        if act == a_exp:
            self.tree_nav.expandAll()
        elif act == a_col:
            self.tree_nav.collapseAll()
        elif act == a_acc:
            self._accordion_mode = not self._accordion_mode

    def _quick_toggle_theme(self) -> None:
        t = get_current_tokens()
        new_mode = "light" if t.is_dark else "dark"
        st = load_settings()
        st["theme"] = new_mode
        save_settings(st)
        apply_theme(QApplication.instance(), mode=new_mode, accent_override=st.get("accent_override", ""))
        self._populate_navigation()
        if "settings" in self._view_cache:
            self._view_cache["settings"]._load_values()
        label_mode = "Claro" if new_mode == "light" else "Escuro"
        show_toast(self, f"Tema {label_mode} Ativado", "A paleta visual foi atualizada.", kind="info", duration_ms=2000)

    def _setup_shortcuts(self) -> None:
        shortcut_k = QShortcut(QKeySequence("Ctrl+K"), self)
        shortcut_k.activated.connect(self._open_command_palette)

        shortcut_b = QShortcut(QKeySequence("Ctrl+B"), self)
        shortcut_b.activated.connect(self.toggle_sidebar)

        shortcut_f = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut_f.activated.connect(lambda: self.txt_filter.setFocus())

        shortcut_debug = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        shortcut_debug.activated.connect(lambda: self.navigate_to("debug"))

        shortcut_back = QShortcut(QKeySequence("Alt+Left"), self)
        shortcut_back.activated.connect(self.navigate_back)

    def _setup_system_tray(self) -> None:
        self.tray_manager = SystemTrayManager(
            on_show_window=self.restore_window,
            on_open_tool=self.navigate_to,
            on_search=self._open_command_palette,
        )

    def _setup_global_hotkey(self) -> None:
        st = load_settings()
        if st.get("global_hotkey_enabled", True):
            self.hotkey_triggered.connect(self.restore_window)
            self.hotkey_mgr = GlobalHotkeyManager(callback=self.hotkey_triggered.emit)
            self.hotkey_mgr.start()
        else:
            self.hotkey_mgr = None

    def restore_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _open_command_palette(self) -> None:
        dlg = CommandPaletteDialog(self)
        dlg.tool_selected.connect(self.navigate_to)
        dlg.exec()

    def navigate_back(self) -> None:
        """Retorna à visualização anterior no histórico de navegação."""
        if self._nav_history:
            prev_id = self._nav_history.pop()
            self.navigate_to(prev_id, record_history=False)

    def _update_breadcrumb(self, view_id: str) -> None:
        if view_id == "home":
            self.lbl_breadcrumb.setText("Início")
        elif view_id == "history":
            self.lbl_breadcrumb.setText("Início  /  Histórico de Tarefas")
        elif view_id == "settings":
            self.lbl_breadcrumb.setText("Início  /  Configurações")
        elif view_id == "debug":
            self.lbl_breadcrumb.setText("Início  /  Depuração e Logs")
        else:
            tool = get_tool(view_id)
            if tool:
                self.lbl_breadcrumb.setText(f"Início  /  {tool.category}  /  {tool.name}")
            else:
                self.lbl_breadcrumb.setText(view_id)

        self.btn_back.setEnabled(len(self._nav_history) > 0)
        # Sincroniza estado ativo nos botões de navegação expandidos e colapsados
        is_home = (view_id == "home")
        is_hist = (view_id == "history")
        is_sett = (view_id == "settings")
        is_debug = (view_id == "debug")

        for btn, active in [
            (self.btn_nav_home, is_home),
            (self.btn_nav_history, is_hist),
            (self.btn_nav_settings, is_sett),
            (self.btn_col_home, is_home),
            (self.btn_col_history, is_hist),
            (self.btn_col_settings, is_sett),
            (self.btn_nav_debug, is_debug),
            (self.btn_col_debug, is_debug),
        ]:
            btn.setProperty("active", "true" if active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def navigate_to(self, view_id: str, record_history: bool = True) -> None:
        """Lazy loading: só instancia e carrega a tela no momento em que é solicitada."""
        if record_history and self._current_view_id and self._current_view_id != view_id:
            if not self._nav_history or self._nav_history[-1] != self._current_view_id:
                self._nav_history.append(self._current_view_id)

        if view_id == "home":
            self.home_page.refresh_home()
        elif view_id == "history":
            if "history" not in self._view_cache:
                hp = HistoryPage(self)
                hp.tool_requested.connect(self.navigate_to)
                self._view_cache["history"] = hp
                self.stack.addWidget(hp)
            self._view_cache["history"].refresh()
        elif view_id == "settings":
            if "settings" not in self._view_cache:
                sp = SettingsPage(self)
                sp.settings_changed.connect(self._on_settings_updated)
                self._view_cache["settings"] = sp
                self.stack.addWidget(sp)
        elif view_id == "debug":
            if "debug" not in self._view_cache:
                dp = DebugPage(self)
                self._view_cache["debug"] = dp
                self.stack.addWidget(dp)
        elif view_id not in self._view_cache:
            tool = get_tool(view_id)
            if not tool:
                return

            if isinstance(tool, FileTool):
                page = FileToolPage(tool, self)
                page.favorite_toggled.connect(lambda tid, is_fav: self._on_favorite_toggled())
                page.task_started.connect(self._on_job_started)
                page.task_progress.connect(self._on_job_progress)
                page.task_completed.connect(lambda title, msg, err, tid=tool.id: self._on_job_finished(tid, title, msg, err))
            elif isinstance(tool, Tool):
                page = tool.build_view(self)
            else:
                return

            self._view_cache[view_id] = page
            self.stack.addWidget(page)

        if view_id not in ("home", "history", "settings", "debug") and get_tool(view_id):
            add_recent_tool(view_id)
            if isinstance(self._view_cache.get(view_id), FileToolPage):
                self._view_cache[view_id]._update_fav_button()

        # Exibe a página solicitada
        if view_id in self._view_cache:
            self._current_view_id = view_id
            self.stack.setCurrentWidget(self._view_cache[view_id])
            self._update_breadcrumb(view_id)

        # Sincroniza seleção na árvore da sidebar
        for i in range(self.tree_nav.topLevelItemCount()):
            top = self.tree_nav.topLevelItem(i)
            if top.data(0, Qt.UserRole) == view_id:
                self.tree_nav.setCurrentItem(top)
                break
            for j in range(top.childCount()):
                child = top.child(j)
                if child.data(0, Qt.UserRole) == view_id:
                    if self._accordion_mode:
                        for k in range(self.tree_nav.topLevelItemCount()):
                            other = self.tree_nav.topLevelItem(k)
                            if other is not top and other.data(0, Qt.UserRole) != "category_favs":
                                other.setExpanded(False)
                    top.setExpanded(True)
                    self.tree_nav.setCurrentItem(child)
                    break

    def _on_favorite_toggled(self) -> None:
        self._populate_navigation()
        self.home_page.refresh_home()

    def _on_job_started(self, tool_id: str, tool_name: str) -> None:
        self._active_jobs[tool_id] = f"{tool_name} (Iniciando...)"
        self._refresh_active_jobs_pill()

    def _on_job_progress(self, tool_id: str, current: int, total: int) -> None:
        tool = get_tool(tool_id)
        name = tool.name if tool else tool_id
        pct = int((current / total) * 100) if total > 0 else 0
        self._active_jobs[tool_id] = f"{name} ({pct}%)"
        self._refresh_active_jobs_pill()

    def _on_job_finished(self, tool_id: str, title: str, message: str, is_error: bool) -> None:
        self._active_jobs.pop(tool_id, None)
        self._refresh_active_jobs_pill()
        self._on_task_completed(title, message, is_error)

    def _refresh_active_jobs_pill(self) -> None:
        if not self._active_jobs:
            self.btn_active_jobs.setVisible(False)
            return
        first_tid, label = next(iter(self._active_jobs.items()))
        extra = f" +{len(self._active_jobs) - 1}" if len(self._active_jobs) > 1 else ""
        self.btn_active_jobs.setText(f"Em execução: {label}{extra}")
        self.btn_active_jobs.setProperty("active_tool_id", first_tid)
        self.btn_active_jobs.setVisible(True)

    def _jump_to_active_job(self) -> None:
        tid = self.btn_active_jobs.property("active_tool_id")
        if tid:
            self.navigate_to(str(tid))

    def _on_task_completed(self, title: str, message: str, is_error: bool) -> None:
        self.tray_manager.notify(title, message, is_error)

    def _on_settings_updated(self) -> None:
        self._populate_navigation()
        self.home_page.refresh_home()
        self.tray_manager.refresh_menu()

    def open_tool_with_paths(self, tool_id: str, paths: List[Path]) -> None:
        """Abre uma ferramenta e injeta os arquivos/pastas selecionados se suportado."""
        self.navigate_to(tool_id)
        page = self._view_cache.get(tool_id)
        if isinstance(page, FileToolPage):
            page.add_paths(paths)
            show_toast(self, page.tool.name, f"{len(paths)} item(ns) carregado(s) para processamento.", kind="success")

    def route_dropped_paths(self, paths: List[Path], interactive: bool = True) -> None:
        """Roteia de forma inteligente quaisquer arquivos ou pastas soltos na janela."""
        if not paths:
            return

        curr_page = self.stack.currentWidget()
        if isinstance(curr_page, FileToolPage):
            curr_page.add_paths(paths)
            return

        compatible = find_compatible_tools_for_paths(paths)
        if not compatible:
            self.open_tool_with_paths("images.convert", paths)
            return

        if not interactive or len(compatible) == 1:
            self.open_tool_with_paths(compatible[0].id, paths)
            return

        dlg = SmartDropDialog(paths, self)
        dlg.tool_chosen.connect(self.open_tool_with_paths)
        dlg.exec()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        """Drop global: arrastar arquivos soltos em qualquer lugar da janela principal."""
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if Path(u.toLocalFile()).exists()]
        if not paths:
            return
        self.route_dropped_paths(paths, interactive=True)

    def handle_external_args(self, args: List[str]) -> None:
        """Argumentos vindos de outra execução do app (instância única)."""
        self.restore_window()
        paths = [Path(a) for a in args if not a.startswith("-") and Path(a).exists()]
        if paths:
            self.route_dropped_paths(paths, interactive=False)

    def _process_startup_args(self) -> None:
        """Recebe caminhos passados pelo Windows via 'Enviar para' ou terminal."""
        if len(sys.argv) > 1:
            paths = [Path(arg) for arg in sys.argv[1:] if Path(arg).exists()]
            if paths:
                self.route_dropped_paths(paths, interactive=False)

    def closeEvent(self, event: QCloseEvent) -> None:
        st = load_settings()
        if st.get("minimize_to_tray", True):
            event.ignore()
            self.hide()
            self.tray_manager.notify(
                "All the Utils",
                "O aplicativo continua em execução na bandeja do sistema.",
            )
        else:
            if self.hotkey_mgr:
                self.hotkey_mgr.stop()
            event.accept()
