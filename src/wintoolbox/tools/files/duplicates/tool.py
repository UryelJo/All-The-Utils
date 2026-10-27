"""
Ferramenta: Localizador e Removedor de Arquivos Duplicados.
Utiliza varredura em 3 estágios (tamanho, hash parcial e hash SHA-256 completo) e exclusão segura para a Lixeira.
"""
import hashlib
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from .logic import (
    DuplicateItem,
    format_size,
    get_file_full_hash,
    get_file_quick_hash,
    scan_duplicates,
    trash_files,
)

@register
class DuplicatesTool(Tool):
    id = "files.duplicates"
    name = "Localizador de Arquivos Duplicados"
    category = "Arquivos e Pastas"
    description = "Localizador de arquivos duplicados idênticos por tamanho exato e hash criptográfico SHA-256, com pré-visualização e envio seguro para a Lixeira do Windows."
    keywords = ["duplicados", "clones", "espaco", "limpar", "lixeira", "hash", "arquivos", "pastas"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return DuplicatesView(self, parent)

class DuplicatesView(QWidget):
    def __init__(self, tool: DuplicatesTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self.runner = TaskRunner()
        self.duplicate_items: List[DuplicateItem] = []
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

        # Seleção de Pasta
        card_dir = QFrame()
        card_dir.setProperty("class", "card")
        l_dir = QVBoxLayout(card_dir)
        l_dir.setSpacing(10)

        row_sel = QHBoxLayout()
        row_sel.addWidget(QLabel("Pasta a Verificar:"))
        self.txt_path = QLineEdit(str(Path.home() / "Downloads"))
        row_sel.addWidget(self.txt_path, stretch=1)

        btn_browse = QPushButton("Selecionar Pasta...")
        btn_browse.clicked.connect(self._select_dir)
        row_sel.addWidget(btn_browse)

        self.btn_scan = QPushButton("Buscar Duplicados")
        self.btn_scan.setProperty("class", "primary")
        self.btn_scan.clicked.connect(self._start_scan)
        row_sel.addWidget(self.btn_scan)
        l_dir.addLayout(row_sel)

        row_opts = QHBoxLayout()
        self.chk_recursive = QCheckBox("Incluir subpastas (recursivo)")
        self.chk_recursive.setChecked(True)
        row_opts.addWidget(self.chk_recursive)
        row_opts.addStretch()
        l_dir.addLayout(row_opts)

        layout.addWidget(card_dir)

        # Barra de Ações Rápidas de Seleção
        bar_select = QHBoxLayout()
        btn_sel_old = QPushButton("Marcar Todos Exceto o Mais Recente")
        btn_sel_old.clicked.connect(self._select_all_except_newest)
        bar_select.addWidget(btn_sel_old)

        btn_sel_new = QPushButton("Marcar Todos Exceto o Mais Antigo")
        btn_sel_new.clicked.connect(self._select_all_except_oldest)
        bar_select.addWidget(btn_sel_new)

        btn_unselect = QPushButton("Desmarcar Todos")
        btn_unselect.clicked.connect(self._unselect_all)
        bar_select.addWidget(btn_unselect)

        bar_select.addStretch()
        self.lbl_stats = QLabel("Nenhuma varredura realizada.")
        self.lbl_stats.setProperty("class", "secondary")
        bar_select.addWidget(self.lbl_stats)
        layout.addLayout(bar_select)

        # Tabela de Duplicados
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Excluir?", "Grupo", "Nome do Arquivo", "Tamanho", "Caminho Completo"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setFixedHeight(280)
        self.table.itemChanged.connect(self._on_table_item_changed)
        layout.addWidget(self.table)

        # Barra de Progresso e Ação de Exclusão
        bar_del = QHBoxLayout()
        self.btn_delete = QPushButton("Enviar Selecionados para a Lixeira")
        self.btn_delete.setProperty("class", "danger")
        self.btn_delete.setFixedHeight(36)
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_selected)
        bar_del.addWidget(self.btn_delete)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        bar_del.addWidget(self.progress_bar, stretch=1)
        layout.addLayout(bar_del)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _select_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta", self.txt_path.text())
        if folder:
            self.txt_path.setText(folder)

    def _start_scan(self):
        folder = self.txt_path.text().strip()
        if not folder or not Path(folder).exists():
            QMessageBox.warning(self, "Aviso", "Selecione uma pasta válida existente.")
            return

        self.btn_scan.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.progress_bar.setValue(5)
        self.lbl_stats.setText("Descobrindo arquivos...")
        recursive = self.chk_recursive.isChecked()

        def worker(ctx):
            def on_progress(p, msg):
                ctx.send_progress(p, msg)

            duplicate_groups = scan_duplicates(Path(folder), recursive=recursive, progress_cb=on_progress)
            result_items: List[DuplicateItem] = []
            for gid, flist in enumerate(duplicate_groups, start=1):
                sz = flist[0].stat().st_size if flist and flist[0].exists() else 0
                for f in flist:
                    mtime = f.stat().st_mtime if f.exists() else 0.0
                    result_items.append(DuplicateItem(path=f, group_id=gid, size=sz, mtime=mtime))

            return result_items

        def on_task_progress(percent, _total, msg):
            self.progress_bar.setValue(percent)
            self.lbl_stats.setText(msg)

        def on_done(items: List[DuplicateItem]):
            self.btn_scan.setEnabled(True)
            self.progress_bar.setValue(100)
            self.duplicate_items = items
            self._populate_table()

            groups_count = len(set(it.group_id for it in items))
            total_waste = sum(it.size for it in items) - sum(dict([(it.group_id, it.size) for it in items]).values())
            mb_waste = round(total_waste / (1024 * 1024), 2)
            self.lbl_stats.setText(f"{len(items)} arquivos duplicados em {groups_count} grupos ({mb_waste} MB desperdiçados)")

        def on_error(err):
            self.btn_scan.setEnabled(True)
            QMessageBox.critical(self, "Erro", f"Falha na varredura:\n{err}")

        self.runner.start_task(worker, on_progress=on_task_progress, on_finished=on_done, on_error=on_error)

    def _populate_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.duplicate_items))

        for row, it in enumerate(self.duplicate_items):
            # Checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Checked if it.selected else Qt.Unchecked)
            self.table.setItem(row, 0, chk_item)

            self.table.setItem(row, 1, QTableWidgetItem(f"Grupo {it.group_id}"))
            self.table.setItem(row, 2, QTableWidgetItem(it.path.name))
            self.table.setItem(row, 3, QTableWidgetItem(self._format_size(it.size)))
            self.table.setItem(row, 4, QTableWidgetItem(str(it.path)))

        self.table.blockSignals(False)
        self._update_delete_button()

    def _format_size(self, size_bytes: int) -> str:
        return format_size(size_bytes)

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if item.column() == 0:
            row = item.row()
            if 0 <= row < len(self.duplicate_items):
                self.duplicate_items[row].selected = (item.checkState() == Qt.Checked)
                self._update_delete_button()

    def _update_delete_button(self):
        selected_count = sum(1 for it in self.duplicate_items if it.selected)
        self.btn_delete.setEnabled(selected_count > 0)
        self.btn_delete.setText(f"Enviar {selected_count} Selecionado(s) para a Lixeira")

    def _select_all_except_newest(self):
        groups = defaultdict(list)
        for it in self.duplicate_items:
            groups[it.group_id].append(it)

        for gid, flist in groups.items():
            # Ordena decrescente por mtime (o mais novo é o primeiro)
            flist.sort(key=lambda x: x.mtime, reverse=True)
            for i, it in enumerate(flist):
                it.selected = (i > 0)  # Marca todos exceto o primeiro

        self._populate_table()

    def _select_all_except_oldest(self):
        groups = defaultdict(list)
        for it in self.duplicate_items:
            groups[it.group_id].append(it)

        for gid, flist in groups.items():
            # Ordena crescente por mtime (o mais antigo é o primeiro)
            flist.sort(key=lambda x: x.mtime)
            for i, it in enumerate(flist):
                it.selected = (i > 0)  # Marca todos exceto o primeiro

        self._populate_table()

    def _unselect_all(self):
        for it in self.duplicate_items:
            it.selected = False
        self._populate_table()

    def _delete_selected(self):
        to_delete = [it for it in self.duplicate_items if it.selected]
        if not to_delete:
            return

        reply = QMessageBox.question(
            self,
            "Confirmar Envio para a Lixeira",
            f"Deseja realmente mover {len(to_delete)} arquivo(s) duplicados para a Lixeira do Windows?\n"
            "Eles poderão ser restaurados caso necessário.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            paths = [it.path for it in to_delete]
            deleted = trash_files(paths)

            QMessageBox.information(
                self,
                "Lixeira",
                f"{deleted} arquivo(s) foram movidos com segurança para a Lixeira!"
            )
            # Remove da lista e atualiza
            self.duplicate_items = [it for it in self.duplicate_items if not it.selected]
            self._populate_table()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao mover para a lixeira:\n{str(e)}")
