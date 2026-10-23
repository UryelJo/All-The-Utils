"""
Ferramenta: Pesquisa Avançada de Arquivos e Conteúdo (File & Content Search).
"""
import os
from pathlib import Path
import subprocess
import time
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import SearchResultItem, search_files


@register
class FileSearchTool(Tool):
    id = "files.search"
    name = "Pesquisa Avançada de Arquivos e Conteúdo"
    category = "Arquivos e Pastas"
    description = "Localize arquivos instantaneamente por nome, tamanho, datas e busca por conteúdo de texto interno"
    keywords = ["busca", "pesquisa", "procurar", "find", "search", "grep", "conteúdo", "texto", "arquivos"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return FileSearchView(self, parent)


class FileSearchView(QWidget):
    def __init__(self, tool: FileSearchTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.current_results: List[SearchResultItem] = []
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

        # Card de Filtros
        card = QFrame()
        card.setProperty("class", "card")
        l_card = QVBoxLayout(card)
        l_card.setSpacing(10)

        # Linha 1: Pasta
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Pesquisar em:"))
        self.txt_folder = QLineEdit(str(Path.home()))
        r1.addWidget(self.txt_folder, stretch=1)
        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._browse_folder)
        r1.addWidget(btn_browse)
        l_card.addLayout(r1)

        # Linha 2: Nome do Arquivo
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Nome do arquivo (Glob/Curingas):"))
        self.txt_pattern = QLineEdit("*")
        self.txt_pattern.setPlaceholderText("Ex: *.pdf, relatorio_*.xlsx, config.json")
        r2.addWidget(self.txt_pattern, stretch=1)

        self.chk_case = QCheckBox("Diferenciar maiúsculas/minúsculas")
        r2.addWidget(self.chk_case)
        l_card.addLayout(r2)

        # Linha 3: Conteúdo de Texto
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Contém o texto interno:"))
        self.txt_content = QLineEdit()
        self.txt_content.setPlaceholderText("Texto a ser pesquisado dentro de arquivos (.txt, .py, .csv, .json, .log...)")
        r3.addWidget(self.txt_content, stretch=1)
        l_card.addLayout(r3)

        # Linha 4: Filtros de Tamanho e Data
        r4 = QHBoxLayout()
        r4.addWidget(QLabel("Tamanho:"))
        self.cmb_size = QComboBox()
        self.cmb_size.addItem("Qualquer tamanho", (None, None))
        self.cmb_size.addItem("Pequeno (< 1 MB)", (0, 1024 * 1024))
        self.cmb_size.addItem("Médio (1 MB a 50 MB)", (1024 * 1024, 50 * 1024 * 1024))
        self.cmb_size.addItem("Grande (> 50 MB)", (50 * 1024 * 1024, None))
        r4.addWidget(self.cmb_size)

        r4.addWidget(QLabel("Data de Modificação:"))
        self.cmb_date = QComboBox()
        self.cmb_date.addItem("Qualquer data", None)
        self.cmb_date.addItem("Últimas 24 horas", 86400)
        self.cmb_date.addItem("Últimos 7 dias", 7 * 86400)
        self.cmb_date.addItem("Últimos 30 dias", 30 * 86400)
        self.cmb_date.addItem("Último ano", 365 * 86400)
        r4.addWidget(self.cmb_date)
        r4.addStretch()

        # Botão de Ação
        self.btn_search = QPushButton("Pesquisar Arquivos")
        self.btn_search.setProperty("class", "primary")
        self.btn_search.clicked.connect(self._start_search)
        r4.addWidget(self.btn_search)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_search)
        r4.addWidget(self.btn_cancel)
        l_card.addLayout(r4)

        layout.addWidget(card)

        # Barra de Status
        self.lbl_status = QLabel("Defina os termos de busca e clique em 'Pesquisar Arquivos'.")
        self.lbl_status.setProperty("class", "secondary")
        layout.addWidget(self.lbl_status)

        # Tabela de Resultados
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Nome", "Localização / Pasta", "Tamanho", "Data Modificação", "Texto Encontrado"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.table)

        # Botões de Ação da Tabela
        r_acts = QHBoxLayout()
        btn_open = QPushButton("Abrir Arquivo Selecionado")
        btn_open.clicked.connect(self._open_selected_file)
        r_acts.addWidget(btn_open)

        btn_folder = QPushButton("Abrir Pasta no Explorer")
        btn_folder.clicked.connect(self._open_selected_folder)
        r_acts.addWidget(btn_folder)

        btn_copy = QPushButton("Copiar Caminho")
        btn_copy.clicked.connect(self._copy_selected_path)
        r_acts.addWidget(btn_copy)
        r_acts.addStretch()
        layout.addLayout(r_acts)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _browse_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Pesquisa", self.txt_folder.text())
        if f:
            self.txt_folder.setText(f)

    def _start_search(self):
        root_str = self.txt_folder.text().strip()
        root_dir = Path(root_str)
        if not root_dir.is_dir():
            QMessageBox.warning(self, "Aviso", "O diretório selecionado não existe ou é inválido.")
            return

        pattern = self.txt_pattern.text().strip() or "*"
        content_q = self.txt_content.text()
        case_sens = self.chk_case.isChecked()

        min_sz, max_sz = self.cmb_size.currentData()
        date_delta = self.cmb_date.currentData()
        min_mtime = (time.time() - date_delta) if date_delta else None

        self.btn_search.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.table.setRowCount(0)
        self.current_results.clear()
        self.lbl_status.setText("Pesquisando arquivos...")

        def worker(ctx):
            return search_files(
                root_dir=root_dir,
                name_pattern=pattern,
                min_size_bytes=min_sz,
                max_size_bytes=max_sz,
                min_mtime=min_mtime,
                content_query=content_q,
                case_sensitive=case_sens,
                is_cancelled_fn=ctx.is_cancelled,
                progress_cb=lambda count, msg: ctx.on_progress(count, 0, msg),
            )

        def on_prog(cur, tot, msg):
            self.lbl_status.setText(f"{msg} ({cur} encontrados)")

        def on_done(results: List[SearchResultItem]):
            self.btn_search.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.current_results = results
            self.table.setRowCount(len(results))

            for row, item in enumerate(results):
                self.table.setItem(row, 0, QTableWidgetItem(item.name))
                self.table.setItem(row, 1, QTableWidgetItem(str(item.path.parent)))
                self.table.setItem(row, 2, QTableWidgetItem(item.formatted_size))
                self.table.setItem(row, 3, QTableWidgetItem(item.formatted_mtime))
                self.table.setItem(row, 4, QTableWidgetItem(item.matched_snippet or "-"))

            count = len(results)
            self.lbl_status.setText(f"Pesquisa concluída! {count} arquivo(s) encontrado(s).")

        self.runner.start_task(worker, on_progress=on_prog, on_finished=on_done)

    def _cancel_search(self):
        self.runner.cancel_current()
        self.lbl_status.setText("Cancelando pesquisa...")

    def _get_selected_item(self) -> Optional[SearchResultItem]:
        row = self.table.currentRow()
        if 0 <= row < len(self.current_results):
            return self.current_results[row]
        return None

    def _open_selected_file(self):
        item = self._get_selected_item()
        if item and item.path.exists():
            os.startfile(str(item.path))

    def _open_selected_folder(self):
        item = self._get_selected_item()
        if item and item.path.exists():
            subprocess.run(["explorer", f"/select,{str(item.path)}"])

    def _copy_selected_path(self):
        item = self._get_selected_item()
        if item:
            QApplication.clipboard().setText(str(item.path))
            QMessageBox.information(self, "Copiado", "Caminho copiado para a área de transferência!")

    def _on_item_double_clicked(self, item):
        self._open_selected_file()

    def _show_context_menu(self, pos):
        item = self._get_selected_item()
        if not item:
            return
        menu = QMenu(self)
        a_open = menu.addAction("Abrir Arquivo")
        a_folder = menu.addAction("Mostrar na Pasta do Explorer")
        a_copy = menu.addAction("Copiar Caminho Completo")
        action = menu.exec(self.table.mapToGlobal(pos))
        if action == a_open:
            self._open_selected_file()
        elif action == a_folder:
            self._open_selected_folder()
        elif action == a_copy:
            self._copy_selected_path()
