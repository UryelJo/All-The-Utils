"""
Interface gráfica do Lançador de Ambientes de Trabalho (Workspaces).
"""
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.automation.workspace_launcher.logic import (
    launch_workspace, load_workspaces, save_workspaces
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("automation.workspace_launcher.ui")


@register
class WorkspaceLauncherTool(Tool):
    id = "automation.workspace_launcher"
    name = "Lançador de Ambientes"
    category = "Automação"
    description = "Abertura simultânea em 1 clique de conjuntos de softwares, pastas e URLs no navegador"
    keywords = ["workspace", "ambiente", "launcher", "abrir", "urls", "programas", "produtividade", "automacao"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return WorkspaceLauncherView(self, parent)


class WorkspaceLauncherView(QWidget):
    def __init__(self, tool: WorkspaceLauncherTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._workspaces: List[Dict[str, Any]] = []
        self._current_index = 0

        self._build_ui()
        self._load_data()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Lançador de Ambientes de Trabalho (Workspaces)",
            "Agrupe seus sites, pastas e ferramentas por contexto (Desenvolvimento, Estudos, Finanças) e inicie tudo de uma vez."
        ))

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 1. Painel Esquerdo: Lista de Perfis
        left_panel = QFrame()
        left_panel.setProperty("class", "card")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        left_layout.addWidget(QLabel("Ambientes Cadastrados:"))
        self.list_workspaces = QListWidget()
        self.list_workspaces.currentRowChanged.connect(self._on_workspace_selected)
        left_layout.addWidget(self.list_workspaces, stretch=1)

        btn_row = QHBoxLayout()
        btn_new_ws = QPushButton("+ Novo Ambiente")
        btn_new_ws.clicked.connect(self._create_new_workspace)
        btn_row.addWidget(btn_new_ws)

        btn_del_ws = QPushButton("Excluir")
        btn_del_ws.clicked.connect(self._delete_workspace)
        btn_row.addWidget(btn_del_ws)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left_panel)

        # 2. Painel Direito: Itens e Ação
        right_panel = QFrame()
        right_panel.setProperty("class", "card")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(10)

        # Cabeçalho do Workspace Selecionado
        top_bar = QHBoxLayout()
        self.lbl_ws_title = QLabel("Selecione um ambiente")
        self.lbl_ws_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        top_bar.addWidget(self.lbl_ws_title)

        top_bar.addStretch(1)

        self.btn_launch = QPushButton("Lançar Este Ambiente Agora")
        self.btn_launch.setProperty("class", "primary")
        self.btn_launch.setFixedHeight(36)
        self.btn_launch.clicked.connect(self._launch_current_workspace)
        top_bar.addWidget(self.btn_launch)

        right_layout.addLayout(top_bar)

        # Tabela de Itens
        self.table_items = QTableWidget()
        self.table_items.setColumnCount(3)
        self.table_items.setHorizontalHeaderLabels(["Tipo", "Alvo / URL / Caminho", "Ação"])
        self.table_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_items.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table_items.setColumnWidth(2, 75)
        right_layout.addWidget(self.table_items, stretch=1)

        # Formulário para Adicionar Novo Item
        add_box = QGroupBox("Adicionar Novo Item ao Ambiente")
        add_grid = QGridLayout(add_box)
        add_grid.setSpacing(8)

        add_grid.addWidget(QLabel("Tipo:"), 0, 0)
        self.combo_item_type = QComboBox()
        self.combo_item_type.addItem("Página Web (URL)", "url")
        self.combo_item_type.addItem("Pasta no Explorer", "folder")
        self.combo_item_type.addItem("Aplicativo (.exe)", "app")
        self.combo_item_type.currentIndexChanged.connect(self._on_type_changed)
        add_grid.addWidget(self.combo_item_type, 0, 1)

        add_grid.addWidget(QLabel("Alvo:"), 0, 2)
        self.edit_target = QLineEdit()
        self.edit_target.setPlaceholderText("Ex: https://google.com ou C:/Projetos")
        add_grid.addWidget(self.edit_target, 0, 3)

        self.btn_browse = QPushButton("Procurar...")
        self.btn_browse.setEnabled(False)
        self.btn_browse.clicked.connect(self._browse_target)
        add_grid.addWidget(self.btn_browse, 0, 4)

        btn_add_item = QPushButton("Adicionar Item")
        btn_add_item.clicked.connect(self._add_item_to_workspace)
        add_grid.addWidget(btn_add_item, 0, 5)

        right_layout.addWidget(add_box)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        root.addWidget(splitter, stretch=1)

    def _load_data(self) -> None:
        self._workspaces = load_workspaces()
        self.list_workspaces.clear()
        for ws in self._workspaces:
            item = QListWidgetItem(ws["name"])
            self.list_workspaces.addItem(item)

        if self._workspaces:
            self.list_workspaces.setCurrentRow(0)

    def _on_workspace_selected(self, row: int) -> None:
        if 0 <= row < len(self._workspaces):
            self._current_index = row
            ws = self._workspaces[row]
            self.lbl_ws_title.setText(ws["name"])
            self._refresh_items_table(ws)

    def _refresh_items_table(self, ws: Dict[str, Any]) -> None:
        items = ws.get("items", [])
        self.table_items.setRowCount(len(items))

        type_names = {"url": "Site / URL", "folder": "Pasta", "app": "Aplicativo"}

        for r, item in enumerate(items):
            itype = type_names.get(item.get("type"), "Item")
            self.table_items.setItem(r, 0, QTableWidgetItem(itype))
            self.table_items.setItem(r, 1, QTableWidgetItem(item.get("target", "")))

            btn_del = QPushButton("Remover")
            btn_del.setStyleSheet("font-size: 10px; padding: 2px;")
            btn_del.clicked.connect(lambda checked=False, idx=r: self._remove_item(idx))
            self.table_items.setCellWidget(r, 2, btn_del)

    def _on_type_changed(self) -> None:
        itype = self.combo_item_type.currentData()
        self.btn_browse.setEnabled(itype in ("folder", "app"))
        if itype == "url":
            self.edit_target.setPlaceholderText("Ex: https://github.com ou localhost:3000")
        elif itype == "folder":
            self.edit_target.setPlaceholderText("Ex: C:/Projetos/MeuApp")
        else:
            self.edit_target.setPlaceholderText("Ex: C:/Program Files/Notepad++/notepad++.exe")

    def _browse_target(self) -> None:
        itype = self.combo_item_type.currentData()
        if itype == "folder":
            path = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
            if path:
                self.edit_target.setText(path)
        elif itype == "app":
            path, _ = QFileDialog.getOpenFileName(self, "Selecionar Executável", "", "Programas (*.exe *.bat *.cmd);;Todos (*.*)")
            if path:
                self.edit_target.setText(path)

    def _add_item_to_workspace(self) -> None:
        if not (0 <= self._current_index < len(self._workspaces)):
            return

        target = self.edit_target.text().strip()
        if not target:
            show_toast(self, "Informe o alvo ou URL a ser aberto.")
            return

        itype = self.combo_item_type.currentData() or "url"
        self._workspaces[self._current_index]["items"].append({
            "type": itype,
            "target": target
        })

        save_workspaces(self._workspaces)
        self._refresh_items_table(self._workspaces[self._current_index])
        self.edit_target.clear()
        show_toast(self, "Item adicionado com sucesso!")

    def _remove_item(self, item_index: int) -> None:
        if 0 <= self._current_index < len(self._workspaces):
            ws = self._workspaces[self._current_index]
            if 0 <= item_index < len(ws["items"]):
                del ws["items"][item_index]
                save_workspaces(self._workspaces)
                self._refresh_items_table(ws)

    def _create_new_workspace(self) -> None:
        name, ok = QInputDialog.getText(self, "Novo Ambiente", "Digite o nome do novo ambiente de trabalho:")
        if ok and name.strip():
            new_ws = {
                "id": f"ws_{len(self._workspaces) + 1}",
                "name": name.strip(),
                "description": "",
                "items": []
            }
            self._workspaces.append(new_ws)
            save_workspaces(self._workspaces)
            self._load_data()
            self.list_workspaces.setCurrentRow(len(self._workspaces) - 1)

    def _delete_workspace(self) -> None:
        if 0 <= self._current_index < len(self._workspaces):
            del self._workspaces[self._current_index]
            save_workspaces(self._workspaces)
            self._load_data()

    def _launch_current_workspace(self) -> None:
        if not (0 <= self._current_index < len(self._workspaces)):
            return

        ws = self._workspaces[self._current_index]
        results = launch_workspace(ws)
        success_count = sum(1 for _, ok, _ in results if ok)
        show_toast(self, f"{success_count} item(ns) abertos com sucesso!", duration_ms=3000)
