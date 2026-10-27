"""
Interface gráfica da ferramenta Comparador de Pastas (files.folder_diff).
Permite comparar duas árvores de pastas, identificando diferenças de tamanho, data e conteúdo hash,
com visualização em tabela interativa (DataTableView) e filtros.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.files.folder_diff.logic import compare_directories
from wintoolbox.ui.widgets.data_table import Column, DataTableView


@register
class FolderDiffTool(Tool):
    id = "files.folder_diff"
    name = "Comparador de Pastas"
    category = "Arquivos e Pastas"
    description = (
        "Compara duas árvores de diretórios detalhadamente, identificando arquivos novos, "
        "excluídos, modificados e idênticos com suporte a comparação profunda por hash SHA-256."
    )
    keywords = ["pastas", "diff", "comparar", "diretorios", "sincronizar", "arquivos", "arvore"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return FolderDiffView(self, parent)


class FolderDiffView(QWidget):
    def __init__(self, tool: FolderDiffTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._runner = TaskRunner()
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

        # Painel de Seleção das Pastas A e B
        sel_group = QGroupBox("Pastas para Comparação")
        sel_layout = QVBoxLayout(sel_group)

        # Pasta A
        row_a = QHBoxLayout()
        row_a.addWidget(QLabel("Pasta Origem (A):"))
        self._txt_dir_a = QLineEdit()
        self._txt_dir_a.setPlaceholderText("Selecione a primeira pasta...")
        row_a.addWidget(self._txt_dir_a)
        btn_browse_a = QPushButton("Procurar...")
        btn_browse_a.clicked.connect(lambda: self._on_browse_dir(self._txt_dir_a))
        row_a.addWidget(btn_browse_a)
        sel_layout.addLayout(row_a)

        # Pasta B
        row_b = QHBoxLayout()
        row_b.addWidget(QLabel("Pasta Destino (B):"))
        self._txt_dir_b = QLineEdit()
        self._txt_dir_b.setPlaceholderText("Selecione a segunda pasta...")
        row_b.addWidget(self._txt_dir_b)
        btn_browse_b = QPushButton("Procurar...")
        btn_browse_b.clicked.connect(lambda: self._on_browse_dir(self._txt_dir_b))
        row_b.addWidget(btn_browse_b)
        sel_layout.addLayout(row_b)

        root_layout.addWidget(sel_group)

        # Barra de Opções e Disparo
        ctrl_bar = QHBoxLayout()
        self._chk_hash = QCheckBox("Comparar por hash SHA-256 (validação binária profunda)")
        ctrl_bar.addWidget(self._chk_hash)

        self._chk_ignore_git = QCheckBox("Ignorar pastas ocultas e .git")
        self._chk_ignore_git.setChecked(True)
        ctrl_bar.addWidget(self._chk_ignore_git)

        ctrl_bar.addStretch()

        btn_run = QPushButton("Comparar Diretórios")
        btn_run.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        btn_run.clicked.connect(self._run_diff)
        ctrl_bar.addWidget(btn_run)

        root_layout.addLayout(ctrl_bar)

        # Barra de Resumo de Métricas
        self._lbl_summary = QLabel("Aguardando comparação...")
        self._lbl_summary.setStyleSheet("font-size: 12px; font-weight: bold; color: #374151;")
        root_layout.addWidget(self._lbl_summary)

        # Tabela de Resultados com DataTableView
        cols = [
            Column("status", "Status", width=110),
            Column("rel_path", "Caminho Relativo", width=260),
            Column("size_a", "Tamanho (A)", width=90, align="right"),
            Column("size_b", "Tamanho (B)", width=90, align="right"),
            Column("mtime_a", "Data (A)", width=130),
            Column("mtime_b", "Data (B)", width=130),
            Column("details", "Detalhes / Diagnóstico", width=220),
        ]
        self._table = DataTableView(cols, key="rel_path", parent=self)
        root_layout.addWidget(self._table)

    def _on_browse_dir(self, target_field: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Diretório")
        if folder:
            target_field.setText(folder)

    def _run_diff(self):
        dir_a_str = self._txt_dir_a.text().strip()
        dir_b_str = self._txt_dir_b.text().strip()

        if not dir_a_str or not dir_b_str:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione ambas as pastas (A e B).")
            return

        path_a = Path(dir_a_str)
        path_b = Path(dir_b_str)

        if not path_a.is_dir() or not path_b.is_dir():
            QMessageBox.critical(self, "Erro", "Uma ou ambas as pastas selecionadas não existem.")
            return

        use_hash = self._chk_hash.isChecked()
        patterns = [".git*", "*.tmp", "desktop.ini"] if self._chk_ignore_git.isChecked() else []

        self._lbl_summary.setText("Comparando diretórios em segundo plano...")
        self._runner.run(
            compare_directories,
            path_a,
            path_b,
            deep_hash_compare=use_hash,
            ignore_patterns=patterns,
            on_success=self._on_diff_success,
            on_error=self._on_diff_error,
        )

    def _on_diff_success(self, res: dict):
        records = res.get("records", [])
        summary = res.get("summary", {})
        self._table.set_records(records)

        tot = summary.get("total_files", 0)
        ident = summary.get("identical", 0)
        mod = summary.get("modified", 0)
        only_a = summary.get("only_a", 0)
        only_b = summary.get("only_b", 0)
        sim = summary.get("similarity_pct", 100.0)

        msg = (
            f"Total: {tot} arquivos | Similaridade: {sim:.1f}% | "
            f"Idênticos: {ident} | Modificados: {mod} | Apenas em A: {only_a} | Apenas em B: {only_b}"
        )
        self._lbl_summary.setText(msg)

    def _on_diff_error(self, exc: Exception):
        QMessageBox.critical(self, "Erro na Comparação", f"Falha ao comparar pastas: {exc}")
        self._lbl_summary.setText("Erro durante a execução da comparação.")
