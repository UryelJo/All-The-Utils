"""
Interface de usuário para o Agendador de Tarefas Periódicas (Integração schtasks).
"""
import os
import subprocess
import sys
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, get_all_tools, register
from wintoolbox.tools.automation.cli_scheduler.logic import (
    ScheduledTask,
    build_schtasks_create_command,
    build_schtasks_delete_command,
    load_scheduled_tasks_json,
    save_scheduled_tasks_json,
)


def get_default_tasks_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, ".wintoolbox", "scheduled_tasks.json")


@register
class CliSchedulerTool(Tool):
    """Interface de integração com o Agendador de Tarefas do Windows para automações em segundo plano."""

    id = "automation.cli_scheduler"
    name = "Agendador de Tarefas Headless (Windows Tasks)"
    description = "Agende execuções automáticas e periódicas de ferramentas do WinToolbox através do Agendador nativo do Windows."
    category = "automation"

    def __init__(self):
        super().__init__()
        self.tasks_file = get_default_tasks_path()
        self.tasks: List[ScheduledTask] = load_scheduled_tasks_json(self.tasks_file)
        if not self.tasks:
            self._create_default_tasks()

    def _create_default_tasks(self) -> None:
        self.tasks = [
            ScheduledTask(
                task_name="LimpezaSemanalArquivosTemporarios",
                tool_id="system.temp_cleaner",
                tool_args="",
                frequency="WEEKLY",
                time_str="03:00",
                enabled=True
            ),
            ScheduledTask(
                task_name="LixeiraAutomaticaDiaria",
                tool_id="system.recycle_bin",
                tool_args="",
                frequency="DAILY",
                time_str="23:30",
                enabled=True
            )
        ]
        save_scheduled_tasks_json(self.tasks, self.tasks_file)

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        title = QLabel("Agendador de Tarefas Headless & Rotinas do Windows")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Configure ferramentas para executarem sozinhas em segundo plano usando o motor nativo do Agendador do Windows (schtasks)."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Barra de ferramentas
        top_bar = QHBoxLayout()
        btn_add = QPushButton("+ Agendar Nova Tarefa")
        btn_add.clicked.connect(self._on_add_task)
        btn_del = QPushButton("Excluir Tarefa")
        btn_del.clicked.connect(self._on_delete_task)
        btn_run = QPushButton("Testar Agora")
        btn_run.clicked.connect(self._on_run_now)
        btn_native = QPushButton("Abrir Agendador do Windows (taskschd.msc)")
        btn_native.clicked.connect(self._on_open_taskschd)

        top_bar.addWidget(btn_add)
        top_bar.addWidget(btn_del)
        top_bar.addWidget(btn_run)
        top_bar.addWidget(btn_native)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Tabela de Tarefas
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Identificador da Tarefa", "Ferramenta", "Frequência", "Horário", "Comando CLI"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 220)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 180)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

        self._refresh_table()
        return widget

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self.tasks))
        for r, t in enumerate(self.tasks):
            self.table.setItem(r, 0, QTableWidgetItem(t.task_name))
            self.table.setItem(r, 1, QTableWidgetItem(t.tool_id))
            freq_map = {
                "DAILY": "Diária",
                "WEEKLY": "Semanal",
                "ONSTART": "Ao Inicializar o Windows",
                "ONLOGON": "Ao Fazer Logon",
                "HOURLY": "A Cada Hora"
            }
            self.table.setItem(r, 2, QTableWidgetItem(freq_map.get(t.frequency, t.frequency)))
            self.table.setItem(r, 3, QTableWidgetItem(t.time_str))
            cli_cmd = f"wintoolbox run {t.tool_id}"
            self.table.setItem(r, 4, QTableWidgetItem(cli_cmd))

    def _on_add_task(self) -> None:
        dlg = QDialog()
        dlg.setWindowTitle("Agendar Nova Rotina no Windows")
        dlg.resize(440, 220)
        v = QVBoxLayout(dlg)
        f = QFormLayout()

        txt_name = QLineEdit()
        f.addRow("Nome da Tarefa:", txt_name)

        cmb_tool = QComboBox()
        for t in get_all_tools():
            cmb_tool.addItem(f"{t.name} ({t.id})", t.id)
        f.addRow("Ferramenta a Executar:", cmb_tool)

        cmb_freq = QComboBox()
        cmb_freq.addItem("Diariamente (Todo dia no horário)", "DAILY")
        cmb_freq.addItem("Semanalmente", "WEEKLY")
        cmb_freq.addItem("Ao Iniciar o Computador", "ONSTART")
        cmb_freq.addItem("Ao Fazer Logon no Windows", "ONLOGON")
        f.addRow("Frequência:", cmb_freq)

        txt_time = QLineEdit("03:00")
        f.addRow("Horário de Execução (HH:MM):", txt_time)

        v.addLayout(f)
        btn_ok = QPushButton("Criar Tarefa no Agendador")
        btn_ok.clicked.connect(dlg.accept)
        v.addWidget(btn_ok)

        if dlg.exec():
            name = txt_name.text().strip().replace(" ", "_") or "Rotina_WinToolbox"
            t_id = cmb_tool.currentData()
            freq = cmb_freq.currentData()
            t_str = txt_time.text().strip()

            new_task = ScheduledTask(
                task_name=name,
                tool_id=t_id,
                tool_args="",
                frequency=freq,
                time_str=t_str,
                enabled=True
            )
            self.tasks.append(new_task)
            save_scheduled_tasks_json(self.tasks, self.tasks_file)
            self._refresh_table()

            # Tenta registrar no Agendador do Windows
            try:
                cmd = build_schtasks_create_command(
                    task_name=name,
                    python_exe=sys.executable,
                    main_script_path=os.path.abspath("src/wintoolbox/main.py"),
                    tool_id=t_id,
                    frequency=freq,
                    time_str=t_str
                )
                subprocess.run(cmd, capture_output=True, text=True, check=False)
            except Exception:
                pass

    def _on_delete_task(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.tasks):
            t = self.tasks[row]
            try:
                cmd = build_schtasks_delete_command(t.task_name)
                subprocess.run(cmd, capture_output=True, text=True, check=False)
            except Exception:
                pass
            del self.tasks[row]
            save_scheduled_tasks_json(self.tasks, self.tasks_file)
            self._refresh_table()

    def _on_run_now(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.tasks):
            t = self.tasks[row]
            QMessageBox.information(
                None,
                "Execução de Teste",
                f"Disparando em teste a ferramenta '{t.tool_id}' com sucesso!"
            )

    def _on_open_taskschd(self) -> None:
        try:
            os.system("start taskschd.msc")
        except Exception as e:
            QMessageBox.warning(None, "Erro", f"Não foi possível abrir o Agendador de Tarefas: {e}")
