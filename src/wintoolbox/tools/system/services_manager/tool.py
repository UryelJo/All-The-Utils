"""
Ferramenta: Gerenciador de Serviços do Windows.
Listagem, início, parada, reinício, configuração de inicialização em lote, ícones e menu de contexto.
"""
from typing import Callable, List, Optional, Tuple
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, prompt_elevation_dialog
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.system.services_manager.logic import (
    change_multiple_services_startup,
    change_multiple_services_status,
    list_windows_services,
)
from wintoolbox.ui.theme import get_current_tokens
from wintoolbox.ui.widgets.data_table import BackgroundLoader, Column, DataTableView
from wintoolbox.ui.widgets.tool_header import make_tool_header


@register
class ServicesManagerTool(Tool):
    id = "system.services_manager"
    name = "Gerenciador de Serviços"
    category = "Sistema"
    description = "Visualização e controle de serviços do Windows em lote (iniciar, parar, reiniciar e tipo de boot)"
    keywords = ["serviços", "services", "daemon", "sc", "iniciar", "parar", "status", "windows"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ServicesManagerView(self, parent)


COLUMNS = [
    Column("name", "Nome do Serviço", width=220, tooltip=True, icon_key="exe_path", fallback_icon=True),
    Column("display_name", "Nome de Exibição", stretch=True, tooltip=True),
    Column("status", "Status", width=115),
    Column("start_type", "Inicialização", width=150),
    Column("pid", "PID", align="right", width=70, fmt=lambda v: str(v) if v else "-"),
]

STATUS_FILTERS = {0: None, 1: "running", 2: "stopped"}


class ServicesManagerView(QWidget):
    def __init__(self, tool: ServicesManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
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

        self.chk_select_all = QCheckBox("Marcar Visíveis")
        self.chk_select_all.toggled.connect(self._on_select_all_toggled)
        top_bar.addWidget(self.chk_select_all)

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

        self.btn_clear_checks = QPushButton("Limpar Seleção")
        self.btn_clear_checks.setVisible(False)
        self.btn_clear_checks.clicked.connect(self._on_clear_checks)
        top_bar.addWidget(self.btn_clear_checks)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._loader.request)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_count = QLabel("Carregando...")
        self.lbl_count.setProperty("class", "secondary")
        top_bar.addWidget(self.lbl_count)
        layout.addLayout(top_bar)

        self.table = DataTableView(COLUMNS, key="name", parent=self, checkable=True)
        self.table.sortByColumn(1, Qt.AscendingOrder)
        self.table.checkedChanged.connect(self._on_checked_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)

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

    def _on_select_all_toggled(self, checked: bool):
        self.table.set_all_visible_checked(checked)

    def _on_clear_checks(self):
        self.chk_select_all.blockSignals(True)
        self.chk_select_all.setChecked(False)
        self.chk_select_all.blockSignals(False)
        self.table.clear_checked()

    def _on_checked_changed(self, count: int):
        self.btn_clear_checks.setVisible(count > 0)
        suffix = f" ({count})" if count > 0 else ""
        self.btn_start.setText(f"Iniciar{suffix}" if count > 0 else "Iniciar Serviço")
        self.btn_stop.setText(f"Parar{suffix}" if count > 0 else "Parar Serviço")
        self.btn_restart.setText(f"Reiniciar{suffix}" if count > 0 else "Reiniciar Serviço")
        self.btn_set_startup.setText(f"Aplicar Tipo{suffix}" if count > 0 else "Aplicar Tipo")
        self._update_count()

    def _update_count(self):
        total = self.table.source_model.rowCount()
        shown = self.table.visible_count()
        checked = len(self.table.checked_records())
        base = f"{total} serviços" if shown == total else f"{shown} de {total} serviços"
        if checked > 0:
            base += f" ({checked} marcado(s))"
        self.lbl_count.setText(base)

    def _get_target_service_names(self) -> List[str]:
        targets = self.table.target_records()
        return [str(r["name"]) for r in targets if r.get("name")]

    def _on_context_menu(self, pos: QPoint):
        rec = self.table.record_at_pos(pos)
        if not rec:
            return

        srv_name = str(rec["name"])
        disp_name = str(rec.get("display_name") or srv_name)
        status_raw = str(rec.get("status_raw") or "")
        is_checked = self.table.is_record_checked(rec)
        checked_records = self.table.checked_records()
        target_names = [str(r["name"]) for r in checked_records] if checked_records else [srv_name]
        batch_label = f" ({len(target_names)} selecionados)" if len(target_names) > 1 else f" '{disp_name}'"

        menu = QMenu(self)
        act_toggle = menu.addAction("Desmarcar Serviço" if is_checked else "Marcar Serviço")
        menu.addSeparator()

        act_start = menu.addAction(f"Iniciar{batch_label}")
        act_stop = menu.addAction(f"Parar{batch_label}")
        act_restart = menu.addAction(f"Reiniciar{batch_label}")
        if len(target_names) == 1:
            act_start.setEnabled(status_raw != "running")
            act_stop.setEnabled(status_raw == "running")

        menu.addSeparator()
        sub_startup = menu.addMenu(f"Tipo de Inicialização{batch_label}")
        act_auto = sub_startup.addAction("Automático")
        act_manual = sub_startup.addAction("Manual")
        act_disabled = sub_startup.addAction("Desativado")

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_toggle:
            self.table.toggle_record_checked(rec)
        elif chosen == act_start:
            self._execute_status_for_names(target_names, "start")
        elif chosen == act_stop:
            self._execute_status_for_names(target_names, "stop")
        elif chosen == act_restart:
            self._execute_status_for_names(target_names, "restart")
        elif chosen == act_auto:
            self._execute_startup_for_names(target_names, "auto")
        elif chosen == act_manual:
            self._execute_startup_for_names(target_names, "manual")
        elif chosen == act_disabled:
            self._execute_startup_for_names(target_names, "disabled")

    def _run_action(self, label: str, fn: Callable[[], Tuple[bool, str]], admin_hint: str) -> None:
        if not is_admin():
            if prompt_elevation_dialog(self, tool_name=self.tool.name, reason=admin_hint):
                return

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
                prompt_elevation_dialog(self, tool_name=self.tool.name, reason=f"{msg}\n{admin_hint}")
            else:
                QMessageBox.critical(self, "Erro", msg)

        run_task(lambda ctx: fn(), on_done=done)

    def _on_change_status(self, action: str):
        names = self._get_target_service_names()
        if not names:
            QMessageBox.information(self, "Aviso", "Selecione ou marque pelo menos um serviço na lista.")
            return
        self._execute_status_for_names(names, action)

    def _execute_status_for_names(self, names: List[str], action: str):
        labels = {"start": "Iniciando", "stop": "Parando", "restart": "Reiniciando"}
        target_str = f"'{names[0]}'" if len(names) == 1 else f"{len(names)} serviços"
        self._run_action(
            f"{labels.get(action, action)} {target_str}",
            lambda: change_multiple_services_status(names, action),
            "Para alterar o status de serviços do sistema é necessário privilégios de administrador.",
        )

    def _on_change_startup(self):
        names = self._get_target_service_names()
        if not names:
            QMessageBox.information(self, "Aviso", "Selecione ou marque pelo menos um serviço na lista.")
            return
        target_type = self.cmb_startup.currentData()
        self._execute_startup_for_names(names, target_type)

    def _execute_startup_for_names(self, names: List[str], target_type: str):
        target_str = f"'{names[0]}'" if len(names) == 1 else f"{len(names)} serviços"
        self._run_action(
            f"Alterando inicialização de {target_str}",
            lambda: change_multiple_services_startup(names, target_type),
            "Para alterar a configuração de inicialização de serviços é necessário privilégios de administrador.",
        )
