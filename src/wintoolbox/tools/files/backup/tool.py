"""
Ferramenta: Assistente de Backup Incremental e Snapshot de Pastas Locais.
"""
import os
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QRadioButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import BackupReport, run_incremental_backup


@register
class FolderBackupTool(Tool):
    id = "files.backup"
    name = "Assistente de Backup Incremental"
    category = "Arquivos e Pastas"
    description = "Crie backups incrementais e snapshots compactados em ZIP ou pasta espelhada de seus arquivos"
    keywords = ["backup", "cópia", "segurança", "incremental", "zip", "snapshot", "restauração", "pastas"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return FolderBackupView(self, parent)


class FolderBackupView(QWidget):
    def __init__(self, tool: FolderBackupTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.history_reports: List[BackupReport] = []
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

        # Linha 1: Origem
        r_src = QHBoxLayout()
        r_src.addWidget(QLabel("Pasta a ser copiada (Origem):"))
        self.txt_src = QLineEdit()
        r_src.addWidget(self.txt_src, stretch=1)
        btn_src = QPushButton("Selecionar...")
        btn_src.clicked.connect(lambda: self._browse_folder(self.txt_src))
        r_src.addWidget(btn_src)
        l_card.addLayout(r_src)

        # Linha 2: Destino
        r_dst = QHBoxLayout()
        r_dst.addWidget(QLabel("Onde salvar os backups (Destino):"))
        self.txt_dst = QLineEdit(str(Path.home() / "Backups"))
        r_dst.addWidget(self.txt_dst, stretch=1)
        btn_dst = QPushButton("Selecionar...")
        btn_dst.clicked.connect(lambda: self._browse_folder(self.txt_dst))
        r_dst.addWidget(btn_dst)
        l_card.addLayout(r_dst)

        # Linha 3: Formato do Backup
        r_mode = QHBoxLayout()
        r_mode.addWidget(QLabel("Formato do Backup:"))
        self.rb_zip = QRadioButton("Arquivo Compactado ZIP com Carimbo de Data/Hora (Snapshot)")
        self.rb_zip.setChecked(True)
        self.rb_folder = QRadioButton("Pasta Incremental Espelhada (Apenas copia arquivos novos/alterados)")
        self.group_mode = QButtonGroup()
        self.group_mode.addButton(self.rb_zip)
        self.group_mode.addButton(self.rb_folder)
        r_mode.addWidget(self.rb_zip)
        r_mode.addWidget(self.rb_folder)
        r_mode.addStretch()
        l_card.addLayout(r_mode)

        # Linha 4: Botão de Execução
        r_btn = QHBoxLayout()
        self.btn_run = QPushButton("Executar Backup Agora")
        self.btn_run.setProperty("class", "primary")
        self.btn_run.clicked.connect(self._start_backup)
        r_btn.addWidget(self.btn_run)
        r_btn.addStretch()
        l_card.addLayout(r_btn)

        layout.addWidget(card)

        # Progresso e Status
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setVisible(False)
        layout.addWidget(self.prog_bar)

        self.lbl_status = QLabel("Selecione as pastas e clique em 'Executar Backup Agora'.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        # Histórico de Backups
        lbl_hist = QLabel("Histórico de Backups Realizados:")
        lbl_hist.setStyleSheet("font-weight: 600;")
        layout.addWidget(lbl_hist)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Data/Hora", "Origem", "Destino / Arquivo", "Arquivos Copiados", "Tamanho"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        r_acts = QHBoxLayout()
        btn_open_target = QPushButton("Abrir Pasta de Destino no Explorer")
        btn_open_target.clicked.connect(self._open_target_folder)
        r_acts.addWidget(btn_open_target)
        r_acts.addStretch()
        layout.addLayout(r_acts)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _browse_folder(self, line_edit: QLineEdit):
        f = QFileDialog.getExistingDirectory(self, "Selecionar Diretório", line_edit.text())
        if f:
            line_edit.setText(f)

    def _start_backup(self):
        src_str = self.txt_src.text().strip()
        dst_str = self.txt_dst.text().strip()

        src = Path(src_str)
        dst = Path(dst_str)

        if not src.is_dir():
            QMessageBox.warning(self, "Aviso", "A pasta de origem especificada não existe.")
            return

        mode = "zip" if self.rb_zip.isChecked() else "folder"

        self.btn_run.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(0)
        self.lbl_status.setText("Iniciando processo de backup...")

        def worker(ctx):
            return run_incremental_backup(
                source_dir=src,
                target_base=dst,
                backup_mode=mode,
                progress_cb=ctx.on_progress
            )

        def on_prog(cur, tot, msg):
            pct = int((cur / tot) * 100) if tot > 0 else 0
            self.prog_bar.setValue(pct)
            self.lbl_status.setText(f"Processando ({cur}/{tot}): {msg}")

        def on_done(rep: BackupReport):
            self.btn_run.setEnabled(True)
            self.prog_bar.setVisible(False)
            self.history_reports.insert(0, rep)

            row = 0
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(rep.timestamp))
            self.table.setItem(row, 1, QTableWidgetItem(rep.source_dir.name))
            self.table.setItem(row, 2, QTableWidgetItem(str(rep.target_path)))
            self.table.setItem(row, 3, QTableWidgetItem(f"{rep.files_copied} arquivo(s)"))
            sz_mb = rep.bytes_copied / (1024 * 1024)
            self.table.setItem(row, 4, QTableWidgetItem(f"{sz_mb:.1f} MB"))

            msg = f"Backup concluído com sucesso! {rep.files_copied} arquivo(s) transferidos ({sz_mb:.1f} MB)."
            if rep.files_skipped > 0:
                msg += f" {rep.files_skipped} arquivo(s) ignorados (já atualizados)."
            self.lbl_status.setText(msg)

            QMessageBox.information(
                self,
                "Backup Finalizado",
                f"Backup gerado com sucesso!\n\nSalvo em:\n{rep.target_path}\n\nArquivos copiados: {rep.files_copied} ({sz_mb:.1f} MB)"
            )

        def on_err(err_msg: str):
            self.btn_run.setEnabled(True)
            self.prog_bar.setVisible(False)
            self.lbl_status.setText("Falha no backup.")
            QMessageBox.critical(self, "Erro no Backup", f"Ocorreu um erro ao executar o backup:\n{err_msg}")

        self.runner.start_task(worker, on_progress=on_prog, on_finished=on_done, on_error=on_err)

    def _open_target_folder(self):
        dst = Path(self.txt_dst.text().strip())
        if dst.is_dir():
            os.startfile(str(dst))
