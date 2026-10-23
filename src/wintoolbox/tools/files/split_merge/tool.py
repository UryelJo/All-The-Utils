"""
Ferramenta: Divisor e Juntador de Arquivos (File Split & Merge).
Permite dividir arquivos volumosos em partes menores (ex: 25 MB para envio por e-mail/Discord) e reconstituí-los.
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import merge_files, split_file

@register
class SplitMergeTool(Tool):
    id = "files.split_merge"
    name = "Divisor e Juntador de Arquivos"
    category = "Arquivos e Pastas"
    description = "Divide arquivos grandes em partes de tamanho fixo e remonta as partes em um único arquivo"
    keywords = ["dividir", "juntar", "split", "merge", "partes", "chunk", "tamanho", "arquivos"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return SplitMergeView(self, parent)

class SplitMergeView(QWidget):
    def __init__(self, tool: SplitMergeTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
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

        tabs = QTabWidget()

        # ABA 1: Dividir Arquivo
        tab_split = QWidget()
        l_sp = QVBoxLayout(tab_split)
        l_sp.setSpacing(12)

        card_sp = QFrame()
        card_sp.setProperty("class", "card")
        l_csp = QVBoxLayout(card_sp)
        l_csp.setSpacing(10)

        # Arquivo de Origem
        row_s1 = QHBoxLayout()
        row_s1.addWidget(QLabel("Arquivo Original:"))
        self.txt_split_src = QLineEdit()
        self.txt_split_src.setReadOnly(True)
        row_s1.addWidget(self.txt_split_src, stretch=1)

        btn_browse_split = QPushButton("Selecionar Arquivo...")
        btn_browse_split.clicked.connect(self._select_split_src)
        row_s1.addWidget(btn_browse_split)
        l_csp.addLayout(row_s1)

        # Tamanho das Partes
        row_s2 = QHBoxLayout()
        row_s2.addWidget(QLabel("Tamanho de Cada Parte (MB):"))
        self.spin_part_mb = QSpinBox()
        self.spin_part_mb.setRange(1, 10240)
        self.spin_part_mb.setValue(25)  # 25MB padrão Discord/E-mail
        row_s2.addWidget(self.spin_part_mb)

        self.cmb_presets = QComboBox()
        self.cmb_presets.addItems([
            "Predefinição: 25 MB (Discord / E-mail)",
            "Predefinição: 50 MB",
            "Predefinição: 100 MB",
            "Predefinição: 700 MB (CD)",
            "Predefinição: 4400 MB (DVD)"
        ])
        self.cmb_presets.currentIndexChanged.connect(self._apply_preset_size)
        row_s2.addWidget(self.cmb_presets)
        row_s2.addStretch()
        l_csp.addLayout(row_s2)

        # Pasta de Saída
        row_s3 = QHBoxLayout()
        row_s3.addWidget(QLabel("Salvar Partes em:"))
        self.txt_split_dst = QLineEdit()
        self.txt_split_dst.setReadOnly(True)
        row_s3.addWidget(self.txt_split_dst, stretch=1)

        btn_browse_dst = QPushButton("Selecionar Pasta...")
        btn_browse_dst.clicked.connect(self._select_split_dst)
        row_s3.addWidget(btn_browse_dst)
        l_csp.addLayout(row_s3)

        btn_do_split = QPushButton("Iniciar Divisão do Arquivo")
        btn_do_split.setProperty("class", "primary")
        btn_do_split.clicked.connect(self._start_split)
        l_csp.addWidget(btn_do_split)

        l_sp.addWidget(card_sp)
        l_sp.addStretch()
        tabs.addTab(tab_split, "Dividir Arquivo em Partes")

        # ABA 2: Juntar Arquivos
        tab_merge = QWidget()
        l_mg = QVBoxLayout(tab_merge)
        l_mg.setSpacing(12)

        card_mg = QFrame()
        card_mg.setProperty("class", "card")
        l_cmg = QVBoxLayout(card_mg)
        l_cmg.setSpacing(10)

        row_m1 = QHBoxLayout()
        row_m1.addWidget(QLabel("Partes Selecionadas:"))
        self.txt_merge_info = QLineEdit()
        self.txt_merge_info.setReadOnly(True)
        self.txt_merge_info.setPlaceholderText("Nenhuma parte selecionada...")
        row_m1.addWidget(self.txt_merge_info, stretch=1)

        btn_browse_parts = QPushButton("Selecionar Partes (.part001...)...")
        btn_browse_parts.clicked.connect(self._select_merge_parts)
        row_m1.addWidget(btn_browse_parts)
        l_cmg.addLayout(row_m1)

        row_m2 = QHBoxLayout()
        row_m2.addWidget(QLabel("Salvar Arquivo Reconstruído como:"))
        self.txt_merge_out = QLineEdit()
        self.txt_merge_out.setReadOnly(True)
        row_m2.addWidget(self.txt_merge_out, stretch=1)

        btn_browse_out = QPushButton("Escolher Destino...")
        btn_browse_out.clicked.connect(self._select_merge_out)
        row_m2.addWidget(btn_browse_out)
        l_cmg.addLayout(row_m2)

        btn_do_merge = QPushButton("Juntar e Reconstruir Arquivo")
        btn_do_merge.setProperty("class", "primary")
        btn_do_merge.clicked.connect(self._start_merge)
        l_cmg.addWidget(btn_do_merge)

        l_mg.addWidget(card_mg)
        l_mg.addStretch()
        tabs.addTab(tab_merge, "Juntar Partes em Arquivo Original")

        layout.addWidget(tabs)

        # Progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Pronto para executar divisão ou junção.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        self.selected_merge_parts: List[Path] = []

    def _select_split_src(self):
        f, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo para Dividir")
        if f:
            p = Path(f)
            self.txt_split_src.setText(str(p))
            if not self.txt_split_dst.text():
                self.txt_split_dst.setText(str(p.parent))

    def _select_split_dst(self):
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Destino", self.txt_split_dst.text())
        if d:
            self.txt_split_dst.setText(d)

    def _apply_preset_size(self, idx: int):
        sizes = [25, 50, 100, 700, 4400]
        if 0 <= idx < len(sizes):
            self.spin_part_mb.setValue(sizes[idx])

    def _start_split(self):
        src_str = self.txt_split_src.text().strip()
        dst_str = self.txt_split_dst.text().strip()
        if not src_str or not Path(src_str).exists():
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo de origem válido.")
            return

        part_mb = self.spin_part_mb.value()
        part_bytes = part_mb * 1024 * 1024
        src = Path(src_str)
        dst = Path(dst_str) if dst_str else src.parent

        self.progress_bar.setValue(0)
        self.lbl_status.setText("Dividindo arquivo em partes...")

        def worker(ctx):
            def on_progress(p):
                ctx.send_progress(p, "")
            return split_file(src, part_bytes, dst, on_progress)

        def on_task_progress(percent, _total, _msg):
            self.progress_bar.setValue(percent)

        def on_done(parts: List[Path]):
            self.progress_bar.setValue(100)
            self.lbl_status.setText(f"Arquivo dividido com sucesso em {len(parts)} parte(s)!")
            QMessageBox.information(
                self,
                "Divisão Concluída",
                f"O arquivo foi dividido em {len(parts)} partes de até {part_mb} MB salvas em:\n{dst}"
            )

        def on_error(err):
            QMessageBox.critical(self, "Erro", f"Falha ao dividir arquivo:\n{err}")

        self.runner.start_task(worker, on_progress=on_task_progress, on_finished=on_done, on_error=on_error)

    def _select_merge_parts(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar Partes para Juntar")
        if files:
            self.selected_merge_parts = [Path(f) for f in files]
            self.selected_merge_parts.sort(key=lambda p: p.name)
            self.txt_merge_info.setText(f"{len(self.selected_merge_parts)} partes selecionadas")

            # Sugere nome original removendo .part001
            first = self.selected_merge_parts[0]
            orig_name = first.name
            if ".part" in orig_name:
                orig_name = orig_name[:orig_name.rfind(".part")]
            self.txt_merge_out.setText(str(first.parent / orig_name))

    def _select_merge_out(self):
        cur = self.txt_merge_out.text()
        f, _ = QFileDialog.getSaveFileName(self, "Salvar Arquivo Reconstruído", cur)
        if f:
            self.txt_merge_out.setText(f)

    def _start_merge(self):
        if not self.selected_merge_parts:
            QMessageBox.warning(self, "Aviso", "Selecione as partes a serem juntadas.")
            return

        out_str = self.txt_merge_out.text().strip()
        if not out_str:
            QMessageBox.warning(self, "Aviso", "Defina o arquivo de saída.")
            return

        out_file = Path(out_str)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Juntando partes do arquivo...")

        def worker(ctx):
            def on_progress(p):
                ctx.send_progress(p, "")
            merge_files(self.selected_merge_parts, out_file, on_progress)

        def on_task_progress(percent, _total, _msg):
            self.progress_bar.setValue(percent)

        def on_done(_):
            self.progress_bar.setValue(100)
            self.lbl_status.setText(f"Arquivo reconstruído com sucesso!")
            QMessageBox.information(
                self,
                "Junção Concluída",
                f"As partes foram unificadas com sucesso no arquivo:\n{out_file}"
            )

        def on_error(err):
            QMessageBox.critical(self, "Erro", f"Falha ao juntar partes:\n{err}")

        self.runner.start_task(worker, on_progress=on_task_progress, on_finished=on_done, on_error=on_error)
