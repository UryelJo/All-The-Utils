"""
Ferramenta: Comparador e Sincronizador de Pastas (Folder Sync & Diff).
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import SyncDifference, compare_directories, execute_sync


@register
class FolderSyncTool(Tool):
    id = "files.sync"
    name = "Comparador e Sincronizador de Pastas"
    category = "Arquivos e Pastas"
    description = "Compare duas pastas, visualize as diferenças e sincronize por espelhamento, atualização ou bidirecional"
    keywords = ["sync", "sincronizar", "backup", "espelhamento", "pastas", "diff", "comparar", "arquivos"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return FolderSyncView(self, parent)


class FolderSyncView(QWidget):
    def __init__(self, tool: FolderSyncTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.planned_diffs: List[SyncDifference] = []
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

        # Card de Configuração
        card = QFrame()
        card.setProperty("class", "card")
        l_card = QVBoxLayout(card)
        l_card.setSpacing(10)

        # Linha 1: Pasta Origem (A)
        r_a = QHBoxLayout()
        r_a.addWidget(QLabel("Pasta Origem (A):"))
        self.txt_dir_a = QLineEdit()
        r_a.addWidget(self.txt_dir_a, stretch=1)
        btn_a = QPushButton("Selecionar...")
        btn_a.clicked.connect(lambda: self._browse_folder(self.txt_dir_a))
        r_a.addWidget(btn_a)
        l_card.addLayout(r_a)

        # Linha 2: Pasta Destino (B)
        r_b = QHBoxLayout()
        r_b.addWidget(QLabel("Pasta Destino (B):"))
        self.txt_dir_b = QLineEdit()
        r_b.addWidget(self.txt_dir_b, stretch=1)
        btn_b = QPushButton("Selecionar...")
        btn_b.clicked.connect(lambda: self._browse_folder(self.txt_dir_b))
        r_b.addWidget(btn_b)
        l_card.addLayout(r_b)

        # Linha 3: Modos e Opções
        r_opts = QHBoxLayout()
        r_opts.addWidget(QLabel("Modo de Sincronização:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("Espelhamento (Origem -> Destino com remoção de órfãos)", "mirror")
        self.cmb_mode.addItem("Atualização (Origem -> Destino sem exclusões)", "update")
        self.cmb_mode.addItem("Bidirecional (Sincronizar ambos com a versão mais recente)", "bidirectional")
        r_opts.addWidget(self.cmb_mode, stretch=1)

        self.chk_hash = QCheckBox("Comparar por Hash MD5 de conteúdo")
        r_opts.addWidget(self.chk_hash)
        l_card.addLayout(r_opts)

        # Linha 4: Botões
        r_btns = QHBoxLayout()
        self.btn_compare = QPushButton("1. Comparar e Analisar Diferenças")
        self.btn_compare.setProperty("class", "primary")
        self.btn_compare.clicked.connect(self._start_compare)
        r_btns.addWidget(self.btn_compare)

        self.btn_sync = QPushButton("2. Executar Sincronização")
        self.btn_sync.setEnabled(False)
        self.btn_sync.clicked.connect(self._start_sync)
        r_btns.addWidget(self.btn_sync)
        r_btns.addStretch()
        l_card.addLayout(r_btns)

        layout.addWidget(card)

        # Progresso e Status
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setVisible(False)
        layout.addWidget(self.prog_bar)

        self.lbl_status = QLabel("Selecione as duas pastas e clique em 'Comparar e Analisar Diferenças'.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        # Tabela de Diferenças
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Arquivo Relativo", "Ação Planejada", "Motivo da Diferença", "Tamanho", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _browse_folder(self, target_line_edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta", target_line_edit.text())
        if folder:
            target_line_edit.setText(folder)
            self.btn_sync.setEnabled(False)
            self.table.setRowCount(0)

    def _start_compare(self):
        dir_a = Path(self.txt_dir_a.text().strip())
        dir_b = Path(self.txt_dir_b.text().strip())

        if not dir_a.is_dir() or not dir_b.is_dir():
            QMessageBox.warning(self, "Aviso", "Por favor, selecione duas pastas válidas existentes.")
            return

        if dir_a == dir_b:
            QMessageBox.warning(self, "Aviso", "A pasta de origem e destino não podem ser as mesmas.")
            return

        mode = self.cmb_mode.currentData()
        use_hash = self.chk_hash.isChecked()

        self.btn_compare.setEnabled(False)
        self.lbl_status.setText("Comparando diretórios e analisando arquivos...")

        def worker(ctx):
            return compare_directories(
                dir_a=dir_a,
                dir_b=dir_b,
                mode=mode,
                use_hash=use_hash,
                progress_cb=lambda cur, msg: ctx.on_progress(cur, 0, msg)
            )

        def on_done(diffs: List[SyncDifference]):
            self.btn_compare.setEnabled(True)
            self.planned_diffs = diffs
            self.table.setRowCount(len(diffs))

            for row, d in enumerate(diffs):
                self.table.setItem(row, 0, QTableWidgetItem(str(d.rel_path)))

                # Formata ação
                act_str = d.action_type
                if act_str == "copy_to_dst":
                    act_str = "Copiar A ➔ B"
                elif act_str == "copy_to_src":
                    act_str = "Copiar B ➔ A"
                elif act_str == "delete_dst":
                    act_str = "Excluir de B"

                item_act = QTableWidgetItem(act_str)
                if "Excluir" in act_str:
                    item_act.setForeground(Qt.red)
                elif "Copiar" in act_str:
                    item_act.setForeground(Qt.blue)
                self.table.setItem(row, 1, item_act)

                self.table.setItem(row, 2, QTableWidgetItem(d.reason))
                sz_str = f"{d.size_bytes / 1024:.1f} KB" if d.size_bytes else "-"
                self.table.setItem(row, 3, QTableWidgetItem(sz_str))
                self.table.setItem(row, 4, QTableWidgetItem(d.status))

            count = len(diffs)
            if count > 0:
                self.btn_sync.setEnabled(True)
                self.lbl_status.setText(f"Análise concluída! {count} diferença(s) encontrada(s). Clique em 'Executar Sincronização'.")
            else:
                self.btn_sync.setEnabled(False)
                self.lbl_status.setText("As duas pastas já estão 100% idênticas e sincronizadas!")

        self.runner.start_task(worker, on_finished=on_done)

    def _start_sync(self):
        if not self.planned_diffs:
            return

        reply = QMessageBox.question(
            self,
            "Confirmar Sincronização",
            f"Deseja aplicar as {len(self.planned_diffs)} operações de sincronização planejadas?\n"
            "Arquivos serão copiados ou excluídos conforme as regras exibidas na tabela.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_compare.setEnabled(False)
        self.btn_sync.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(0)

        def worker(ctx):
            return execute_sync(
                self.planned_diffs,
                progress_cb=ctx.on_progress
            )

        def on_prog(cur, tot, msg):
            pct = int((cur / tot) * 100) if tot > 0 else 0
            self.prog_bar.setValue(pct)
            self.lbl_status.setText(f"Sincronizando ({cur}/{tot}): {msg}")

        def on_done(res):
            self.btn_compare.setEnabled(True)
            self.btn_sync.setEnabled(False)
            self.prog_bar.setVisible(False)
            succ, fail = res

            for row, d in enumerate(self.planned_diffs):
                item = QTableWidgetItem(d.status if not d.error else f"Erro: {d.error}")
                if d.error:
                    item.setForeground(Qt.red)
                else:
                    item.setForeground(Qt.darkGreen)
                self.table.setItem(row, 4, item)

            self.lbl_status.setText(f"Sincronização concluída! {succ} operação(ões) realizada(s). Falhas: {fail}.")
            QMessageBox.information(
                self,
                "Sincronização Concluída",
                f"Sincronização finalizada!\n\nOperações bem-sucedidas: {succ}\nFalhas: {fail}"
            )

        self.runner.start_task(worker, on_progress=on_prog, on_finished=on_done)
