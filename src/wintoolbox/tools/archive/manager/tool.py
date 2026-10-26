"""
Ferramenta: Gerenciador de Compactação e Extração (ZIP, TAR, TAR.GZ).
Permite compactar arquivos e pastas, extrair com relatório de progresso e inspecionar conteúdo sem extrair.
"""
import os
import tarfile
import zipfile
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import (
    compress_items,
    extract_archive,
    format_archive_size,
    inspect_archive,
)
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

@register
class ArchiveManagerTool(Tool):
    id = "archive.manager"
    name = "Compactador e Extrator de Arquivos"
    category = "Compactação"
    description = "Compacte arquivos e pastas em ZIP/TAR, extraia pacotes (ZIP, TAR, 7Z, RAR) e inspecione conteúdo interno"
    keywords = ["zip", "tar", "7z", "rar", "compactar", "extrair", "descompactar", "arquivo", "pasta", "compressao"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ArchiveManagerView(self, parent)

class ArchiveManagerView(QWidget):
    def __init__(self, tool: ArchiveManagerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.source_items_to_compress: List[Path] = []
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

        # ABA 1: Compactar Arquivos/Pastas
        tab_comp = QWidget()
        l_comp = QVBoxLayout(tab_comp)
        l_comp.setSpacing(12)

        card_c = QFrame()
        card_c.setProperty("class", "card")
        l_cc = QVBoxLayout(card_c)
        l_cc.setSpacing(10)

        row_c1 = QHBoxLayout()
        row_c1.addWidget(QLabel("Itens a Compactar:"))
        self.lbl_comp_count = QLabel("Nenhum item selecionado.")
        self.lbl_comp_count.setProperty("class", "secondary")
        row_c1.addWidget(self.lbl_comp_count, stretch=1)

        btn_add_files = QPushButton("Adicionar Arquivos...")
        btn_add_files.clicked.connect(self._add_files_to_compress)
        row_c1.addWidget(btn_add_files)

        btn_add_dir = QPushButton("Adicionar Pasta...")
        btn_add_dir.clicked.connect(self._add_dir_to_compress)
        row_c1.addWidget(btn_add_dir)

        btn_clear_c = QPushButton("Limpar")
        btn_clear_c.clicked.connect(self._clear_compress_list)
        row_c1.addWidget(btn_clear_c)
        l_cc.addLayout(row_c1)

        row_c2 = QHBoxLayout()
        row_c2.addWidget(QLabel("Formato de Compactação:"))
        self.cmb_fmt = QComboBox()
        self.cmb_fmt.addItems(["ZIP (Compatível com Windows)", "TAR.GZ (Linux / Web)", "TAR (Sem compressão)"])
        row_c2.addWidget(self.cmb_fmt)

        row_c2.addSpacing(16)
        row_c2.addWidget(QLabel("Salvar Arquivo Como:"))
        self.txt_out_archive = QLineEdit()
        self.txt_out_archive.setPlaceholderText("Defina o caminho de saída...")
        row_c2.addWidget(self.txt_out_archive, stretch=1)

        btn_browse_out = QPushButton("Escolher Destino...")
        btn_browse_out.clicked.connect(self._browse_compress_out)
        row_c2.addWidget(btn_browse_out)
        l_cc.addLayout(row_c2)

        self.btn_run_comp = QPushButton("Iniciar Compactação")
        self.btn_run_comp.setProperty("class", "primary")
        self.btn_run_comp.setEnabled(False)
        self.btn_run_comp.clicked.connect(self._start_compress)
        l_cc.addWidget(self.btn_run_comp)

        l_comp.addWidget(card_c)
        l_comp.addStretch()
        tabs.addTab(tab_comp, "Compactar Arquivos e Pastas")

        # ABA 2: Extrair e Inspecionar
        tab_ext = QWidget()
        l_ext = QVBoxLayout(tab_ext)
        l_ext.setSpacing(12)

        card_e = QFrame()
        card_e.setProperty("class", "card")
        l_ce = QVBoxLayout(card_e)
        l_ce.setSpacing(10)

        row_e1 = QHBoxLayout()
        row_e1.addWidget(QLabel("Arquivo Compactado:"))
        self.txt_archive_in = QLineEdit()
        self.txt_archive_in.setReadOnly(True)
        row_e1.addWidget(self.txt_archive_in, stretch=1)

        btn_browse_arch = QPushButton("Selecionar Arquivo (.zip, .tar, .tar.gz)...")
        btn_browse_arch.clicked.connect(self._browse_archive_in)
        row_e1.addWidget(btn_browse_arch)
        l_ce.addLayout(row_e1)

        row_e2 = QHBoxLayout()
        row_e2.addWidget(QLabel("Extrair para:"))
        self.txt_extract_dst = QLineEdit()
        self.txt_extract_dst.setReadOnly(True)
        row_e2.addWidget(self.txt_extract_dst, stretch=1)

        btn_browse_dst = QPushButton("Escolher Pasta de Destino...")
        btn_browse_dst.clicked.connect(self._browse_extract_dst)
        row_e2.addWidget(btn_browse_dst)

        self.btn_run_ext = QPushButton("Extrair Tudo")
        self.btn_run_ext.setProperty("class", "primary")
        self.btn_run_ext.setEnabled(False)
        self.btn_run_ext.clicked.connect(self._start_extract)
        row_e2.addWidget(self.btn_run_ext)
        l_ce.addLayout(row_e2)

        l_ext.addWidget(card_e)

        # Tabela de Conteúdo Inspecionado
        l_ext.addWidget(QLabel("Conteúdo do Arquivo (Visualização sem Extrair):"))
        self.table_contents = QTableWidget(0, 3)
        self.table_contents.setHorizontalHeaderLabels(["Nome Interno", "Tamanho Real", "Tamanho Comprimido"])
        self.table_contents.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_contents.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_contents.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_contents.verticalHeader().setVisible(False)
        self.table_contents.setFixedHeight(220)
        enable_sorting_on_table(self.table_contents)
        l_ext.addWidget(self.table_contents)

        tabs.addTab(tab_ext, "Extrair e Inspecionar Pacotes")

        layout.addWidget(tabs)

        # Barra de Progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Pronto para compactar ou extrair.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _add_files_to_compress(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar Arquivos para Compactar")
        if files:
            for f in files:
                p = Path(f)
                if p not in self.source_items_to_compress:
                    self.source_items_to_compress.append(p)
            self._update_compress_ui()

    def _add_dir_to_compress(self):
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Compactar")
        if d:
            p = Path(d)
            if p not in self.source_items_to_compress:
                self.source_items_to_compress.append(p)
            self._update_compress_ui()

    def _clear_compress_list(self):
        self.source_items_to_compress.clear()
        self._update_compress_ui()

    def _update_compress_ui(self):
        count = len(self.source_items_to_compress)
        self.lbl_comp_count.setText(f"{count} item(ns) selecionado(s)")
        self.btn_run_comp.setEnabled(count > 0 and bool(self.txt_out_archive.text()))

        if count > 0 and not self.txt_out_archive.text():
            first = self.source_items_to_compress[0]
            fmt_ext = ".zip" if "ZIP" in self.cmb_fmt.currentText() else ".tar.gz"
            suggested = first.parent / f"{first.stem}_compactado{fmt_ext}"
            self.txt_out_archive.setText(str(suggested))
            self.btn_run_comp.setEnabled(True)

    def _browse_compress_out(self):
        fmt = "Arquivo ZIP (*.zip)" if "ZIP" in self.cmb_fmt.currentText() else "Arquivo TAR.GZ (*.tar.gz)"
        path, _ = QFileDialog.getSaveFileName(self, "Salvar Arquivo Compactado", self.txt_out_archive.text(), fmt)
        if path:
            self.txt_out_archive.setText(path)
            self.btn_run_comp.setEnabled(len(self.source_items_to_compress) > 0)

    def _start_compress(self):
        out_str = self.txt_out_archive.text().strip()
        if not out_str or not self.source_items_to_compress:
            return

        out_path = Path(out_str)
        fmt = "ZIP" if "ZIP" in self.cmb_fmt.currentText() else ("TAR.GZ" if "TAR.GZ" in self.cmb_fmt.currentText() else "TAR")

        self.btn_run_comp.setEnabled(False)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Compactando arquivos...")

        sources = list(self.source_items_to_compress)

        def worker(ctx):
            def on_progress(p):
                ctx.send_progress(p, "")
            compress_items(sources, out_path, fmt, on_progress)

        def on_task_progress(percent, _total, _msg):
            self.progress_bar.setValue(percent)

        def on_done(_):
            self.btn_run_comp.setEnabled(True)
            self.progress_bar.setValue(100)
            self.lbl_status.setText(f"Arquivo compactado com sucesso em: {out_path.name}")
            QMessageBox.information(
                self,
                "Compactação Concluída",
                f"Arquivo compactado salvo com sucesso em:\n{out_path}"
            )

        def on_error(err):
            self.btn_run_comp.setEnabled(True)
            QMessageBox.critical(self, "Erro", f"Falha na compactação:\n{err}")

        self.runner.start_task(worker, on_progress=on_task_progress, on_finished=on_done, on_error=on_error)

    def _browse_archive_in(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Arquivo Compactado",
            "",
            "Arquivos Compactados (*.zip *.7z *.rar *.tar *.tar.gz *.tgz *.tar.bz2 *.tar.xz)"
        )
        if f:
            p = Path(f)
            self.txt_archive_in.setText(str(p))
            # Sugere pasta de extração com o mesmo nome do arquivo
            extract_folder = p.parent / p.stem
            self.txt_extract_dst.setText(str(extract_folder))
            self.btn_run_ext.setEnabled(True)
            self._load_archive_contents(p)

    def _browse_extract_dst(self):
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Destino", self.txt_extract_dst.text())
        if d:
            self.txt_extract_dst.setText(d)

    def _load_archive_contents(self, archive_path: Path):
        try:
            items = inspect_archive(archive_path)
            with batch_table_update(self.table_contents):
                self.table_contents.setRowCount(len(items))
                for row, it in enumerate(items):
                    prefix = "[DIR] " if it["is_dir"] else ""
                    self.table_contents.setItem(row, 0, SmartTableWidgetItem(f"{prefix}{it['name']}", sort_value=it["name"].lower(), user_data=it))
                    self.table_contents.setItem(row, 1, SmartTableWidgetItem(self._format_size(it["size"]), sort_value=it["size"]))
                    self.table_contents.setItem(row, 2, SmartTableWidgetItem(self._format_size(it["compressed"]), sort_value=it["compressed"]))
        except Exception as e:
            QMessageBox.warning(self, "Aviso", f"Não foi possível inspecionar o arquivo:\n{str(e)}")

    def _start_extract(self):
        arch_str = self.txt_archive_in.text().strip()
        dst_str = self.txt_extract_dst.text().strip()
        if not arch_str or not dst_str:
            return

        arch_path = Path(arch_str)
        dst_path = Path(dst_str)
        dst_path.mkdir(parents=True, exist_ok=True)

        self.btn_run_ext.setEnabled(False)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Extraindo conteúdo...")

        def worker(ctx):
            def on_progress(p):
                ctx.send_progress(p, "")
            return extract_archive(arch_path, dst_path, on_progress)

        def on_task_progress(percent, _total, _msg):
            self.progress_bar.setValue(percent)

        def on_done(count):
            self.btn_run_ext.setEnabled(True)
            self.progress_bar.setValue(100)
            self.lbl_status.setText(f"{count} arquivo(s) extraídos com sucesso!")
            QMessageBox.information(
                self,
                "Extração Concluída",
                f"{count} arquivos foram extraídos com sucesso na pasta:\n{dst_path}"
            )

        def on_error(err):
            self.btn_run_ext.setEnabled(True)
            QMessageBox.critical(self, "Erro", f"Falha na extração:\n{err}")

        self.runner.start_task(worker, on_progress=on_task_progress, on_finished=on_done, on_error=on_error)

    def _format_size(self, size_bytes: int) -> str:
        return format_archive_size(size_bytes)
