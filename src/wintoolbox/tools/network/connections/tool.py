"""
Interface gráfica do Monitor de Conexões Ativas por Processo (estilo TCPView).
"""
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.network.connections.logic import (
    list_active_connections, terminate_connection_process
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("network.connections.ui")


@register
class ConnectionsTool(Tool):
    id = "network.connections"
    name = "Conexões de Rede por Processo"
    category = "Rede e Internet"
    description = "Monitoramento ao vivo de portas abertas, sockets e conexões ativas associadas a cada processo (TCPView)"
    keywords = ["conexoes", "portas", "tcp", "udp", "processo", "tcpview", "socket", "rede", "listening", "established"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ConnectionsView(self, parent)


class ConnectionsView(QWidget):
    def __init__(self, tool: ConnectionsTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._all_conns: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        # Barra de ferramentas superior
        top_bar = QHBoxLayout()

        self.btn_refresh = QPushButton("Atualizar Conexões")
        self.btn_refresh.setProperty("accent", True)
        self.btn_refresh.clicked.connect(self._load_async)
        top_bar.addWidget(self.btn_refresh)

        self.btn_kill = QPushButton("Finalizar Processo")
        self.btn_kill.clicked.connect(self._kill_selected_process)
        top_bar.addWidget(self.btn_kill)

        top_bar.addSpacing(16)
        top_bar.addWidget(QLabel("Filtrar:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Buscar por IP, porta, processo ou PID...")
        self.txt_filter.textChanged.connect(self._apply_filter)
        top_bar.addWidget(self.txt_filter, stretch=1)

        self.lbl_stats = QLabel("0 conexões")
        top_bar.addWidget(self.lbl_stats)

        layout.addLayout(top_bar)

        # Tabela de conexões
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Protocolo", "Processo", "PID", "Endereço Local", "Endereço Remoto", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table, stretch=1)

        self._load_async()

    def _load_async(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_stats.setText("Consultando sockets...")

        def _worker():
            return list_active_connections()

        def _on_done(conns: List[Dict[str, Any]]):
            self.btn_refresh.setEnabled(True)
            self._all_conns = conns
            self._apply_filter(self.txt_filter.text())

        def _on_error(err):
            self.btn_refresh.setEnabled(True)
            self.lbl_stats.setText("Erro ao listar conexões.")
            show_toast(self, "Falha na leitura de conexões de rede", is_error=True)

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _apply_filter(self, query: str) -> None:
        q = query.lower().strip()
        filtered = []
        for c in self._all_conns:
            if (not q or q in c["process_name"].lower() or q in str(c["pid"])
                    or q in c["local_address"].lower() or q in c["remote_address"].lower()
                    or q in c["status"].lower() or q in c["proto"].lower()):
                filtered.append(c)

        self.table.setRowCount(len(filtered))
        established_count = 0

        for row, c in enumerate(filtered):
            self.table.setItem(row, 0, QTableWidgetItem(c["proto"]))
            self.table.setItem(row, 1, QTableWidgetItem(c["process_name"]))
            self.table.setItem(row, 2, QTableWidgetItem(str(c["pid"])))
            self.table.setItem(row, 3, QTableWidgetItem(c["local_address"]))
            self.table.setItem(row, 4, QTableWidgetItem(c["remote_address"]))

            status_item = QTableWidgetItem(c["status"])
            if c["status"] == "ESTABLISHED":
                established_count += 1
                status_item.setForeground(Qt.green)
            elif c["status"] == "LISTENING":
                status_item.setForeground(Qt.cyan)

            self.table.setItem(row, 5, status_item)

        self.lbl_stats.setText(f"{len(filtered)} exibidas ({established_count} estabelecidas)")

    def _kill_selected_process(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            show_toast(self, "Selecione uma conexão na tabela.", is_error=True)
            return

        pid_text = self.table.item(row, 2).text()
        try:
            pid = int(pid_text)
            ok, msg = terminate_connection_process(pid)
            if ok:
                show_toast(self, msg)
                self._load_async()
            else:
                show_toast(self, msg, is_error=True)
        except Exception as exc:
            show_toast(self, f"Erro: {exc}", is_error=True)
