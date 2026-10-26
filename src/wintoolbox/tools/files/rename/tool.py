"""
Ferramenta: Renomeador de Arquivos em Lote (Batch Renamer).
Permite aplicar regras de substituição, numeração, prefixos/sufixos, alteração de caixa e prévia antes de gravar.
"""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import RenameItem, compute_new_name, execute_batch_rename
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

@register
class BatchRenameTool(Tool):
    id = "files.rename"
    name = "Renomeador de Arquivos em Lote"
    category = "Arquivos e Pastas"
    description = "Renomeia múltiplos arquivos com regras de substituição, numeração, data e prévia em tempo real"
    keywords = ["renomear", "arquivos", "lote", "substituir", "prefixo", "sufixo", "numeracao", "organizar"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return BatchRenameView(self, parent)

class BatchRenameView(QWidget):
    def __init__(self, tool: BatchRenameTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.items: List[RenameItem] = []
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

        # Barra de Adição de Arquivos
        bar_add = QHBoxLayout()
        btn_add_files = QPushButton("Adicionar Arquivos...")
        btn_add_files.clicked.connect(self._add_files)
        bar_add.addWidget(btn_add_files)

        btn_add_folder = QPushButton("Adicionar Pasta...")
        btn_add_folder.clicked.connect(self._add_folder)
        bar_add.addWidget(btn_add_folder)

        btn_clear_list = QPushButton("Limpar Lista")
        btn_clear_list.clicked.connect(self._clear_list)
        bar_add.addWidget(btn_clear_list)

        bar_add.addStretch()
        self.lbl_count = QLabel("Nenhum arquivo carregado.")
        self.lbl_count.setProperty("class", "secondary")
        bar_add.addWidget(self.lbl_count)
        layout.addLayout(bar_add)

        # Card de Regras de Renomeação
        card_rules = QFrame()
        card_rules.setProperty("class", "card")
        l_rules = QVBoxLayout(card_rules)
        l_rules.setSpacing(10)

        lbl_r_title = QLabel("Regras de Renomeação")
        lbl_r_title.setStyleSheet("font-weight: 600;")
        l_rules.addWidget(lbl_r_title)

        # Regra 1: Localizar e Substituir
        row_find = QHBoxLayout()
        row_find.addWidget(QLabel("Localizar:"))
        self.txt_find = QLineEdit()
        self.txt_find.setPlaceholderText("Texto a ser substituído...")
        self.txt_find.textChanged.connect(self._preview_rename)
        row_find.addWidget(self.txt_find, stretch=1)

        row_find.addWidget(QLabel("Substituir por:"))
        self.txt_replace = QLineEdit()
        self.txt_replace.setPlaceholderText("Novo texto...")
        self.txt_replace.textChanged.connect(self._preview_rename)
        row_find.addWidget(self.txt_replace, stretch=1)

        self.chk_regex = QCheckBox("Regex")
        self.chk_regex.stateChanged.connect(self._preview_rename)
        row_find.addWidget(self.chk_regex)
        l_rules.addLayout(row_find)

        # Regra 2: Prefixo e Sufixo
        row_affix = QHBoxLayout()
        row_affix.addWidget(QLabel("Inserir Prefixo:"))
        self.txt_prefix = QLineEdit()
        self.txt_prefix.setPlaceholderText("Texto no início do nome...")
        self.txt_prefix.textChanged.connect(self._preview_rename)
        row_affix.addWidget(self.txt_prefix, stretch=1)

        row_affix.addWidget(QLabel("Inserir Sufixo:"))
        self.txt_suffix = QLineEdit()
        self.txt_suffix.setPlaceholderText("Texto antes da extensão...")
        self.txt_suffix.textChanged.connect(self._preview_rename)
        row_affix.addWidget(self.txt_suffix, stretch=1)
        l_rules.addLayout(row_affix)

        # Regra 3: Numeração Sequencial e Caixa
        row_num = QHBoxLayout()
        self.chk_number = QCheckBox("Adicionar Numeração:")
        self.chk_number.stateChanged.connect(self._preview_rename)
        row_num.addWidget(self.chk_number)

        row_num.addWidget(QLabel("Início:"))
        self.spin_start = QSpinBox()
        self.spin_start.setRange(0, 99999)
        self.spin_start.setValue(1)
        self.spin_start.valueChanged.connect(self._preview_rename)
        row_num.addWidget(self.spin_start)

        row_num.addWidget(QLabel("Dígitos (Zeros):"))
        self.spin_digits = QSpinBox()
        self.spin_digits.setRange(1, 8)
        self.spin_digits.setValue(3)
        self.spin_digits.valueChanged.connect(self._preview_rename)
        row_num.addWidget(self.spin_digits)

        row_num.addWidget(QLabel("Caixa do Texto:"))
        self.cmb_case = QComboBox()
        self.cmb_case.addItems(["Manter Original", "MAIÚSCULAS", "minúsculas", "Primeira Maiúscula"])
        self.cmb_case.currentTextChanged.connect(self._preview_rename)
        row_num.addWidget(self.cmb_case)

        row_num.addStretch()
        l_rules.addLayout(row_num)

        layout.addWidget(card_rules)

        # Tabela de Prévia
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nome Atual", "Novo Nome Previsto", "Status", "Caminho da Pasta"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setFixedHeight(260)
        enable_sorting_on_table(self.table)
        layout.addWidget(self.table)

        # Barra de Ação de Execução
        bar_actions = QHBoxLayout()
        self.btn_apply = QPushButton("Aplicar Renomeação")
        self.btn_apply.setProperty("class", "primary")
        self.btn_apply.setFixedHeight(36)
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply_rename)
        bar_actions.addWidget(self.btn_apply)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        bar_actions.addWidget(self.progress_bar, stretch=1)
        layout.addLayout(bar_actions)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar Arquivos para Renomear")
        if files:
            for f in files:
                p = Path(f)
                if not any(item.original_path == p for item in self.items):
                    self.items.append(RenameItem(p))
            self._preview_rename()

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
        if folder:
            for root, _, files in os.walk(folder):
                for f in files:
                    p = Path(root) / f
                    if not any(item.original_path == p for item in self.items):
                        self.items.append(RenameItem(p))
            self._preview_rename()

    def _clear_list(self):
        self.items.clear()
        self.table.setRowCount(0)
        self.lbl_count.setText("Nenhum arquivo carregado.")
        self.btn_apply.setEnabled(False)

    def _preview_rename(self):
        find_str = self.txt_find.text()
        replace_str = self.txt_replace.text()
        prefix = self.txt_prefix.text()
        suffix = self.txt_suffix.text()
        is_regex = self.chk_regex.isChecked()
        add_number = self.chk_number.isChecked()
        start_num = self.spin_start.value()
        digits = self.spin_digits.value()
        case_opt = self.cmb_case.currentText()

        with batch_table_update(self.table):
            self.table.setRowCount(len(self.items))
            self.lbl_count.setText(f"{len(self.items)} arquivo(s) na lista")
            self.btn_apply.setEnabled(len(self.items) > 0)

            for i, item in enumerate(self.items):
                item.new_name = compute_new_name(
                    original_name=item.original_path.name,
                    index=i,
                    find_str=find_str,
                    replace_str=replace_str,
                    prefix=prefix,
                    suffix=suffix,
                    is_regex=is_regex,
                    add_number=add_number,
                    start_num=start_num,
                    digits=digits,
                    case_opt=case_opt
                )

                # Preenche tabela
                self.table.setItem(i, 0, SmartTableWidgetItem(item.original_path.name, sort_value=item.original_path.name.lower(), user_data=item))
                self.table.setItem(i, 1, SmartTableWidgetItem(item.new_name, sort_value=item.new_name.lower()))
                self.table.setItem(i, 2, SmartTableWidgetItem(item.status))
                self.table.setItem(i, 3, SmartTableWidgetItem(str(item.original_path.parent)))

    def _apply_rename(self):
        if not self.items:
            return

        reply = QMessageBox.question(
            self,
            "Confirmar Renomeação",
            f"Deseja realmente renomear {len(self.items)} arquivo(s)?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_apply.setEnabled(False)
        self.progress_bar.setValue(0)

        def worker(ctx):
            def on_progress(p, _):
                ctx.send_progress(p, "")
            return execute_batch_rename(self.items, progress_cb=on_progress)

        def on_task_progress(percent, _total, _msg):
            self.progress_bar.setValue(percent)

        def on_done(success_count):
            self.btn_apply.setEnabled(True)
            self.progress_bar.setValue(100)
            self._preview_rename()
            QMessageBox.information(
                self,
                "Concluído",
                f"Renomeação finalizada! {success_count} arquivo(s) foram renomeados."
            )

        def on_error(err):
            self.btn_apply.setEnabled(True)
            QMessageBox.critical(self, "Erro", f"Falha durante a renomeação:\n{err}")

        self.runner.start_task(worker, on_progress=on_task_progress, on_finished=on_done, on_error=on_error)
