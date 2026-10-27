"""
Ferramenta: Quem Está Usando Este Arquivo? (Restart Manager API do Windows).
Identifica processos que estão travando arquivos ou pastas no Windows e permite encerrá-los.
"""
import ctypes
import os
import psutil
from ctypes import wintypes
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import find_locking_processes, terminate_process
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

@register
class LockCheckerTool(Tool):
    id = "files.lock_checker"
    name = "Quem Está Usando Este Arquivo?"
    category = "Arquivos e Pastas"
    description = "Verificador de arquivos travados: detecta quais programas ou processos do Windows estão bloqueando a exclusão ou renomeação de um arquivo e permite liberá-lo."
    keywords = ["bloqueado", "trava", "processo", "lock", "fechar", "arquivo", "em uso", "restart manager"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return LockCheckerView(self, parent)

class LockCheckerView(QWidget):
    def __init__(self, tool: LockCheckerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.processes: List[Dict[str, str]] = []
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # Seletor do Arquivo Bloqueado
        card_sel = QFrame()
        card_sel.setProperty("class", "card")
        l_sel = QVBoxLayout(card_sel)
        l_sel.setSpacing(10)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Arquivo ou Pasta Travada:"))
        self.txt_path = QLineEdit()
        self.txt_path.setPlaceholderText("Cole o caminho do arquivo ou selecione abaixo...")
        row1.addWidget(self.txt_path, stretch=1)

        btn_browse_f = QPushButton("Arquivo...")
        btn_browse_f.clicked.connect(self._browse_file)
        row1.addWidget(btn_browse_f)

        btn_browse_d = QPushButton("Pasta...")
        btn_browse_d.clicked.connect(self._browse_dir)
        row1.addWidget(btn_browse_d)

        self.btn_check = QPushButton("Verificar Bloqueios")
        self.btn_check.setProperty("class", "primary")
        self.btn_check.clicked.connect(self._start_check)
        row1.addWidget(self.btn_check)
        l_sel.addLayout(row1)

        layout.addWidget(card_sel)

        # Status
        self.lbl_status = QLabel("Nenhum arquivo analisado no momento.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        # Tabela de Processos
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["PID", "Nome do Programa / Processo", "Serviço", "Ação"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setFixedHeight(260)
        enable_sorting_on_table(self.table)
        layout.addWidget(self.table)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _browse_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo Bloqueado")
        if f:
            self.txt_path.setText(f)
            self._start_check()

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta Bloqueada")
        if d:
            self.txt_path.setText(d)
            self._start_check()

    def _start_check(self):
        target = self.txt_path.text().strip()
        if not target or not Path(target).exists():
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo ou pasta existente.")
            return

        self.btn_check.setEnabled(False)
        self.lbl_status.setText("Consultando API do Windows Restart Manager...")

        def worker(ctx):
            return find_locking_processes(target)

        def on_done(procs: List[Dict[str, str]]):
            self.btn_check.setEnabled(True)
            self.processes = procs
            self._populate_table()

            if procs:
                self.lbl_status.setText(f"{len(procs)} processo(s) estão utilizando ou bloqueando este item.")
                self.lbl_status.setStyleSheet("color: #ffa198; font-weight: 600;")
            else:
                self.lbl_status.setText("[LIVRE] Nenhum processo está travando este arquivo ou pasta no momento.")
                self.lbl_status.setStyleSheet("color: #7ee787; font-weight: 600;")

        def on_error(err):
            self.btn_check.setEnabled(True)
            QMessageBox.critical(self, "Erro", f"Falha ao consultar bloqueios:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_error)

    def _populate_table(self):
        with batch_table_update(self.table):
            self.table.setRowCount(len(self.processes))
            for row, p in enumerate(self.processes):
                pid_val = int(p["pid"]) if p["pid"].isdigit() else p["pid"]
                self.table.setItem(row, 0, SmartTableWidgetItem(p["pid"], sort_value=pid_val))
                self.table.setItem(row, 1, SmartTableWidgetItem(p["name"]))
                self.table.setItem(row, 2, SmartTableWidgetItem(p["service"]))

                btn_kill = QPushButton("Encerrar Processo")
                btn_kill.setProperty("class", "danger")
                btn_kill.clicked.connect(lambda _, pid=int(p["pid"]), name=p["name"]: self._kill_process(pid, name))
                self.table.setCellWidget(row, 3, btn_kill)

    def _kill_process(self, pid: int, name: str):
        reply = QMessageBox.question(
            self,
            "Confirmar Encerramento",
            f"Deseja realmente forçar o encerramento do processo '{name}' (PID: {pid})?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                terminate_process(pid)
                QMessageBox.information(self, "Sucesso", f"Processo {name} finalizado!")
                self._start_check()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Não foi possível finalizar o processo:\n{str(e)}")
