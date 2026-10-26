"""
Interface gráfica do Gerenciador de Regras do Firewall do Windows.
"""
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.network.firewall.logic import (
    block_application_firewall, delete_firewall_rule, list_firewall_rules
)
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("network.firewall.ui")


@register
class FirewallTool(Tool):
    id = "network.firewall"
    name = "Regras do Firewall do Windows"
    category = "Rede e Internet"
    description = "Consulta de regras ativas e bloqueio rápido de acesso à internet para executáveis específicos"
    keywords = ["firewall", "bloquear", "aplicativo", "porta", "regra", "netsh", "inbound", "outbound", "seguranca"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return FirewallView(self, parent)


class FirewallView(QWidget):
    def __init__(self, tool: FirewallTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._rules_cache: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        self.tabs = QTabWidget()
        self._setup_block_tab()
        self._setup_rules_tab()
        layout.addWidget(self.tabs, stretch=1)

    def _setup_block_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(12)

        box = QGroupBox("Bloquear Acesso à Internet de um Executável")
        b_lay = QVBoxLayout(box)
        b_lay.setContentsMargins(14, 14, 14, 14)
        b_lay.setSpacing(10)

        # Seleção de executável
        b_lay.addWidget(QLabel("Caminho do Aplicativo (.exe):"))
        path_row = QHBoxLayout()
        self.txt_exe_path = QLineEdit()
        self.txt_exe_path.setPlaceholderText("Selecione um arquivo .exe para bloquear conexões...")
        path_row.addWidget(self.txt_exe_path, stretch=1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._browse_exe)
        path_row.addWidget(btn_browse)
        b_lay.addLayout(path_row)

        # Nome da regra
        b_lay.addWidget(QLabel("Nome Identificador da Regra:"))
        self.txt_rule_name = QLineEdit()
        self.txt_rule_name.setPlaceholderText("Ex: Bloqueio AppXYZ")
        b_lay.addWidget(self.txt_rule_name)

        # Direções de tráfego
        dir_row = QHBoxLayout()
        self.chk_block_out = QCheckBox("Bloquear Saída (Impede o app de enviar dados / acessar internet)")
        self.chk_block_out.setChecked(True)
        dir_row.addWidget(self.chk_block_out)

        self.chk_block_in = QCheckBox("Bloquear Entrada (Impede conexões externas entrando)")
        self.chk_block_in.setChecked(True)
        dir_row.addWidget(self.chk_block_in)
        dir_row.addStretch()
        b_lay.addLayout(dir_row)

        btn_create = QPushButton("Aplicar Regra de Bloqueio")
        btn_create.setProperty("accent", True)
        btn_create.setFixedWidth(200)
        btn_create.clicked.connect(self._create_block_rule)
        b_lay.addWidget(btn_create)

        lay.addWidget(box)
        lay.addStretch()
        self.tabs.addTab(tab, "Bloquear Aplicativo")

    def _setup_rules_tab(self) -> None:
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(8, 12, 8, 8)
        lay.setSpacing(10)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Direção:"))
        self.combo_dir = QComboBox()
        self.combo_dir.addItem("Entrada (Inbound)", "Inbound")
        self.combo_dir.addItem("Saída (Outbound)", "Outbound")
        self.combo_dir.currentIndexChanged.connect(self._load_rules_async)
        top_bar.addWidget(self.combo_dir)

        self.btn_refresh = QPushButton("Atualizar Regras")
        self.btn_refresh.clicked.connect(self._load_rules_async)
        top_bar.addWidget(self.btn_refresh)

        top_bar.addSpacing(12)
        top_bar.addWidget(QLabel("Filtrar:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Buscar nome da regra...")
        self.txt_filter.textChanged.connect(self._filter_table)
        top_bar.addWidget(self.txt_filter, stretch=1)

        self.btn_delete_rule = QPushButton("Excluir Regra Selecionada")
        self.btn_delete_rule.clicked.connect(self._delete_rule)
        top_bar.addWidget(self.btn_delete_rule)

        lay.addLayout(top_bar)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nome da Regra", "Ação", "Direção", "Perfil"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        enable_sorting_on_table(self.table)
        lay.addWidget(self.table, stretch=1)

        self.lbl_rules_status = QLabel("Clique em Atualizar para consultar.")
        lay.addWidget(self.lbl_rules_status)

        self.tabs.addTab(tab, "Regras Ativas do Firewall")
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, idx: int) -> None:
        if idx == 1 and not self._rules_cache:
            self._load_rules_async()

    def _browse_exe(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar Executável", "", "Executáveis (*.exe);;Todos os Arquivos (*.*)")
        if path:
            self.txt_exe_path.setText(path)
            from pathlib import Path
            p = Path(path)
            if not self.txt_rule_name.text():
                self.txt_rule_name.setText(f"Bloqueio {p.stem}")

    def _create_block_rule(self) -> None:
        exe = self.txt_exe_path.text().strip()
        rname = self.txt_rule_name.text().strip()
        b_in = self.chk_block_in.isChecked()
        b_out = self.chk_block_out.isChecked()

        if not exe:
            show_toast(self, "Selecione o arquivo .exe do aplicativo.", is_error=True)
            return

        ok, msg = block_application_firewall(rname, exe, b_in, b_out)
        if ok:
            show_toast(self, msg)
            self._rules_cache.clear()
        else:
            show_toast(self, msg, is_error=True)

    def _load_rules_async(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_rules_status.setText("Consultando regras do Firewall do Windows...")
        direction = self.combo_dir.currentData()

        def _worker():
            return list_firewall_rules(direction, max_rules=150)

        def _on_done(rules: List[Dict[str, Any]]):
            self.btn_refresh.setEnabled(True)
            self._rules_cache = rules
            self._filter_table(self.txt_filter.text())
            self.lbl_rules_status.setText(f"{len(rules)} regras ativas carregadas.")

        def _on_error(err):
            self.btn_refresh.setEnabled(True)
            self.lbl_rules_status.setText("Erro ao consultar regras.")
            show_toast(self, "Falha na consulta do firewall", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _filter_table(self, query: str) -> None:
        q = query.lower().strip()
        filtered = [r for r in self._rules_cache if not q or q in r["name"].lower() or q in r["id"].lower()]

        with batch_table_update(self.table):
            self.table.setRowCount(len(filtered))
            for row, r in enumerate(filtered):
                self.table.setItem(row, 0, SmartTableWidgetItem(r["name"], user_data=r))

                act_item = SmartTableWidgetItem(r["action"])
                if r["action"] == "Bloquear":
                    act_item.setForeground(Qt.red)
                else:
                    act_item.setForeground(Qt.green)
                self.table.setItem(row, 1, act_item)

                self.table.setItem(row, 2, SmartTableWidgetItem(r["direction"]))
                self.table.setItem(row, 3, SmartTableWidgetItem(r["profile"]))

    def _delete_rule(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            show_toast(self, "Selecione uma regra na tabela para excluir.", is_error=True)
            return

        rule_name = self.table.item(row, 0).text()
        ok, msg = delete_firewall_rule(rule_name)
        if ok:
            show_toast(self, msg)
            self._load_rules_async()
        else:
            show_toast(self, msg, is_error=True)
