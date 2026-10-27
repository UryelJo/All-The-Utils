"""
Interface gráfica Fluent para o Gerenciador de Links NTFS.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.files.links_manager.logic import (
    remove_link_safely,
    scan_ntfs_links,
)


@register
class FilesLinksManagerTool(Tool):
    id = "files.links_manager"
    name = "Gerenciador de Links NTFS"
    description = "Auditor de ponteiros de sistema de arquivos NTFS: links simbólicos, junctions e hardlinks."
    category = "Arquivos e Pastas"
    icon = "Link"
    tags = ["link", "symlink", "junction", "hardlink", "ntfs", "quebrado", "ponteiro"]

    def __init__(self) -> None:
        super().__init__()
        self._current_links: List[Dict[str, Any]] = []
        self._scanned_dir: Optional[str] = None

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Barra Superior
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        btn_scan = QPushButton("Escanear Pasta / Disco...")
        btn_scan.setStyleSheet("font-weight: bold;")
        btn_delete = QPushButton("Remover Link com Segurança")
        btn_delete.setStyleSheet("color: #d32f2f;")

        top_bar.addWidget(btn_scan)
        top_bar.addWidget(btn_delete)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        self.lbl_status = QLabel("Selecione um diretório para auditar todos os links e junções existentes.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Tabela de Links
        self.table_links = QTableWidget()
        self.table_links.setColumnCount(5)
        self.table_links.setHorizontalHeaderLabels(["Tipo", "Nome", "Status", "Alvo Apontado", "Caminho do Link"])
        self.table_links.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_links.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table_links.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_links.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table_links.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table_links.setColumnWidth(1, 180)
        self.table_links.setColumnWidth(3, 260)
        self.table_links.setAlternatingRowColors(True)

        layout.addWidget(self.table_links, 1)

        # Conexões
        btn_scan.clicked.connect(self._on_scan)
        btn_delete.clicked.connect(self._on_delete_selected)

        return container

    def _on_scan(self) -> None:
        folder = QFileDialog.getExistingDirectory(None, "Selecione o Disco ou Pasta para Varrer")
        if not folder:
            return

        self._scanned_dir = folder
        try:
            links = scan_ntfs_links(folder)
            self._current_links = links
            self._render_table(links)

            broken_count = sum(1 for l in links if l.get("is_broken"))
            status_text = f"Varredura concluída: {len(links)} link(s) encontrados em '{folder}'."
            if broken_count > 0:
                status_text += f" ⚠️ {broken_count} link(s) com alvo QUEBRADO!"
            self.lbl_status.setText(status_text)
        except Exception as exc:
            QMessageBox.critical(None, "Erro ao Varrer", f"Falha na varredura:\n{exc}")

    def _render_table(self, links: List[Dict[str, Any]]) -> None:
        self.table_links.clearContents()
        self.table_links.setRowCount(len(links))

        for idx, item in enumerate(links):
            item_type = QTableWidgetItem(item.get("type", ""))
            item_name = QTableWidgetItem(item.get("name", ""))
            item_status = QTableWidgetItem(item.get("status", ""))
            item_target = QTableWidgetItem(item.get("target", ""))
            item_path = QTableWidgetItem(item.get("path", ""))

            if item.get("is_broken"):
                item_status.setForeground(QColor("#d32f2f"))
            else:
                item_status.setForeground(QColor("#2e7d32"))

            self.table_links.setItem(idx, 0, item_type)
            self.table_links.setItem(idx, 1, item_name)
            self.table_links.setItem(idx, 2, item_status)
            self.table_links.setItem(idx, 3, item_target)
            self.table_links.setItem(idx, 4, item_path)

    def _on_delete_selected(self) -> None:
        row = self.table_links.currentRow()
        if row < 0 or row >= len(self._current_links):
            QMessageBox.information(None, "Seleção", "Selecione um link na tabela para remover.")
            return

        link_info = self._current_links[row]
        link_path = link_info.get("path", "")

        ans = QMessageBox.question(
            None,
            "Confirmar Remoção Segura",
            f"Deseja remover o link '{link_info.get('name')}'?\n\n"
            f"O ponteiro será excluído, mas o diretório/arquivo alvo NÃO será afetado:\n{link_info.get('target')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        ok = remove_link_safely(link_path)
        if ok:
            QMessageBox.information(None, "Sucesso", "Link removido com segurança.")
            if self._scanned_dir:
                self._on_scan()
        else:
            QMessageBox.warning(None, "Falha", "Não foi possível remover o link selecionado.")
