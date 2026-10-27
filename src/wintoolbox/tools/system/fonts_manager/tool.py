"""
Ferramenta: Gerenciador e Instalador de Fontes (Fonts Manager).
Permite visualizar amostras tipográficas e instalar fontes TTF/OTF sem privilégios de administrador.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSlider,
    QSplitter, QTextEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.tools.system.fonts_manager.logic import (
    FontInfo,
    extract_font_metadata,
    install_font_for_current_user,
    list_installed_fonts_summary,
)


@register
class FontsManagerTool(Tool):
    id = "system.fonts_manager"
    name = "Gerenciador de Fontes"
    category = "Sistema"
    description = "Instale fontes TTF/OTF no perfil do usuário sem admin e visualize amostras tipográficas"
    keywords = ["fontes", "fonts", "tipografia", "ttf", "otf", "instalar fonte", "amostra", "type"]

    def __init__(self) -> None:
        super().__init__()
        self._all_fonts: List[FontInfo] = []
        self._selected_font_family: str = "Segoe UI"

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Barra Superior de Ações
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.btn_install = QPushButton("Instalar Nova Fonte (TTF / OTF)...")
        self.btn_install.setStyleSheet("font-weight: 600;")
        self.btn_install.clicked.connect(self._install_font_dialog)
        top_bar.addWidget(self.btn_install)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar fonte por nome da família...")
        self.txt_search.textChanged.connect(self._apply_filter)
        top_bar.addWidget(self.txt_search, stretch=1)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self._load_fonts)
        top_bar.addWidget(self.btn_refresh)

        main_layout.addLayout(top_bar)

        # Splitter Vertical
        splitter = QSplitter(Qt.Vertical)

        # Tabela de Fontes
        columns = [
            Column("family", "Família da Fonte", width=220),
            Column("subfamily", "Estilo", width=120),
            Column("format_type", "Formato", width=110),
            Column("scope_display", "Instalação", width=120),
            Column("file_name", "Arquivo", stretch=True),
        ]
        self.table = DataTableView(columns, key="file_name", parent=container)
        self.table.clicked.connect(self._on_font_selected)
        splitter.addWidget(self.table)

        # Painel Inferior de Prévia Tipográfica
        preview_card = QFrame()
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(0, 10, 0, 0)
        preview_layout.setSpacing(8)

        ctrl_row = QHBoxLayout()
        self.lbl_preview_title = QLabel("Prévia: Segoe UI")
        self.lbl_preview_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        ctrl_row.addWidget(self.lbl_preview_title)
        ctrl_row.addStretch()

        self.lbl_size = QLabel("Tamanho (24 pt):")
        ctrl_row.addWidget(self.lbl_size)

        self.slider_size = QSlider(Qt.Horizontal)
        self.slider_size.setRange(10, 72)
        self.slider_size.setValue(24)
        self.slider_size.setFixedWidth(160)
        self.slider_size.valueChanged.connect(self._on_size_changed)
        ctrl_row.addWidget(self.slider_size)
        preview_layout.addLayout(ctrl_row)

        self.txt_sample = QTextEdit()
        self.txt_sample.setText(
            "A rápida raposa marrom salta sobre o cão preguiçoso.\n"
            "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG.\n"
            "0123456789 - @#$%&*() [] {}"
        )
        self.txt_sample.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;")
        self._update_sample_font()
        preview_layout.addWidget(self.txt_sample)

        splitter.addWidget(preview_card)
        splitter.setSizes([340, 200])
        main_layout.addWidget(splitter)

        # Status
        self.lbl_status = QLabel("Carregando fontes do sistema...")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
        main_layout.addWidget(self.lbl_status)

        self._load_fonts()
        return container

    def _load_fonts(self) -> None:
        self.btn_refresh.setEnabled(False)
        self.lbl_status.setText("Indexando fontes do sistema e do usuário...")

        TaskRunner.run(
            list_installed_fonts_summary,
            on_success=self._on_fonts_loaded,
            on_error=self._on_fonts_error
        )

    def _on_fonts_loaded(self, fonts: List[FontInfo]) -> None:
        self._all_fonts = fonts
        self.btn_refresh.setEnabled(True)
        self.lbl_status.setText(f"{len(fonts)} fontes tipográficas catalogadas.")
        self._apply_filter()

    def _on_fonts_error(self, err: Exception) -> None:
        self.btn_refresh.setEnabled(True)
        self.lbl_status.setText(f"Erro ao catalogar fontes: {err}")

    def _apply_filter(self) -> None:
        q = self.txt_search.text().strip().lower()
        records: List[Dict[str, Any]] = []

        for f in self._all_fonts:
            if q and q not in f.family.lower() and q not in f.file_name.lower():
                continue

            records.append({
                "family": f.family,
                "subfamily": f.subfamily,
                "format_type": f.format_type,
                "scope_display": "Usuário (AppData)" if f.is_user_font else "Sistema (Windows)",
                "file_name": f.file_name,
                "file_path": f.file_path,
            })

        self.table.set_records(records)

    def _on_font_selected(self) -> None:
        rec = self.table.current_record()
        if rec:
            fam = rec.get("family") or "Segoe UI"
            self._selected_font_family = fam
            self.lbl_preview_title.setText(f"Prévia: {fam} ({rec.get('file_name')})")
            self._update_sample_font()

    def _on_size_changed(self, size: int) -> None:
        self.lbl_size.setText(f"Tamanho ({size} pt):")
        self._update_sample_font()

    def _update_sample_font(self) -> None:
        size = self.slider_size.value()
        font = QFont(self._selected_font_family, size)
        self.txt_sample.setFont(font)

    def _install_font_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Arquivo de Fonte para Instalar",
            "",
            "Fontes Tipográficas (*.ttf *.otf)"
        )
        if not file_path:
            return

        p = Path(file_path)
        ok, msg = install_font_for_current_user(p)
        if ok:
            QMessageBox.information(None, "Fonte Instalada", msg)
            self._load_fonts()
        else:
            QMessageBox.warning(None, "Erro na Instalação", msg)
