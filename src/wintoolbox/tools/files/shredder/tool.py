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

def shred_single_file(file_path: Path, passes: int = 3, progress_cb=None) -> None:
    """Sobrescreve o arquivo fisicamente no disco antes de apagá-lo."""
    if not file_path.exists() or not file_path.is_file():
        return

    length = file_path.stat().st_size
    chunk_size = 65536

    with open(file_path, "r+b") as f:
        for p in range(passes):
            f.seek(0)
            if p == 0:
                pattern = b"\x00" * chunk_size
            elif p == 1:
                pattern = b"\xff" * chunk_size
            else:
                pattern = secrets.token_bytes(chunk_size)

            written = 0
            while written < length:
                to_write = min(chunk_size, length - written)
                f.write(pattern[:to_write])
                written += to_write
                if progress_cb and length > 0:
                    progress_cb(int(((p * length + written) / (passes * length)) * 90))

            f.flush()
            os.fsync(f.fileno())

        # Trunca para tamanho zero
        f.truncate(0)

    # Renomeia para nome anônimo na MFT
    random_name = file_path.parent / f"tmp_shred_{secrets.token_hex(8)}.tmp"
    file_path.rename(random_name)

    # Remove permanentemente
    random_name.unlink(missing_ok=True)
    if progress_cb:
        progress_cb(100)

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
        self.table.setRowCount(len(self.files_to_shred))
        for row, p in enumerate(self.files_to_shred):
            sz = p.stat().st_size if p.exists() else 0
            self.table.setItem(row, 0, QTableWidgetItem(p.name))
            self.table.setItem(row, 1, QTableWidgetItem(self._format_size(sz)))
            self.table.setItem(row, 2, QTableWidgetItem(str(p.parent)))

        self.btn_shred.setEnabled(len(self.files_to_shred) > 0)
        self.lbl_status.setText(f"{len(self.files_to_shred)} arquivo(s) prontos para trituração.")

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{round(size_bytes / 1024, 1)} KB"
        return f"{round(size_bytes / (1024 * 1024), 2)} MB"

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
            total = len(files)
            for idx, f in enumerate(files):
                def on_file_p(percent):
                    overall = int(((idx + (percent / 100)) / total) * 100)
                    ctx.send_progress(overall, f"Triturando {f.name} ({idx+1}/{total})...")

                shred_single_file(f, passes=passes, progress_cb=on_file_p)
            return total

        def on_task_progress(percent, msg):
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
