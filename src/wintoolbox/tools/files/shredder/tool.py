"""
Ferramenta: Triturador Seguro de Arquivos (File Shredder).
Sobrescreve dados em múltiplos passes (zeros, uns e aleatório criptográfico), trunca e renomeia antes de excluir definitivamente.
"""
import os
import secrets
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import format_file_size, shred_multiple_files, shred_single_file
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

@register
class ShredderTool(Tool):
    id = "files.shredder"
    name = "Triturador Seguro de Arquivos"
    category = "Arquivos e Pastas"
    description = "Destrói permanentemente arquivos com sobrescrita multi-passes impedindo recuperação"
    keywords = ["triturar", "shredder", "apagar", "seguro", "privacidade", "destruir", "wipe", "excluir"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ShredderView(self, parent)

class ShredderView(QWidget):
    def __init__(self, tool: ShredderTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.files_to_shred: List[Path] = []
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

        # Card de Alerta
        card_warn = QFrame()
        card_warn.setProperty("class", "card")
        l_warn = QVBoxLayout(card_warn)
        l_warn.setSpacing(6)

        lbl_w1 = QLabel("Atenção: Ação Irreversível")
        lbl_w1.setStyleSheet("color: #ffa198; font-weight: 700; font-size: 14px;")
        l_warn.addWidget(lbl_w1)

        lbl_w2 = QLabel(
            "Os arquivos triturados NÃO poderão ser recuperados pela Lixeira nem por softwares de recuperação forense.\n"
            "Em unidades SSD modernas, o firmware de nivelamento de desgaste (wear-leveling) gerencia blocos flash internamente."
        )
        lbl_w2.setProperty("class", "secondary")
        l_warn.addWidget(lbl_w2)
        layout.addWidget(card_warn)

        # Configurações do Algoritmo
        card_cfg = QFrame()
        card_cfg.setProperty("class", "card")
        l_cfg = QHBoxLayout(card_cfg)
        l_cfg.setSpacing(12)

        l_cfg.addWidget(QLabel("Método de Sobrescrita:"))
        self.cmb_passes = QComboBox()
        self.cmb_passes.addItems([
            "1 Passe — Sobrescrita Rápida com Zeros (0x00)",
            "3 Passes — Padrão DoD 5220.22-M (Zeros, Uns e Aleatório)",
            "7 Passes — Padrão Avançado de Segurança"
        ])
        self.cmb_passes.setCurrentIndex(1)  # 3 passes padrão
        l_cfg.addWidget(self.cmb_passes, stretch=1)

        btn_add = QPushButton("Adicionar Arquivos...")
        btn_add.clicked.connect(self._add_files)
        l_cfg.addWidget(btn_add)

        btn_clear = QPushButton("Limpar Lista")
        btn_clear.clicked.connect(self._clear_list)
        l_cfg.addWidget(btn_clear)
        layout.addWidget(card_cfg)

        # Tabela de Arquivos para Triturar
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Arquivo", "Tamanho", "Caminho Completo"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setFixedHeight(240)
        enable_sorting_on_table(self.table)
        layout.addWidget(self.table)

        # Barra de Ação
        bar_actions = QHBoxLayout()
        self.btn_shred = QPushButton("Triturar Permanentemente os Arquivos")
        self.btn_shred.setProperty("class", "danger")
        self.btn_shred.setFixedHeight(36)
        self.btn_shred.setEnabled(False)
        self.btn_shred.clicked.connect(self._start_shredding)
        bar_actions.addWidget(self.btn_shred)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        bar_actions.addWidget(self.progress_bar, stretch=1)
        layout.addLayout(bar_actions)

        self.lbl_status = QLabel("Nenhum arquivo na fila de trituração.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar Arquivos para Destruição Segura")
        if files:
            for f in files:
                p = Path(f)
                if p not in self.files_to_shred:
                    self.files_to_shred.append(p)
            self._update_table()

    def _clear_list(self):
        self.files_to_shred.clear()
        self._update_table()

    def _update_table(self):
        with batch_table_update(self.table):
            self.table.setRowCount(len(self.files_to_shred))
            for row, p in enumerate(self.files_to_shred):
                sz = p.stat().st_size if p.exists() else 0
                self.table.setItem(row, 0, SmartTableWidgetItem(p.name, sort_value=p.name.lower(), user_data=p))
                self.table.setItem(row, 1, SmartTableWidgetItem(self._format_size(sz), sort_value=sz))
                self.table.setItem(row, 2, SmartTableWidgetItem(str(p.parent)))

        self.btn_shred.setEnabled(len(self.files_to_shred) > 0)
        self.lbl_status.setText(f"{len(self.files_to_shred)} arquivo(s) prontos para trituração.")

    def _format_size(self, size_bytes: int) -> str:
        return format_file_size(size_bytes)

    def _start_shredding(self):
        if not self.files_to_shred:
            return

        passes_map = {0: 1, 1: 3, 2: 7}
        passes = passes_map.get(self.cmb_passes.currentIndex(), 3)

        reply = QMessageBox.warning(
            self,
            "Confirmação Crítica",
            f"Deseja REALMENTE destruir permanentemente {len(self.files_to_shred)} arquivo(s) com {passes} passes de sobrescrita?\n\n"
            "Esta operação NÃO pode ser desfeita!",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_shred.setEnabled(False)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Iniciando trituração segura...")

        files = list(self.files_to_shred)

        def worker(ctx):
            def on_progress(percent, msg):
                ctx.send_progress(percent, msg)
            return shred_multiple_files(files, passes=passes, progress_cb=on_progress)

        def on_task_progress(percent, _total, msg):
            self.progress_bar.setValue(percent)
            self.lbl_status.setText(msg)

        def on_done(total):
            self.progress_bar.setValue(100)
            self.files_to_shred.clear()
            self._update_table()
            self.lbl_status.setText(f"{total} arquivo(s) destruídos permanentemente.")
            QMessageBox.information(
                self,
                "Trituração Concluída",
                f"{total} arquivo(s) foram sobrescritos e destruídos com sucesso!"
            )

        def on_error(err):
            self.btn_shred.setEnabled(True)
            QMessageBox.critical(self, "Erro", f"Falha durante a trituração:\n{err}")

        self.runner.start_task(worker, on_progress=on_task_progress, on_finished=on_done, on_error=on_error)
