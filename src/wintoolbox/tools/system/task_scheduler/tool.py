"""
Ferramenta: Gerenciador de Tarefas Agendadas do Windows.
Visualização de tarefas de sistema e aplicativos, disparo manual e ativação/desativação.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import is_admin, request_elevation
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.task_scheduler.logic import (
    list_scheduled_tasks, run_scheduled_task, toggle_scheduled_task
)


@register
class TaskSchedulerTool(Tool):
    id = "system.task_scheduler"
    name = "Tarefas Agendadas do Windows"
    category = "Sistema"
    description = "Visualização e controle rápido de tarefas agendadas do Windows (executar agora, ativar e desativar)"
    keywords = ["tarefas", "schtasks", "agendadas", "cron", "timer", "schedule", "gatilhos", "windows"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return TaskSchedulerView(self, parent)


class TaskSchedulerView(QWidget):
    def __init__(self, tool: TaskSchedulerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._tasks = []
        self._build_ui()
        self._refresh_tasks()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Barra Superior
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        top_bar.addWidget(QLabel("Filtrar:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filtrar por nome ou pasta da tarefa...")
        self.txt_filter.textChanged.connect(self._refresh_tasks)
        top_bar.addWidget(self.txt_filter)

        self.chk_hide_ms = QCheckBox("Ocultar tarefas da Microsoft / Windows")
        self.chk_hide_ms.setChecked(True)
        self.chk_hide_ms.stateChanged.connect(self._refresh_tasks)
        top_bar.addWidget(self.chk_hide_ms)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._refresh_tasks)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_count = QLabel("0 tarefas")
        self.lbl_count.setStyleSheet("color: #888890; font-weight: 500;")
        top_bar.addWidget(self.lbl_count)

        layout.addLayout(top_bar)

        # Tabela
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Nome da Tarefa", "Pasta / Caminho", "Próxima Execução", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Barra Inferior
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

    def _refresh_tasks(self):
        query = self.txt_filter.text()
        hide_ms = self.chk_hide_ms.isChecked()
        self._tasks = list_scheduled_tasks(hide_microsoft=hide_ms, filter_text=query)

        self.table.setRowCount(len(self._tasks))
        for row, t in enumerate(self._tasks):
            self.table.setItem(row, 0, QTableWidgetItem(t["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(t["folder"]))
            self.table.setItem(row, 2, QTableWidgetItem(t["next_run"]))

            st_item = QTableWidgetItem(t["status"])
            if "execu" in t["status"].lower():
                st_item.setForeground(Qt.green)
            elif "desativ" in t["status"].lower():
                st_item.setForeground(Qt.gray)
            self.table.setItem(row, 3, st_item)

        self.lbl_count.setText(f"{len(self._tasks)} tarefas")

    def _get_selected_task(self) -> Optional[dict]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        if 0 <= row < len(self._tasks):
            return self._tasks[row]
        return None

    def _on_run_now(self):
        task = self._get_selected_task()
        if not task:
            QMessageBox.information(self, "Aviso", "Selecione uma tarefa na tabela.")
            return

        ok, msg = run_scheduled_task(task["full_name"])
        if ok:
            QMessageBox.information(self, "Sucesso", msg)
            self._refresh_tasks()
        else:
            QMessageBox.critical(self, "Erro", msg)

    def _on_toggle(self, enable: bool):
        task = self._get_selected_task()
        if not task:
            QMessageBox.information(self, "Aviso", "Selecione uma tarefa na tabela.")
            return

        ok, msg = toggle_scheduled_task(task["full_name"], enable)
        if ok:
            QMessageBox.information(self, "Sucesso", msg)
            self._refresh_tasks()
        else:
            if not is_admin():
                ans = QMessageBox.question(
                    self,
                    "Privilégios Necessários",
                    f"{msg}\n\nPara alterar o agendamento de tarefas é necessário privilégio de Administrador. Deseja reiniciar como Administrador?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ans == QMessageBox.Yes:
                    request_elevation()
            else:
                QMessageBox.critical(self, "Erro", msg)
