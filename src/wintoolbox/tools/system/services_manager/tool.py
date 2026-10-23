"""
Ferramenta: Gerenciador de Serviços do Windows.
Listagem, início, parada, reinício e configuração de tipo de inicialização.
"""
from typing import Callable, Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, request_elevation
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.system.services_manager.logic import (
    change_service_startup_type, change_service_status, list_windows_services
)
from wintoolbox.ui.theme import get_current_tokens
from wintoolbox.ui.widgets.data_table import BackgroundLoader, Column, DataTableView
from wintoolbox.ui.widgets.tool_header import make_tool_header


@register
class ServicesManagerTool(Tool):
    id = "system.services_manager"
    name = "Gerenciador de Serviços"
    category = "Sistema"
    description = "Visualização e controle de serviços do Windows (iniciar, parar, reiniciar e tipo de boot)"
    keywords = ["serviços", "services", "daemon", "sc", "iniciar", "parar", "status", "windows"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ServicesManagerView(self, parent)


COLUMNS = [
    Column("name", "Nome do Serviço", width=200, tooltip=True),
    Column("display_name", "Nome de Exibição", stretch=True, tooltip=True),
    Column("status", "Status", width=110),
    Column("start_type", "Inicialização", width=150),
    Column("pid", "PID", align="right", width=70, fmt=lambda v: str(v) if v else "-"),
]

STATUS_FILTERS = {0: None, 1: "running", 2: "stopped"}


class ServicesManagerView(QWidget):
    def __init__(self, tool: ServicesManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        # Carrega todos os serviços uma vez; texto e status são filtrados localmente
        self._loader = BackgroundLoader(lambda: list_windows_services(""), self)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.failed.connect(lambda err: self.lbl_count.setText(f"Falha ao listar: {err}"))
        self._build_ui()
        self._loader.request()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(make_tool_header(self.tool))

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        top_bar.addWidget(QLabel("Filtrar:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setClearButtonEnabled(True)
        self.txt_filter.setPlaceholderText("Nome, nome de exibição ou PID...")
        self.txt_filter.textChanged.connect(self._apply_filters)
        top_bar.addWidget(self.txt_filter, stretch=1)

        top_bar.addWidget(QLabel("Status:"))
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["Todos", "Em execução", "Parados"])
        self.cmb_status.currentIndexChanged.connect(self._apply_filters)
        top_bar.addWidget(self.cmb_status)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._loader.request)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_count = QLabel("Carregando...")
        self.lbl_count.setProperty("class", "secondary")
        top_bar.addWidget(self.lbl_count)
        layout.addLayout(top_bar)

        self.table = DataTableView(COLUMNS, key="name", parent=self)
        self.table.sortByColumn(1, Qt.AscendingOrder)
        t = get_current_tokens()
        self.table.source_model.foreground = lambda rec, key: (
            (t.status_success if rec["status_raw"] == "running" else t.text_muted) if key == "status" else None
        )
        layout.addWidget(self.table, stretch=1)

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
        self._action_buttons = [self.btn_start, self.btn_stop, self.btn_restart, self.btn_set_startup]

    def _on_loaded(self, services):
        self.table.set_records(services)
        self._update_count()

    def _apply_filters(self):
        wanted = STATUS_FILTERS.get(self.cmb_status.currentIndex())
        self.table.proxy.set_predicate(None if wanted is None else (lambda rec: rec["status_raw"] == wanted))
        self.table.proxy.set_text_filter(self.txt_filter.text())
        self._update_count()

    def _update_count(self):
        total = self.table.source_model.rowCount()
        shown = self.table.visible_count()
        self.lbl_count.setText(f"{total} serviços" if shown == total else f"{shown} de {total} serviços")

    def _get_selected_service_name(self) -> Optional[str]:
        rec = self.table.current_record()
        return rec["name"] if rec else None

    def _run_action(self, label: str, fn: Callable[[], Tuple[bool, str]], admin_hint: str) -> None:
        """Executa a ação fora da thread da UI ('net stop' pode levar até ~20 s)."""
        for b in self._action_buttons:
            b.setEnabled(False)
        self.lbl_count.setText(f"{label}...")

        def done(result, exc):
            for b in self._action_buttons:
                b.setEnabled(True)
            ok, msg = result if exc is None else (False, str(exc))
            self._loader.request()
            if ok:
                QMessageBox.information(self, "Sucesso", msg)
            elif not is_admin():
                ans = QMessageBox.question(
                    self, "Privilégios Necessários",
                    f"{msg}\n\n{admin_hint} Deseja reiniciar a aplicação como Administrador?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ans == QMessageBox.Yes:
                    request_elevation()
            else:
                QMessageBox.critical(self, "Erro", msg)

        run_task(lambda ctx: fn(), on_done=done)

    def _on_change_status(self, action: str):
        srv = self._get_selected_service_name()
        if not srv:
            QMessageBox.information(self, "Aviso", "Selecione um serviço na lista.")
            return
        labels = {"start": "Iniciando", "stop": "Parando", "restart": "Reiniciando"}
        self._run_action(
            f"{labels.get(action, action)} '{srv}'",
            lambda: change_service_status(srv, action),
            "Para alterar o status de serviços do sistema é necessário privilégios de administrador.",
        )

    def _on_change_startup(self):
        srv = self._get_selected_service_name()
        if not srv:
            QMessageBox.information(self, "Aviso", "Selecione um serviço na lista.")
            return
        target_type = self.cmb_startup.currentData()
        self._run_action(
            f"Alterando inicialização de '{srv}'",
            lambda: change_service_startup_type(srv, target_type),
            "Para alterar a configuração de inicialização de serviços é necessário privilégios de administrador.",
        )
