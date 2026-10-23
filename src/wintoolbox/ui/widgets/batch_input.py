"""
Widget de Entrada de Lote (Batch Input Widget).
Suporta Empty State com Dropzone visual tracejada, chips de extensões aceitas,
seleção de arquivos individuais, pastas com ToggleSwitch recursivo, remoção individual
de itens e Drag & Drop direto do Windows Explorer.
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget
)

from wintoolbox.core.batch import DiscoveredFile, SourceItem, discover_files
from wintoolbox.ui.icons import get_glyph, get_icon_font
from wintoolbox.ui.widgets.toggle_switch import ToggleSwitch


class _ClickableDropFrame(QFrame):
    """Área visual clicável para o estado vazio do lote."""
    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setProperty("class", "dropzone")
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


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

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Cabeçalho da seção com chips de extensões suportadas
        hdr_row = QHBoxLayout()
        lbl_header = QLabel("1. Arquivos e Pastas de Origem")
        lbl_header.setProperty("class", "section-title")
        hdr_row.addWidget(lbl_header)
        hdr_row.addStretch()

        if self.allowed_extensions:
            exts_sorted = sorted(self.allowed_extensions)[:7]
            for ext in exts_sorted:
                chip = QLabel(ext.upper())
                chip.setProperty("class", "ext-chip")
                hdr_row.addWidget(chip)
            if len(self.allowed_extensions) > 7:
                more = QLabel(f"+{len(self.allowed_extensions) - 7}")
                more.setProperty("class", "ext-chip")
                hdr_row.addWidget(more)

        layout.addLayout(hdr_row)

        # Stack que alterna entre Dropzone Vazia (0) e Tabela Populada (1)
        self.view_stack = QStackedWidget()
        self.view_stack.setFixedHeight(145)

        # Visão 0: Empty Dropzone Visual
        self.drop_frame = _ClickableDropFrame()
        df_layout = QVBoxLayout(self.drop_frame)
        df_layout.setContentsMargins(16, 14, 16, 14)
        df_layout.setSpacing(4)
        df_layout.setAlignment(Qt.AlignCenter)

        lbl_drop_title = QLabel("Arraste e solte arquivos ou pastas aqui")
        lbl_drop_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        lbl_drop_title.setAlignment(Qt.AlignCenter)
        df_layout.addWidget(lbl_drop_title)

        lbl_drop_sub = QLabel("Ou clique nesta área para procurar arquivos no computador")
        lbl_drop_sub.setProperty("class", "secondary")
        lbl_drop_sub.setAlignment(Qt.AlignCenter)
        df_layout.addWidget(lbl_drop_sub)

        self.drop_frame.clicked.connect(self._on_add_files)
        self.view_stack.addWidget(self.drop_frame)

        # Visão 1: Tabela de Origens com botão de remover individual
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Caminho de Origem", "Tipo", "Subpastas", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 64)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.view_stack.addWidget(self.table)

        layout.addWidget(self.view_stack)

        # Barra de ações e opções de entrada
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.btn_add_files = QPushButton("Adicionar Arquivos...")
        self.btn_add_files.clicked.connect(self._on_add_files)
        action_layout.addWidget(self.btn_add_files)

        self.btn_add_folder = QPushButton("Adicionar Pasta...")
        self.btn_add_folder.clicked.connect(self._on_add_folder)
        action_layout.addWidget(self.btn_add_folder)

        self.btn_clear = QPushButton("Limpar Lista")
        self.btn_clear.clicked.connect(self.clear)
        action_layout.addWidget(self.btn_clear)

        action_layout.addSpacing(16)

        # Interruptor de recursão estilo Windows 11
        self.chk_recursive = ToggleSwitch("Incluir subpastas (recursivo)")
        self.chk_recursive.setChecked(False)
        self.chk_recursive.toggled.connect(self._on_recursive_toggled)
        action_layout.addWidget(self.chk_recursive)

        action_layout.addStretch()
        layout.addLayout(action_layout)

        # Barra de status do lote
        self.lbl_summary = QLabel("Nenhum arquivo ou pasta adicionado. Arraste itens aqui.")
        self.lbl_summary.setProperty("class", "secondary")
        layout.addWidget(self.lbl_summary)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = []
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.exists():
                paths.append(p)
        if paths:
            self.add_paths(paths)

    def _on_add_files(self) -> None:
        filter_str = "Arquivos Suportados (*.*)"
        if self.allowed_extensions:
            ext_patterns = " ".join(f"*{e}" if e.startswith('.') else f"*.{e}" for e in self.allowed_extensions)
            filter_str = f"Suportados ({ext_patterns});;Todos (*.*)"
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar Arquivos", "", filter_str)
        if files:
            self.add_paths([Path(f) for f in files])

    def _on_add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
        if folder:
            self.add_paths([Path(folder)])

    def _on_recursive_toggled(self, checked: bool) -> None:
        for src in self.sources:
            if src.is_dir:
                src.recursive = checked
        self._refresh_table()
        self._update_discovered()

    def add_paths(self, paths: List[Path]) -> None:
        for p in paths:
            is_dir = p.is_dir()
            item = SourceItem(
                path=p,
                is_dir=is_dir,
                recursive=self.chk_recursive.isChecked() if is_dir else False
            )
            if not any(s.path == item.path for s in self.sources):
                self.sources.append(item)

        self._refresh_table()
        self._update_discovered()

    def remove_source_at(self, index: int) -> None:
        """Remove uma origem específica da tabela pelo índice."""
        if 0 <= index < len(self.sources):
            self.sources.pop(index)
            self._refresh_table()
            self._update_discovered()

    def clear(self) -> None:
        self.sources.clear()
        self._discovered_cache.clear()
        self._refresh_table()
        self._update_discovered()

    def _refresh_table(self) -> None:
        self.view_stack.setCurrentIndex(1 if self.sources else 0)
        self.table.setRowCount(len(self.sources))
        for row, src in enumerate(self.sources):
            item_path = QTableWidgetItem(str(src.path))
            item_path.setFlags(item_path.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, 0, item_path)

            tipo_str = "Pasta" if src.is_dir else "Arquivo"
            item_tipo = QTableWidgetItem(tipo_str)
            item_tipo.setFlags(item_tipo.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, 1, item_tipo)

            sub_str = "Sim" if src.is_dir and src.recursive else ("Não" if src.is_dir else "-")
            item_sub = QTableWidgetItem(sub_str)
            item_sub.setFlags(item_sub.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row, 2, item_sub)

            btn_del = QPushButton("Remover")
            btn_del.setProperty("class", "ghost")
            btn_del.setStyleSheet("font-size: 11px; padding: 2px 6px;")
            btn_del.setToolTip("Remover este item da lista")
            btn_del.clicked.connect(lambda _, r=row: self.remove_source_at(r))
            self.table.setCellWidget(row, 3, btn_del)

    def _update_discovered(self) -> None:
        self._discovered_cache = discover_files(self.sources, self.allowed_extensions)
        total = len(self._discovered_cache)
        if total == 0:
            self.lbl_summary.setText("Nenhum arquivo correspondente encontrado.")
        else:
            total_bytes = sum(f.size_bytes for f in self._discovered_cache)
            mb = total_bytes / (1024 * 1024)
            ext_counts = {}
            for f in self._discovered_cache:
                ext = f.extension or "sem_ext"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
            ext_summary = ", ".join(f"{ext}: {cnt}" for ext, cnt in sorted(ext_counts.items()))
            self.lbl_summary.setText(f"{total} arquivo(s) localizados (~{mb:.1f} MB) | Tipos: {ext_summary}")

        self.files_changed.emit(total)

    def get_discovered_files(self) -> List[DiscoveredFile]:
        return list(self._discovered_cache)
