"""
Ferramenta: Gerenciador de Processos do Windows.
Monitor em tempo real de CPU/RAM, busca e encerramento de tarefas.
"""
import os
import subprocess
from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.process_manager.logic import (
    ProcessSampler, get_process_details, terminate_process
)
from wintoolbox.ui.theme import get_current_tokens
from wintoolbox.ui.widgets.data_table import (
    BackgroundLoader, Column, DataTableView, bind_timer_to_visibility, fmt_number
)
from wintoolbox.ui.widgets.tool_header import make_tool_header

REFRESH_MS = 2000


@register
class ProcessManagerTool(Tool):
    id = "system.process_manager"
    name = "Gerenciador de Processos"
    category = "Sistema"
    description = "Monitoramento de processos em execução, consumo de CPU/RAM e finalização de tarefas"
    keywords = ["processo", "taskmanager", "cpu", "memória", "ram", "finalizar", "kill", "tarefas"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ProcessManagerView(self, parent)


COLUMNS = [
    Column("pid", "PID", align="right", width=70),
    Column("name", "Nome do Processo", width=260, tooltip=True),
    Column("cpu_percent", "CPU (%)", align="right", width=80, fmt=fmt_number(1)),
    Column("memory_mb", "Memória (MB)", align="right", width=110, fmt=fmt_number(1)),
    Column("private_mb", "Privada (MB)", align="right", width=105, fmt=fmt_number(1)),
    Column("threads", "Threads", align="right", width=75),
    Column("handles", "Handles", align="right", width=80),
    Column("username", "Usuário", stretch=True),
]


class ProcessManagerView(QWidget):
    def __init__(self, tool: ProcessManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        # O amostrador guarda a amostra anterior para calcular CPU%; só a thread do loader o usa
        self._sampler = ProcessSampler()
        self._loader = BackgroundLoader(self._sampler.sample, self)
        self._loader.loaded.connect(self._on_loaded)
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._loader.request)
        bind_timer_to_visibility(self, self.timer, REFRESH_MS, on_show=self._loader.request)
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
        self.txt_filter.setPlaceholderText("Nome do processo, PID ou usuário...")
        # Filtro local: não reconsulta o Windows a cada tecla
        self.txt_filter.textChanged.connect(self._on_filter_changed)
        top_bar.addWidget(self.txt_filter, stretch=1)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._loader.request)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_count = QLabel("Carregando...")
        self.lbl_count.setProperty("class", "secondary")
        top_bar.addWidget(self.lbl_count)
        layout.addLayout(top_bar)

        self.table = DataTableView(COLUMNS, key="pid", parent=self)
        self.table.sortByColumn(3, Qt.DescendingOrder)  # memória, maior primeiro
        self.table.doubleClicked.connect(lambda _idx: self._on_view_details())
        t = get_current_tokens()
        self.table.source_model.foreground = (
            lambda rec, key: t.status_warning if key == "cpu_percent" and rec["cpu_percent"] >= 25 else None
        )
        layout.addWidget(self.table, stretch=1)

        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        self.btn_open_location = QPushButton("Abrir Local do Executável")
        self.btn_open_location.clicked.connect(self._on_open_location)
        bottom_bar.addWidget(self.btn_open_location)

        self.btn_details = QPushButton("Ver Detalhes")
        self.btn_details.clicked.connect(self._on_view_details)
        bottom_bar.addWidget(self.btn_details)

        bottom_bar.addStretch()

        self.btn_kill_tree = QPushButton("Finalizar Árvore de Processos")
        self.btn_kill_tree.clicked.connect(lambda: self._on_kill(tree=True))
        bottom_bar.addWidget(self.btn_kill_tree)

        self.btn_kill = QPushButton("Finalizar Processo")
        self.btn_kill.setProperty("class", "danger")
        self.btn_kill.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        self.btn_kill.clicked.connect(lambda: self._on_kill(tree=False))
        bottom_bar.addWidget(self.btn_kill)

        layout.addLayout(bottom_bar)

    def _on_loaded(self, procs):
        self.table.set_records(procs)
        self._update_count()

    def _on_filter_changed(self, text: str):
        self.table.proxy.set_text_filter(text)
        self._update_count()

    def _update_count(self):
        total = self.table.source_model.rowCount()
        shown = self.table.visible_count()
        self.lbl_count.setText(f"{total} processos" if shown == total else f"{shown} de {total} processos")

    def _get_selected_pid(self) -> Optional[int]:
        rec = self.table.current_record()
        return int(rec["pid"]) if rec else None

    def _on_kill(self, tree: bool = False):
        pid = self._get_selected_pid()
        if not pid:
            QMessageBox.information(self, "Aviso", "Selecione um processo na tabela para finalizar.")
            return

        action_name = "a árvore de processos deste executável" if tree else f"o processo com PID {pid}"
        confirm = QMessageBox.question(
            self,
            "Confirmar Encerramento",
            f"Deseja realmente finalizar {action_name}?\nDados não salvos do aplicativo podem ser perdidos.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        res = terminate_process(pid, kill_tree=tree)
        if res["success"]:
            self._loader.request()
            QMessageBox.information(self, "Sucesso", res["message"])
        else:
            QMessageBox.critical(self, "Erro", res["message"])

    def _on_open_location(self):
        pid = self._get_selected_pid()
        if not pid:
            QMessageBox.information(self, "Aviso", "Selecione um processo na tabela.")
            return
        details = get_process_details(pid)
        exe = details.get("executable")
        if exe and os.path.exists(exe):
            subprocess.Popen(f'explorer /select,"{exe}"')
        else:
            QMessageBox.warning(self, "Aviso", "Não foi possível localizar o caminho deste executável.")

    def _on_view_details(self):
        pid = self._get_selected_pid()
        if not pid:
            QMessageBox.information(self, "Aviso", "Selecione um processo na tabela.")
            return

        details = get_process_details(pid)
        if not details.get("success"):
            QMessageBox.warning(self, "Aviso", details.get("message", "Falha ao obter detalhes."))
            return

        msg = (
            f"Nome: {details['name']}\n"
            f"PID: {details['pid']}\n"
            f"Executável: {details['executable']}\n"
            f"Linha de Comando: {details['cmdline']}\n"
            f"Pasta de Trabalho: {details['cwd']}\n"
            f"Threads: {details['num_threads']}\n"
            f"Memória RSS: {details['memory_rss_mb']} MB\n"
            f"Prioridade: {details['priority']}"
        )
        QMessageBox.information(self, f"Detalhes do Processo (PID {pid})", msg)
