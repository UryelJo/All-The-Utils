"""
Interface gráfica da ferramenta Criador Avançado de Arquivos Compactados (archive.creator_advanced).
Permite criar arquivos ZIP com controle minucioso de algoritmos (DEFLATE, BZIP2, LZMA, STORE),
nível de compressão (1 a 9), divisão de volumes multipartes e proteção por senha.
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.archive.creator_advanced.logic import (
    create_advanced_archive,
)
from wintoolbox.ui.widgets.data_table import Column, DataTableView


@register
class CreatorAdvancedTool(Tool):
    id = "archive.creator_advanced"
    name = "Criador Avançado de Compactados"
    category = "Compactação"
    description = (
        "Cria arquivos compactados com algoritmos modernos (LZMA, BZIP2, DEFLATE), "
        "divisão em volumes multipartes (.001, .002) e cálculo de taxa de economia de espaço."
    )
    keywords = ["zip", "lzma", "bzip2", "compressao", "compactar", "volumes", "multi-part", "arquivo"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return CreatorAdvancedView(self, parent)


class CreatorAdvancedView(QWidget):
    def __init__(self, tool: CreatorAdvancedTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._runner = TaskRunner()
        self._selected_items: List[Path] = []
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937;")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        root_layout.addWidget(lbl_desc)

        # Painel de Parâmetros de Compressão
        config_group = QGroupBox("Configurações de Compressão")
        config_layout = QVBoxLayout(config_group)

        # Linha 1: Algoritmo e Nível
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Algoritmo:"))
        self._combo_alg = QComboBox()
        self._combo_alg.addItem("LZMA (Máxima Compressão - Tipo 7z)", "lzma")
        self._combo_alg.addItem("DEFLATE (Padrão Universal ZIP)", "deflate")
        self._combo_alg.addItem("BZIP2 (Alta Compressão para Textos)", "bzip2")
        self._combo_alg.addItem("STORE (Sem Compressão - Apenas empacota)", "store")
        row1.addWidget(self._combo_alg)

        row1.addWidget(QLabel("Nível (1 a 9):"))
        self._spin_level = QSpinBox()
        self._spin_level.setRange(1, 9)
        self._spin_level.setValue(6)
        row1.addWidget(self._spin_level)

        row1.addStretch()
        config_layout.addLayout(row1)

        # Linha 2: Divisão em Volumes (Multi-volume)
        row2 = QHBoxLayout()
        self._chk_split = QCheckBox("Dividir em volumes multipartes:")
        row2.addWidget(self._chk_split)

        self._combo_split_size = QComboBox()
        self._combo_split_size.addItem("10 MB (Pequeno)", 10 * 1024 * 1024)
        self._combo_split_size.addItem("50 MB (E-mail / Discord)", 50 * 1024 * 1024)
        self._combo_split_size.addItem("100 MB", 100 * 1024 * 1024)
        self._combo_split_size.addItem("700 MB (CD-ROM)", 700 * 1024 * 1024)
        self._combo_split_size.addItem("2 GB", 2 * 1024 * 1024 * 1024)
        row2.addWidget(self._combo_split_size)

        row2.addWidget(QLabel("Senha opcional:"))
        self._txt_password = QLineEdit()
        self._txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._txt_password.setPlaceholderText("Deixe em branco para sem senha")
        row2.addWidget(self._txt_password)

        row2.addStretch()
        config_layout.addLayout(row2)

        root_layout.addWidget(config_group)

        # Barra de Adição de Itens
        item_bar = QHBoxLayout()
        btn_add_files = QPushButton("Adicionar Arquivos...")
        btn_add_files.clicked.connect(self._on_add_files)
        item_bar.addWidget(btn_add_files)

        btn_add_folder = QPushButton("Adicionar Pasta Inteira...")
        btn_add_folder.clicked.connect(self._on_add_folder)
        item_bar.addWidget(btn_add_folder)

        btn_clear = QPushButton("Limpar Lista")
        btn_clear.clicked.connect(self._on_clear_items)
        item_bar.addWidget(btn_clear)

        item_bar.addStretch()

        self._btn_create = QPushButton("Criar Arquivo Compactado...")
        self._btn_create.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self._btn_create.clicked.connect(self._on_start_creation)
        item_bar.addWidget(self._btn_create)

        root_layout.addLayout(item_bar)

        # Tabela com os Itens Adicionados
        cols = [
            Column("type", "Tipo", width=80),
            Column("name", "Nome", width=220),
            Column("size", "Tamanho", width=120, align="right"),
            Column("path", "Caminho Completo", width=380),
        ]
        self._table = DataTableView(cols, key="path", parent=self)
        root_layout.addWidget(self._table)

        # Painel de Métricas e Resultados
        self._lbl_metrics = QLabel("Pronto para adicionar arquivos.")
        self._lbl_metrics.setStyleSheet("font-size: 12px; font-weight: bold; color: #374151;")
        root_layout.addWidget(self._lbl_metrics)

    def _on_add_files(self):
        fpaths, _ = QFileDialog.getOpenFileNames(self, "Selecionar Arquivos para Compactar")
        if not fpaths:
            return
        for p in fpaths:
            path_obj = Path(p)
            if path_obj not in self._selected_items:
                self._selected_items.append(path_obj)
        self._update_table()

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta para Compactar")
        if folder:
            path_obj = Path(folder)
            if path_obj not in self._selected_items:
                self._selected_items.append(path_obj)
            self._update_table()

    def _on_clear_items(self):
        self._selected_items.clear()
        self._update_table()

    def _update_table(self):
        records = []
        for p in self._selected_items:
            is_dir = p.is_dir()
            size_str = "-" if is_dir else f"{p.stat().st_size / 1024:.1f} KB"
            records.append({
                "type": "Pasta" if is_dir else "Arquivo",
                "name": p.name,
                "size": size_str,
                "path": str(p),
            })
        self._table.set_records(records)
        self._lbl_metrics.setText(f"{len(self._selected_items)} item(ns) na fila para compactação.")

    def _on_start_creation(self):
        if not self._selected_items:
            QMessageBox.warning(self, "Aviso", "Por favor, adicione ao menos um arquivo ou pasta.")
            return

        out_zip_str, _ = QFileDialog.getSaveFileName(self, "Salvar Arquivo Compactado", "pacote.zip", "Arquivo ZIP (*.zip)")
        if not out_zip_str:
            return

        out_zip = Path(out_zip_str)
        method = self._combo_alg.currentData()
        level = self._spin_level.value()
        pwd = self._txt_password.text().strip() or None

        split_bytes = None
        if self._chk_split.isChecked():
            split_bytes = self._combo_split_size.currentData()

        self._lbl_metrics.setText("Compactando dados em segundo plano...")
        self._btn_create.setEnabled(False)

        self._runner.run(
            create_advanced_archive,
            self._selected_items,
            out_zip,
            compression_method=method,
            compress_level=level,
            split_size_bytes=split_bytes,
            password=pwd,
            on_success=self._on_creation_success,
            on_error=self._on_creation_error,
        )

    def _on_creation_success(self, res: dict):
        self._btn_create.setEnabled(True)
        orig_kb = res["uncompressed_bytes"] / 1024
        comp_kb = res["compressed_bytes"] / 1024
        pct = res["saving_percent"]
        ms = res["elapsed_ms"]

        vols = res.get("volumes", [])
        vol_info = f" | {len(vols)} volumes criados" if vols else ""

        msg = (
            f"Concluído com sucesso! Original: {orig_kb:.1f} KB ➔ Compactado: {comp_kb:.1f} KB "
            f"({pct:.1f}% de economia) em {ms:.0f} ms{vol_info}."
        )
        self._lbl_metrics.setStyleSheet("color: #047857; font-weight: bold;")
        self._lbl_metrics.setText(msg)

    def _on_creation_error(self, exc: Exception):
        self._btn_create.setEnabled(True)
        QMessageBox.critical(self, "Erro na Compactação", f"Falha ao criar arquivo: {exc}")
        self._lbl_metrics.setStyleSheet("color: #b91c1c; font-weight: bold;")
        self._lbl_metrics.setText("Erro na criação do arquivo.")
