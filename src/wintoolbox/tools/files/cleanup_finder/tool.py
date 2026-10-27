"""
Interface gráfica Fluent para o Higienizador de Arquivos e Pastas.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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
from wintoolbox.tools.files.cleanup_finder.logic import (
    execute_cleanup,
    scan_cleanup_candidates,
)


@register
class FilesCleanupFinderTool(Tool):
    id = "files.cleanup_finder"
    name = "Higienizador de Arquivos e Pastas"
    description = "Localizador e higienizador de pastas vazias, arquivos de 0 byte e atalhos quebrados com simulação (Dry Run)."
    category = "Arquivos e Pastas"
    icon = "Delete"
    tags = ["cleanup", "limpeza", "pastas vazias", "0 byte", "atalhos", "lixeira", "dry run"]

    def __init__(self) -> None:
        super().__init__()
        self._target_dir: Optional[str] = None
        self._found_items: List[Dict[str, Any]] = []

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Barra Superior de Controles
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        btn_select_dir = QPushButton("Selecionar Pasta para Analisar...")
        self.lbl_selected_dir = QLabel("Nenhuma pasta selecionada")
        self.lbl_selected_dir.setStyleSheet("color: #888888; font-style: italic;")

        top_bar.addWidget(btn_select_dir)
        top_bar.addWidget(self.lbl_selected_dir, 1)

        layout.addLayout(top_bar)

        # Barra de Opções de Varredura
        options_bar = QHBoxLayout()
        options_bar.setSpacing(12)

        self.chk_empty_dirs = QCheckBox("Pastas Vazias")
        self.chk_empty_dirs.setChecked(True)

        self.chk_zero_byte = QCheckBox("Arquivos de 0 Byte")
        self.chk_zero_byte.setChecked(True)

        self.chk_broken_lnks = QCheckBox("Atalhos Quebrados (.lnk)")
        self.chk_broken_lnks.setChecked(True)

        self.chk_use_trash = QCheckBox("Enviar para a Lixeira (Recomendado)")
        self.chk_use_trash.setChecked(True)

        options_bar.addWidget(self.chk_empty_dirs)
        options_bar.addWidget(self.chk_zero_byte)
        options_bar.addWidget(self.chk_broken_lnks)
        options_bar.addWidget(self.chk_use_trash)
        options_bar.addStretch()

        btn_scan = QPushButton("Simular Varredura (Dry Run)")
        btn_scan.setStyleSheet("font-weight: bold;")
        btn_cleanup = QPushButton("Higienizar Selecionados")
        btn_cleanup.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")

        options_bar.addWidget(btn_scan)
        options_bar.addWidget(btn_cleanup)

        layout.addLayout(options_bar)

        self.lbl_status = QLabel("Selecione um diretório para buscar itens desnecessários com modo de simulação.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Tabela de Itens Identificados
        self.table_items = QTableWidget()
        self.table_items.setColumnCount(4)
        self.table_items.setHorizontalHeaderLabels(["Tipo", "Nome do Item", "Detalhes / Diagnóstico", "Caminho no Disco"])
        self.table_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table_items.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table_items.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_items.setColumnWidth(1, 200)
        self.table_items.setColumnWidth(2, 280)
        self.table_items.setAlternatingRowColors(True)

        layout.addWidget(self.table_items, 1)

        # Conexões
        btn_select_dir.clicked.connect(self._on_select_dir)
        btn_scan.clicked.connect(self._on_scan)
        btn_cleanup.clicked.connect(self._on_cleanup)

        return container

    def _on_select_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(None, "Selecione a Pasta para Analisar")
        if folder:
            self._target_dir = folder
            self.lbl_selected_dir.setText(folder)
            self._on_scan()

    def _on_scan(self) -> None:
        if not self._target_dir:
            QMessageBox.information(None, "Atenção", "Selecione uma pasta primeiro.")
            return

        find_dirs = self.chk_empty_dirs.isChecked()
        find_zeros = self.chk_zero_byte.isChecked()
        find_lnks = self.chk_broken_lnks.isChecked()

        try:
            candidates = scan_cleanup_candidates(
                self._target_dir,
                find_empty_dirs=find_dirs,
                find_zero_byte_files=find_zeros,
                find_broken_shortcuts=find_lnks,
            )
            self._found_items = candidates
            self._render_table(candidates)
            self.lbl_status.setText(
                f"Simulação concluída: {len(candidates)} item(ns) passíveis de higienização encontrados."
            )
        except Exception as exc:
            QMessageBox.critical(None, "Erro na Varredura", f"Falha ao escanear pasta:\n{exc}")

    def _render_table(self, items: List[Dict[str, Any]]) -> None:
        self.table_items.clearContents()
        self.table_items.setRowCount(len(items))

        for idx, it in enumerate(items):
            item_type = QTableWidgetItem(it.get("type", ""))
            item_name = QTableWidgetItem(it.get("name", ""))
            item_det = QTableWidgetItem(it.get("detail", ""))
            item_path = QTableWidgetItem(it.get("path", ""))

            self.table_items.setItem(idx, 0, item_type)
            self.table_items.setItem(idx, 1, item_name)
            self.table_items.setItem(idx, 2, item_det)
            self.table_items.setItem(idx, 3, item_path)

    def _on_cleanup(self) -> None:
        if not self._found_items:
            QMessageBox.information(None, "Limpeza", "Nenhum item encontrado para higienizar.")
            return

        use_trash = self.chk_use_trash.isChecked()
        dest_str = "para a Lixeira" if use_trash else "DEFINITIVAMENTE (sem recuperação)"
        ans = QMessageBox.warning(
            None,
            "Confirmar Higienização",
            f"Deseja remover {len(self._found_items)} item(ns) encontrados {dest_str}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        res = execute_cleanup(self._found_items, use_trash=use_trash)
        self._found_items.clear()
        self.table_items.clearContents()
        self.table_items.setRowCount(0)

        msg = f"Higienização concluída:\n{res['success_count']} item(ns) removido(s) com sucesso."
        if res["failed_count"] > 0:
            msg += f"\n{res['failed_count']} falha(s) ao tentar remover."
        QMessageBox.information(None, "Resultado da Higienização", msg)
        self.lbl_status.setText(f"Higienização finalizada: {res['success_count']} removidos.")
