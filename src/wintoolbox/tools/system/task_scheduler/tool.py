"""
Ferramenta: Gerenciador de Tarefas Agendadas do Windows.
Visualização de tarefas de sistema e aplicativos, disparo manual e ativação/desativação.
"""
from typing import Callable, Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, request_elevation
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.system.task_scheduler.logic import (
    list_all_scheduled_tasks, run_scheduled_task, toggle_scheduled_task
)
from wintoolbox.ui.theme import get_current_tokens
from wintoolbox.ui.widgets.data_table import BackgroundLoader, Column, DataTableView
from wintoolbox.ui.widgets.tool_header import make_tool_header


@register
class TaskSchedulerTool(Tool):
    id = "system.task_scheduler"
    name = "Tarefas Agendadas do Windows"
    category = "Sistema"
    description = "Visualização e controle rápido de tarefas agendadas do Windows (executar agora, ativar e desativar)"
    keywords = ["tarefas", "schtasks", "agendadas", "cron", "timer", "schedule", "gatilhos", "windows"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return TaskSchedulerView(self, parent)


COLUMNS = [
    Column("name", "Nome da Tarefa", stretch=True, tooltip=True),
    Column("folder", "Pasta", width=170, tooltip=True),
    Column("status", "Status", width=100),
    Column("next_run", "Próxima Execução", width=130),
    Column("last_run", "Última Execução", width=130),
    Column("last_result", "Último Resultado", width=140),
]


class TaskSchedulerView(QWidget):
    def __init__(self, tool: TaskSchedulerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        # Carrega todas as tarefas uma vez (API COM); filtros de texto e Microsoft são locais
        self._loader = BackgroundLoader(list_all_scheduled_tasks, self)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.failed.connect(lambda err: self.lbl_count.setText(f"Falha ao listar: {err}"))
        self._build_ui()
        self._apply_filters()
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
        self.txt_filter.setPlaceholderText("Nome, pasta ou status da tarefa...")
        self.txt_filter.textChanged.connect(self._apply_filters)
        top_bar.addWidget(self.txt_filter, stretch=1)

        self.chk_hide_ms = QCheckBox("Ocultar tarefas da Microsoft / Windows")
        self.chk_hide_ms.setChecked(True)
        self.chk_hide_ms.stateChanged.connect(self._apply_filters)
        top_bar.addWidget(self.chk_hide_ms)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._loader.request)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_count = QLabel("Carregando...")
        self.lbl_count.setProperty("class", "secondary")
        top_bar.addWidget(self.lbl_count)
        layout.addLayout(top_bar)

        self.table = DataTableView(COLUMNS, key="full_name", parent=self)
        self.table.sortByColumn(0, Qt.AscendingOrder)
        t = get_current_tokens()

        def color(rec, key):
            if key == "status":
                return {"Em execução": t.status_success, "Desativado": t.text_muted}.get(rec["status"])
            if key == "last_result" and rec["last_result"].startswith("0x"):
                return t.status_warning
            return None

        self.table.source_model.foreground = color
        layout.addWidget(self.table, stretch=1)

        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.btn_run_now = QPushButton("Executar Tarefa Agora")
        self.btn_run_now.setProperty("class", "primary")
        self.btn_run_now.clicked.connect(self._on_run_now)
        bottom_bar.addWidget(self.btn_run_now)

        self.btn_enable = QPushButton("Ativar Tarefa")
        self.btn_enable.clicked.connect(lambda: self._on_toggle(True))
        bottom_bar.addWidget(self.btn_enable)

        self.btn_disable = QPushButton("Desativar Tarefa")
        self.btn_disable.clicked.connect(lambda: self._on_toggle(False))
        bottom_bar.addWidget(self.btn_disable)

        bottom_bar.addStretch()
        layout.addLayout(bottom_bar)
        self._action_buttons = [self.btn_run_now, self.btn_enable, self.btn_disable]

    def _on_loaded(self, tasks):
        self.table.set_records(tasks)
        self._update_count()

    def _apply_filters(self):
        hide_ms = self.chk_hide_ms.isChecked()
        self.table.proxy.set_predicate((lambda rec: not rec["is_microsoft"]) if hide_ms else None)
        self.table.proxy.set_text_filter(self.txt_filter.text())
        self._update_count()

    def _update_count(self):
        total = self.table.source_model.rowCount()
        if not total and self._loader.busy:
            return
        shown = self.table.visible_count()
        self.lbl_count.setText(f"{shown} tarefas" + (f" (de {total})" if shown != total else ""))

    def _get_selected_task(self) -> Optional[dict]:
        return self.table.current_record()

    def _run_action(self, fn: Callable[[], Tuple[bool, str]], admin_hint: Optional[str]) -> None:
        for b in self._action_buttons:
            b.setEnabled(False)

        def done(result, exc):
            for b in self._action_buttons:
                b.setEnabled(True)
            ok, msg = result if exc is None else (False, str(exc))
            self._loader.request()
            if ok:
                QMessageBox.information(self, "Sucesso", msg)
            elif admin_hint and not is_admin():
                ans = QMessageBox.question(
                    self, "Privilégios Necessários", f"{msg}\n\n{admin_hint}", QMessageBox.Yes | QMessageBox.No
                )
                if ans == QMessageBox.Yes:
                    request_elevation()
            else:
                QMessageBox.critical(self, "Erro", msg)

        run_task(lambda ctx: fn(), on_done=done)

    def _on_run_now(self):
        task = self._get_selected_task()
        if not task:
            QMessageBox.information(self, "Aviso", "Selecione uma tarefa na tabela.")
            return
        self._run_action(lambda: run_scheduled_task(task["full_name"]), None)

    def _on_toggle(self, enable: bool):
        task = self._get_selected_task()
        if not task:
            QMessageBox.information(self, "Aviso", "Selecione uma tarefa na tabela.")
            return
        self._run_action(
            lambda: toggle_scheduled_task(task["full_name"], enable),
            "Para alterar o agendamento de tarefas é necessário privilégio de Administrador. "
            "Deseja reiniciar como Administrador?",
        )
