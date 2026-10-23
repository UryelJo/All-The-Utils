"""
Ferramenta: Gerenciador de Processos do Windows.
Monitor em tempo real de CPU/RAM, busca e encerramento de tarefas.
"""
import os
import subprocess
from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.system.process_manager.logic import (
    get_process_details, list_running_processes, terminate_process
)


@register
class ProcessManagerTool(Tool):
    id = "system.process_manager"
    name = "Gerenciador de Processos"
    category = "Sistema"
    description = "Monitoramento de processos em execução, consumo de CPU/RAM e finalização de tarefas"
    keywords = ["processo", "taskmanager", "cpu", "memória", "ram", "finalizar", "kill", "tarefas"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ProcessManagerView(self, parent)


class ProcessManagerView(QWidget):
    def __init__(self, tool: ProcessManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()
        self._refresh_processes()

        # Timer de auto-atualização opcional (5 segundos)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)
        self.timer.start(5000)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Barra de ferramentas superior
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        lbl_filter = QLabel("Filtrar:")
        top_bar.addWidget(lbl_filter)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Digite o nome do processo, PID ou usuário...")
        self.txt_filter.textChanged.connect(self._refresh_processes)
        top_bar.addWidget(self.txt_filter)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._refresh_processes)
        top_bar.addWidget(self.btn_refresh)

        self.lbl_count = QLabel("0 processos")
        self.lbl_count.setStyleSheet("color: #888890; font-weight: 500;")
        top_bar.addWidget(self.lbl_count)

        layout.addLayout(top_bar)

        # Tabela de Processos
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "PID", "Nome do Processo", "RAM (MB)", "CPU (%)", "Usuário", "Status"
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

    def _on_timer_tick(self):
        # Apenas atualiza se o usuário não estiver com foco no campo de texto digitando
        if not self.txt_filter.hasFocus():
            self._refresh_processes()

    def _get_selected_pid(self) -> Optional[int]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        pid_item = self.table.item(row, 0)
        if pid_item:
            try:
                return int(pid_item.text())
            except ValueError:
                pass
        return None

    def _refresh_processes(self):
        query = self.txt_filter.text()
        procs = list_running_processes(query)

        self.table.setRowCount(len(procs))
        for row, p in enumerate(procs):
            pid_item = QTableWidgetItem(str(p["pid"]))
            pid_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 0, pid_item)

            name_item = QTableWidgetItem(p["name"])
            self.table.setItem(row, 1, name_item)

            ram_item = QTableWidgetItem(f"{p['memory_mb']:.1f}")
            ram_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, ram_item)

            cpu_item = QTableWidgetItem(f"{p['cpu_percent']:.1f}")
            cpu_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 3, cpu_item)

            user_item = QTableWidgetItem(p["username"])
            self.table.setItem(row, 4, user_item)

            status_item = QTableWidgetItem(p["status"])
            self.table.setItem(row, 5, status_item)

        self.lbl_count.setText(f"{len(procs)} processos")

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
            self._refresh_processes()
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
