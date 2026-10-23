"""
Ferramenta: Gerenciador de Serviços do Windows.
Listagem, início, parada, reinício e configuração de tipo de inicialização.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, request_elevation
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.system.services_manager.logic import (
    change_service_startup_type, change_service_status, list_windows_services
)


@register
class ServicesManagerTool(Tool):
    id = "system.services_manager"
    name = "Gerenciador de Serviços"
    category = "Sistema"
    description = "Visualização e controle de serviços do Windows (iniciar, parar, reiniciar e tipo de boot)"
    keywords = ["serviços", "services", "daemon", "sc", "iniciar", "parar", "status", "windows"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ServicesManagerView(self, parent)


class ServicesManagerView(QWidget):
    def __init__(self, tool: ServicesManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self._build_ui()
        self._refresh_services()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Barra de Filtros
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        top_bar.addWidget(QLabel("Filtrar:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filtrar por nome ou exibição...")
        self.txt_filter.textChanged.connect(self._refresh_services)
        top_bar.addWidget(self.txt_filter)

        top_bar.addWidget(QLabel("Status:"))
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["Todos", "Em execução", "Parados"])
        self.cmb_status.currentIndexChanged.connect(self._refresh_services)
        top_bar.addWidget(self.cmb_status)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._refresh_services)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_count = QLabel("0 serviços")
        self.lbl_count.setStyleSheet("color: #888890; font-weight: 500;")
        top_bar.addWidget(self.lbl_count)

        layout.addLayout(top_bar)

        # Tabela de Serviços
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Nome do Serviço", "Nome de Exibição", "Status", "Tipo de Inicialização", "PID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Barra de Ações Inferior
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.btn_start = QPushButton("Iniciar Serviço")
        self.btn_start.clicked.connect(lambda: self._on_change_status("start"))
        bottom_bar.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Parar Serviço")
        self.btn_stop.clicked.connect(lambda: self._on_change_status("stop"))
        bottom_bar.addWidget(self.btn_stop)

        self.btn_restart = QPushButton("Reiniciar Serviço")
        self.btn_restart.clicked.connect(lambda: self._on_change_status("restart"))
        bottom_bar.addWidget(self.btn_restart)

        bottom_bar.addStretch()

        bottom_bar.addWidget(QLabel("Alterar Inicialização:"))
        self.cmb_startup = QComboBox()
        self.cmb_startup.addItem("Automático", "auto")
        self.cmb_startup.addItem("Manual", "manual")
        self.cmb_startup.addItem("Desativado", "disabled")
        bottom_bar.addWidget(self.cmb_startup)

        self.btn_set_startup = QPushButton("Aplicar Tipo")
        self.btn_set_startup.clicked.connect(self._on_change_startup)
        bottom_bar.addWidget(self.btn_set_startup)

        layout.addLayout(bottom_bar)

    def _get_selected_service_name(self) -> Optional[str]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.table.item(row, 0)
        return item.text() if item else None

    def _refresh_services(self):
        query = self.txt_filter.text()
        st_idx = self.cmb_status.currentIndex()
        st_map = {0: "all", 1: "running", 2: "stopped"}
        st_filter = st_map.get(st_idx, "all")

        srvs = list_windows_services(query, status_filter=st_filter)

        self.table.setRowCount(len(srvs))
        for row, s in enumerate(srvs):
            name_item = QTableWidgetItem(s["name"])
            self.table.setItem(row, 0, name_item)

            disp_item = QTableWidgetItem(s["display_name"])
            self.table.setItem(row, 1, disp_item)

            status_item = QTableWidgetItem(s["status"])
            if s["status_raw"] == "running":
                status_item.setForeground(Qt.green)
            else:
                status_item.setForeground(Qt.gray)
            self.table.setItem(row, 2, status_item)

            start_item = QTableWidgetItem(s["start_type"])
            self.table.setItem(row, 3, start_item)

            pid_str = str(s["pid"]) if s["pid"] > 0 else "-"
            pid_item = QTableWidgetItem(pid_str)
            pid_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, pid_item)

        self.lbl_count.setText(f"{len(srvs)} serviços")

    def _on_change_status(self, action: str):
        srv = self._get_selected_service_name()
        if not srv:
            QMessageBox.information(self, "Aviso", "Selecione um serviço na lista.")
            return

        ok, msg = change_service_status(srv, action)
        if ok:
            QMessageBox.information(self, "Sucesso", msg)
            self._refresh_services()
        else:
            if not is_admin():
                ans = QMessageBox.question(
                    self,
                    "Privilégios Necessários",
                    f"{msg}\n\nPara alterar o status de serviços do sistema é necessário privilégios de administrador. Deseja reiniciar a aplicação como Administrador?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ans == QMessageBox.Yes:
                    request_elevation()
            else:
                QMessageBox.critical(self, "Erro", msg)

    def _on_change_startup(self):
        srv = self._get_selected_service_name()
        if not srv:
            QMessageBox.information(self, "Aviso", "Selecione um serviço na lista.")
            return

        target_type = self.cmb_startup.currentData()
        ok, msg = change_service_startup_type(srv, target_type)
        if ok:
            QMessageBox.information(self, "Sucesso", msg)
            self._refresh_services()
        else:
            if not is_admin():
                ans = QMessageBox.question(
                    self,
                    "Privilégios Necessários",
                    f"{msg}\n\nPara alterar a configuração de inicialização de serviços é necessário privilégios de administrador. Deseja reiniciar como Administrador?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ans == QMessageBox.Yes:
                    request_elevation()
            else:
                QMessageBox.critical(self, "Erro", msg)
