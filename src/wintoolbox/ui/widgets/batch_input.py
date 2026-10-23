"""
Widget de Entrada de Lote (Batch Input Widget).
Suporta seleção de arquivos individuais, pastas com opção recursiva,
e Drag & Drop direto do Windows Explorer.
"""
from pathlib import Path
from typing import Callable, List, Optional, Set
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.batch import DiscoveredFile, SourceItem, discover_files

class BatchInputWidget(QFrame):
    """Componente de entrada para ferramentas baseadas em arquivos."""
    files_changed = Signal(int)  # Emite contagem de itens

    def __init__(self, allowed_extensions: Optional[List[str]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setAcceptDrops(True)
        self.allowed_extensions = set(allowed_extensions) if allowed_extensions else None
        self.sources: List[SourceItem] = []
        self._discovered_cache: List[DiscoveredFile] = []

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Cabeçalho da seção
        lbl_header = QLabel("Arquivos e Pastas de Origem")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        # Tabela de origens
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Caminho de Origem", "Tipo", "Subpastas"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setFixedHeight(140)
        layout.addWidget(self.table)

        # Barra de ações e opções de entrada
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.btn_add_files = QPushButton("Adicionar Arquivos...")
        self.btn_add_files.clicked.connect(self._on_add_files)
        action_layout.addWidget(self.btn_add_files)

        self.btn_add_folder = QPushButton("Adicionar Pasta...")
        self.btn_add_folder.clicked.connect(self._on_add_folder)
        action_layout.addWidget(self.btn_add_folder)

        self.btn_clear = QPushButton("Limpar")
        self.btn_clear.clicked.connect(self.clear)
        action_layout.addWidget(self.btn_clear)

        action_layout.addSpacing(15)

        # Checkbox de recursão (desmarcado por padrão conforme instrução do usuário)
        self.chk_recursive = QCheckBox("Incluir subpastas (recursivo)")
        self.chk_recursive.setChecked(False)
        self.chk_recursive.toggled.connect(self._on_recursive_toggled)
        action_layout.addWidget(self.chk_recursive)

        action_layout.addStretch()
        layout.addLayout(action_layout)

        # Barra de status do lote (resumo de arquivos detectados)
        self.lbl_summary = QLabel("Nenhum arquivo ou pasta adicionado. Arraste itens aqui.")
        self.lbl_summary.setProperty("class", "secondary")
        layout.addWidget(self.lbl_summary)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.exists():
                paths.append(p)
        if paths:
            self.add_paths(paths)

    def _on_add_files(self):
        filter_str = "Arquivos Suportados (*.*)"
        if self.allowed_extensions:
            ext_patterns = " ".join(f"*{e}" if e.startswith('.') else f"*.{e}" for e in self.allowed_extensions)
            filter_str = f"Suportados ({ext_patterns});;Todos (*.*)"
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar Arquivos", "", filter_str)
        if files:
            self.add_paths([Path(f) for f in files])

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
        if folder:
            self.add_paths([Path(folder)])

    def _on_recursive_toggled(self, checked: bool):
        # Atualiza a flag em todas as pastas adicionadas
        for src in self.sources:
            if src.is_dir:
                src.recursive = checked
        self._refresh_table()
        self._update_discovered()

    def add_paths(self, paths: List[Path]):
        for p in paths:
            is_dir = p.is_dir()
            item = SourceItem(
                path=p,
                is_dir=is_dir,
                recursive=self.chk_recursive.isChecked() if is_dir else False
            )
            # Evita duplicatas diretas
            if not any(s.path == item.path for s in self.sources):
                self.sources.append(item)

        self._refresh_table()
        self._update_discovered()

    def clear(self):
        self.sources.clear()
        self._discovered_cache.clear()
        self._refresh_table()
        self._update_discovered()

    def _refresh_table(self):
        self.table.setRowCount(len(self.sources))
        for row, src in enumerate(self.sources):
            # Caminho
            item_path = QTableWidgetItem(str(src.path))
            item_path.setFlags(item_path.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, 0, item_path)

            # Tipo
            tipo_str = "Pasta" if src.is_dir else "Arquivo"
            item_tipo = QTableWidgetItem(tipo_str)
            item_tipo.setFlags(item_tipo.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, 1, item_tipo)

            # Subpastas
            sub_str = "Sim" if src.is_dir and src.recursive else ("Não" if src.is_dir else "-")
            item_sub = QTableWidgetItem(sub_str)
            item_sub.setFlags(item_sub.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, 2, item_sub)

    def _update_discovered(self):
        self._discovered_cache = discover_files(self.sources, self.allowed_extensions)
        total = len(self._discovered_cache)
        if total == 0:
            self.lbl_summary.setText("Nenhum arquivo correspondente encontrado.")
        else:
            total_bytes = sum(f.size_bytes for f in self._discovered_cache)
            mb = total_bytes / (1024 * 1024)
            # Extensões encontradas
            ext_counts = {}
            for f in self._discovered_cache:
                ext = f.extension or "sem_ext"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
            ext_summary = ", ".join(f"{ext}: {cnt}" for ext, cnt in sorted(ext_counts.items()))

            self.lbl_summary.setText(f"{total} arquivo(s) localizados (~{mb:.1f} MB) | Tipos: {ext_summary}")

        self.files_changed.emit(total)

    def get_discovered_files(self) -> List[DiscoveredFile]:
        return list(self._discovered_cache)
