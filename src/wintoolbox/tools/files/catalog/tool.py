"""
Interface gráfica Fluent para o Catalogador de Mídias Externas.
Permite criar snapshots e realizar buscas offline ultra rápidas em mídias desconectadas.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.files.catalog.logic import (
    load_catalog_from_file,
    save_catalog_to_file,
    scan_directory_catalog,
    search_catalog_entries,
)


@register
class FilesCatalogTool(Tool):
    id = "files.catalog"
    name = "Catalogador de Mídias Externas"
    description = "Indexador de HDs externos e pendrives: salva snapshots da estrutura de pastas para busca offline."
    category = "Arquivos e Pastas"
    icon = "HardDrive"
    tags = ["catalog", "disco", "hd", "pendrive", "nas", "snapshot", "busca", "offline"]

    def __init__(self) -> None:
        super().__init__()
        self._current_catalog: Optional[Dict[str, Any]] = None

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Barra Superior de Ações
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        btn_scan = QPushButton("Escanear Nova Pasta / Drive...")
        btn_scan.setStyleSheet("font-weight: bold;")
        btn_save = QPushButton("Salvar Catálogo...")
        btn_open = QPushButton("Abrir Catálogo Salvo...")

        top_bar.addWidget(btn_scan)
        top_bar.addWidget(btn_save)
        top_bar.addWidget(btn_open)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        # Barra de Pesquisa Offline
        search_bar = QHBoxLayout()
        search_bar.setSpacing(8)

        search_bar.addWidget(QLabel("Pesquisar:"))
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Digite nome ou parte do caminho do arquivo...")
        search_bar.addWidget(self.edit_search, 1)

        search_bar.addWidget(QLabel("Extensão:"))
        self.edit_ext = QLineEdit()
        self.edit_ext.setPlaceholderText(".mkv, .pdf, etc")
        self.edit_ext.setMaximumWidth(100)
        search_bar.addWidget(self.edit_ext)

        btn_search = QPushButton("Buscar")
        btn_clear = QPushButton("Limpar")
        search_bar.addWidget(btn_search)
        search_bar.addWidget(btn_clear)

        layout.addLayout(search_bar)

        self.lbl_status = QLabel("Nenhum catálogo carregado. Escaneie um disco ou abra um arquivo de catálogo.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Tabela de Arquivos do Catálogo
        self.table_results = QTableWidget()
        self.table_results.setColumnCount(4)
        self.table_results.setHorizontalHeaderLabels(["Nome do Arquivo", "Tamanho", "Modificação", "Caminho no Catálogo"])
        self.table_results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_results.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_results.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_results.setColumnWidth(0, 260)
        self.table_results.setAlternatingRowColors(True)

        layout.addWidget(self.table_results, 1)

        # Conexões
        btn_scan.clicked.connect(self._on_scan_directory)
        btn_save.clicked.connect(self._on_save_catalog)
        btn_open.clicked.connect(self._on_open_catalog)
        btn_search.clicked.connect(self._on_search)
        btn_clear.clicked.connect(self._on_clear_search)
        self.edit_search.textChanged.connect(self._on_search)
        self.edit_ext.textChanged.connect(self._on_search)

        return container

    def _on_scan_directory(self) -> None:
        folder = QFileDialog.getExistingDirectory(None, "Selecione a Pasta ou Drive para Catalogar")
        if not folder:
            return

        try:
            cat_data = scan_directory_catalog(folder)
            self._current_catalog = cat_data
            self._render_results(cat_data["entries"])
            self.lbl_status.setText(
                f"✅ Catálogo '{cat_data['catalog_name']}' gerado: {cat_data['total_files']} arquivos, "
                f"{cat_data['total_dirs']} pastas ({cat_data['total_bytes_formatted']})."
            )
        except Exception as exc:
            QMessageBox.critical(None, "Erro ao Escanear", f"Falha ao escanear diretório:\n{exc}")

    def _on_save_catalog(self) -> None:
        if not self._current_catalog:
            QMessageBox.information(None, "Salvar Catálogo", "Nenhum catálogo ativo para salvar.")
            return

        default_name = f"{self._current_catalog['catalog_name']}_catalogo.json"
        path, _ = QFileDialog.getSaveFileName(None, "Salvar Catálogo", default_name, "Arquivo de Catálogo (*.json)")
        if not path:
            return

        try:
            save_catalog_to_file(self._current_catalog, path)
            QMessageBox.information(None, "Catálogo Salvo", f"Catálogo salvo com sucesso em:\n{path}")
        except Exception as exc:
            QMessageBox.critical(None, "Erro ao Salvar", str(exc))

    def _on_open_catalog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Abrir Arquivo de Catálogo", "", "Arquivo de Catálogo (*.json)")
        if not path:
            return

        try:
            cat_data = load_catalog_from_file(path)
            self._current_catalog = cat_data
            self._render_results(cat_data["entries"])
            self.lbl_status.setText(
                f"📁 Catálogo '{cat_data['catalog_name']}' carregado: {cat_data['total_files']} arquivos, "
                f"({cat_data.get('total_bytes_formatted', '')}). Criado em {cat_data.get('created_at', '')[:10]}."
            )
        except Exception as exc:
            QMessageBox.critical(None, "Erro ao Abrir Catálogo", f"Arquivo inválido:\n{exc}")

    def _on_search(self) -> None:
        if not self._current_catalog:
            return

        query = self.edit_search.text().strip()
        ext = self.edit_ext.text().strip()

        filtered = search_catalog_entries(self._current_catalog, query=query, extension=ext)
        self._render_results(filtered)

    def _on_clear_search(self) -> None:
        self.edit_search.clear()
        self.edit_ext.clear()
        if self._current_catalog:
            self._render_results(self._current_catalog["entries"])

    def _render_results(self, items: List[Dict[str, Any]]) -> None:
        self.table_results.clearContents()
        self.table_results.setRowCount(len(items))

        for idx, item in enumerate(items):
            name_item = QTableWidgetItem(item.get("name", ""))
            size_item = QTableWidgetItem(item.get("size_formatted", str(item.get("size", 0))))
            mtime_item = QTableWidgetItem(item.get("mtime_formatted", ""))
            path_item = QTableWidgetItem(item.get("path", ""))

            self.table_results.setItem(idx, 0, name_item)
            self.table_results.setItem(idx, 1, size_item)
            self.table_results.setItem(idx, 2, mtime_item)
            self.table_results.setItem(idx, 3, path_item)
