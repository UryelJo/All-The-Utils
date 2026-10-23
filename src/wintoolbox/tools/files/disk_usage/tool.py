"""
Ferramenta: Analisador de Espaço em Disco e Pastas Volumosas.
Mapeia o consumo de armazenamento por subpastas e por tipos de extensão de arquivos.
"""
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner

class DiskItem:
    def __init__(self, name: str, path: str, size: int, is_dir: bool, count: int = 1):
        self.name = name
        self.path = path
        self.size = size
        self.is_dir = is_dir
        self.count = count

@register
class DiskUsageTool(Tool):
    id = "files.disk_usage"
    name = "Analisador de Espaço em Disco"
    category = "Arquivos e Pastas"
    description = "Mapeia as maiores pastas, arquivos pesados e tipos de extensões que mais ocupam espaço"
    keywords = ["disco", "espaco", "tamanho", "pastas", "armazenamento", "windirstat", "analisador"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DiskUsageView(self, parent)

class DiskUsageView(QWidget):
    def __init__(self, tool: DiskUsageTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.top_items: List[DiskItem] = []
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

        # Seletor de Pasta / Unidade
        card_dir = QFrame()
        card_dir.setProperty("class", "card")
        l_dir = QVBoxLayout(card_dir)
        l_dir.setSpacing(10)

        row_sel = QHBoxLayout()
        row_sel.addWidget(QLabel("Pasta ou Unidade para Analisar:"))
        self.txt_path = QLineEdit(str(Path.home()))
        row_sel.addWidget(self.txt_path, stretch=1)

        btn_browse = QPushButton("Selecionar Pasta...")
        btn_browse.clicked.connect(self._select_dir)
        row_sel.addWidget(btn_browse)

        self.btn_scan = QPushButton("Analisar Armazenamento")
        self.btn_scan.setProperty("class", "primary")
        self.btn_scan.clicked.connect(self._start_analysis)
        row_sel.addWidget(self.btn_scan)
        l_dir.addLayout(row_sel)

        layout.addWidget(card_dir)

        # Status e Progresso
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_stats = QLabel("Selecione uma pasta e clique em 'Analisar Armazenamento'.")
        self.lbl_stats.setProperty("class", "secondary")
        layout.addWidget(self.lbl_stats)

        # Abas de Visualização
        tabs = QTabWidget()

        # ABA 1: Maiores Itens
        tab_top = QWidget()
        l_top = QVBoxLayout(tab_top)
        l_top.setSpacing(8)

        self.table_items = QTableWidget(0, 4)
        self.table_items.setHorizontalHeaderLabels(["Nome", "Tipo", "Tamanho", "Caminho Completo"])
        self.table_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_items.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_items.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table_items.verticalHeader().setVisible(False)
        self.table_items.setFixedHeight(280)
        self.table_items.cellDoubleClicked.connect(self._on_item_double_clicked)
        l_top.addWidget(self.table_items)

        row_top_act = QHBoxLayout()
        btn_open_exp = QPushButton("Abrir Selecionado no Explorador")
        btn_open_exp.clicked.connect(self._open_selected_in_explorer)
        row_top_act.addWidget(btn_open_exp)
        row_top_act.addStretch()
        l_top.addLayout(row_top_act)

        tabs.addTab(tab_top, "Maiores Pastas e Arquivos")

        # ABA 2: Distribuição por Extensões
        tab_ext = QWidget()
        l_ext = QVBoxLayout(tab_ext)
        l_ext.setSpacing(8)

        self.table_ext = QTableWidget(0, 3)
        self.table_ext.setHorizontalHeaderLabels(["Extensão", "Quantidade de Arquivos", "Espaço Ocupado"])
        self.table_ext.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_ext.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_ext.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_ext.verticalHeader().setVisible(False)
        self.table_ext.setFixedHeight(280)
        l_ext.addWidget(self.table_ext)

        tabs.addTab(tab_ext, "Consumo por Extensão de Arquivo")

        layout.addWidget(tabs)
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _select_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta", self.txt_path.text())
        if folder:
            self.txt_path.setText(folder)

    def _start_analysis(self):
        folder = self.txt_path.text().strip()
        if not folder or not Path(folder).exists():
            QMessageBox.warning(self, "Aviso", "Selecione uma pasta ou unidade válida existente.")
            return

        self.btn_scan.setEnabled(False)
        self.progress_bar.setValue(10)
        self.lbl_stats.setText("Examinando diretório...")

        def worker(ctx):
            target = Path(folder)
            top_level_items = []
            ext_sizes = defaultdict(int)
            ext_counts = defaultdict(int)
            total_dir_bytes = 0

            # 1. Analisa itens de primeiro nível para o relatório de maiores itens
            try:
                for entry in os.scandir(target):
                    try:
                        if entry.is_file(follow_symlinks=False):
                            s = entry.stat().st_size
                            top_level_items.append(DiskItem(entry.name, entry.path, s, False))
                            total_dir_bytes += s
                            ext = Path(entry.name).suffix.lower() or "(sem extensão)"
                            ext_sizes[ext] += s
                            ext_counts[ext] += 1
                        elif entry.is_dir(follow_symlinks=False):
                            # Calcula tamanho recursivo da subpasta
                            dir_size, dir_count, sub_exts, sub_counts = self._calc_dir_size(entry.path)
                            top_level_items.append(DiskItem(entry.name, entry.path, dir_size, True, dir_count))
                            total_dir_bytes += dir_size
                            for k, v in sub_exts.items():
                                ext_sizes[k] += v
                            for k, v in sub_counts.items():
                                ext_counts[k] += v
                    except Exception:
                        pass
            except Exception as e:
                raise e

            # Ordena maiores itens de primeiro nível
            top_level_items.sort(key=lambda x: x.size, reverse=True)

            # Ordena extensões
            sorted_exts = sorted(ext_sizes.items(), key=lambda x: x[1], reverse=True)

            return top_level_items, sorted_exts, ext_counts, total_dir_bytes

        def on_done(result):
            items, sorted_exts, ext_counts, total_bytes = result
            self.btn_scan.setEnabled(True)
            self.progress_bar.setValue(100)
            self.top_items = items

            # Preenche tabela 1
            self.table_items.setRowCount(len(items))
            for row, it in enumerate(items):
                name_item = QTableWidgetItem(f"[DIR] {it.name}" if it.is_dir else it.name)
                if it.is_dir:
                    name_item.setStyleSheet("font-weight: 600;")
                self.table_items.setItem(row, 0, name_item)
                self.table_items.setItem(row, 1, QTableWidgetItem(f"Pasta ({it.count} itens)" if it.is_dir else "Arquivo"))
                self.table_items.setItem(row, 2, QTableWidgetItem(self._format_size(it.size)))
                self.table_items.setItem(row, 3, QTableWidgetItem(it.path))

            # Preenche tabela 2
            self.table_ext.setRowCount(len(sorted_exts))
            for row, (ext, sz) in enumerate(sorted_exts):
                count = ext_counts.get(ext, 0)
                self.table_ext.setItem(row, 0, QTableWidgetItem(ext))
                self.table_ext.setItem(row, 1, QTableWidgetItem(f"{count:,}"))
                self.table_ext.setItem(row, 2, QTableWidgetItem(self._format_size(sz)))

            mb_total = round(total_bytes / (1024 * 1024), 2)
            gb_total = round(total_bytes / (1024 * 1024 * 1024), 2)
            display_total = f"{gb_total} GB" if gb_total >= 1.0 else f"{mb_total} MB"
            self.lbl_stats.setText(f"Varredura concluída! Tamanho total calculado: {display_total} ({len(items)} itens no nível inicial).")

        def on_error(err):
            self.btn_scan.setEnabled(True)
            QMessageBox.critical(self, "Erro", f"Falha ao analisar pasta:\n{err}")

        self.runner.start_task(worker, on_finished=on_done, on_error=on_error)

    def _calc_dir_size(self, dir_path: str):
        total_size = 0
        total_count = 0
        ext_sizes = defaultdict(int)
        ext_counts = defaultdict(int)

        for root, dirs, files in os.walk(dir_path):
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    s = os.path.getsize(fp)
                    total_size += s
                    total_count += 1
                    ext = Path(f).suffix.lower() or "(sem extensão)"
                    ext_sizes[ext] += s
                    ext_counts[ext] += 1
                except Exception:
                    pass

        return total_size, total_count, ext_sizes, ext_counts

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{round(size_bytes / 1024, 1)} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{round(size_bytes / (1024 * 1024), 2)} MB"
        return f"{round(size_bytes / (1024 * 1024 * 1024), 2)} GB"

    def _on_item_double_clicked(self, row: int, col: int):
        if 0 <= row < len(self.top_items):
            it = self.top_items[row]
            if it.is_dir:
                self.txt_path.setText(it.path)
                self._start_analysis()

    def _open_selected_in_explorer(self):
        row = self.table_items.currentRow()
        if 0 <= row < len(self.top_items):
            p = self.top_items[row].path
            target = p if os.path.isdir(p) else os.path.dirname(p)
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))
