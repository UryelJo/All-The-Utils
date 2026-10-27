"""
Interface gráfica Fluent para o Exportador de Árvore de Pastas.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.files.tree_export.logic import (
    build_directory_tree,
    export_ascii_tree,
    export_csv_tree,
    export_html_tree,
    export_markdown_tree,
)


@register
class FilesTreeExportTool(Tool):
    id = "files.tree_export"
    name = "Exportador de Árvore de Pastas"
    description = "Exportador de estrutura de pastas: gera a árvore de diretórios em representação visual ASCII/Unicode, formato Markdown, tabela CSV ou página HTML."
    category = "Arquivos e Pastas"
    icon = "List"
    tags = ["tree", "arvore", "diretorio", "pastas", "ascii", "markdown", "csv", "html"]

    def __init__(self) -> None:
        super().__init__()
        self._selected_path: Optional[str] = None
        self._last_tree: Optional[dict] = None

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Barra Superior de Controles
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        btn_select = QPushButton("Selecionar Pasta...")
        btn_select.setStyleSheet("font-weight: bold;")
        self.lbl_selected_dir = QLabel("Nenhuma pasta selecionada")
        self.lbl_selected_dir.setStyleSheet("color: #888888; font-style: italic;")

        top_bar.addWidget(btn_select)
        top_bar.addWidget(self.lbl_selected_dir, 1)

        layout.addLayout(top_bar)

        # Barra de Opções e Formato
        opt_bar = QHBoxLayout()
        opt_bar.setSpacing(10)

        opt_bar.addWidget(QLabel("Formato:"))
        self.combo_fmt = QComboBox()
        self.combo_fmt.addItem("Árvore ASCII / Unicode", "ascii")
        self.combo_fmt.addItem("Lista Markdown (.md)", "markdown")
        self.combo_fmt.addItem("Planilha Tabular CSV (.csv)", "csv")
        self.combo_fmt.addItem("Relatório Colapsável HTML (.html)", "html")
        opt_bar.addWidget(self.combo_fmt)

        opt_bar.addWidget(QLabel("Profundidade Máx:"))
        self.spin_depth = QSpinBox()
        self.spin_depth.setRange(1, 20)
        self.spin_depth.setValue(4)
        opt_bar.addWidget(self.spin_depth)

        self.chk_files = QCheckBox("Incluir Arquivos")
        self.chk_files.setChecked(True)
        opt_bar.addWidget(self.chk_files)

        self.chk_sizes = QCheckBox("Exibir Tamanhos")
        self.chk_sizes.setChecked(True)
        opt_bar.addWidget(self.chk_sizes)

        btn_generate = QPushButton("Gerar Árvore")
        btn_generate.setStyleSheet("font-weight: bold;")
        opt_bar.addWidget(btn_generate)

        btn_copy = QPushButton("Copiar")
        btn_save = QPushButton("Salvar Arquivo...")
        opt_bar.addWidget(btn_copy)
        opt_bar.addWidget(btn_save)

        layout.addLayout(opt_bar)

        self.lbl_status = QLabel("Selecione um diretório para gerar a representação estrutural.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Editor de Exibição
        self.text_preview = QPlainTextEdit()
        self.text_preview.setReadOnly(True)
        font = QFont("Consolas, Courier New, monospace", 10)
        self.text_preview.setFont(font)
        layout.addWidget(self.text_preview, 1)

        # Conexões
        btn_select.clicked.connect(self._on_select_folder)
        btn_generate.clicked.connect(self._on_generate)
        btn_copy.clicked.connect(self._on_copy)
        btn_save.clicked.connect(self._on_save)
        self.combo_fmt.currentIndexChanged.connect(self._render_current_tree)

        return container

    def _on_select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(None, "Selecione a Pasta")
        if folder:
            self._selected_path = folder
            self.lbl_selected_dir.setText(folder)
            self._on_generate()

    def _on_generate(self) -> None:
        if not self._selected_path:
            QMessageBox.information(None, "Aviso", "Selecione uma pasta primeiro.")
            return

        depth = self.spin_depth.value()
        inc_files = self.chk_files.isChecked()

        try:
            tree_data = build_directory_tree(self._selected_path, max_depth=depth, include_files=inc_files)
            self._last_tree = tree_data
            self._render_current_tree()
            self.lbl_status.setText(f"Árvore gerada com sucesso para '{Path(self._selected_path).name}'.")
        except Exception as exc:
            QMessageBox.critical(None, "Erro ao Gerar Árvore", f"Falha na leitura:\n{exc}")

    def _render_current_tree(self) -> None:
        if not self._last_tree:
            return

        fmt = self.combo_fmt.currentData()
        show_size = self.chk_sizes.isChecked()

        if fmt == "ascii":
            content = export_ascii_tree(self._last_tree, show_size=show_size)
        elif fmt == "markdown":
            content = export_markdown_tree(self._last_tree, show_size=show_size)
        elif fmt == "csv":
            content = export_csv_tree(self._last_tree)
        elif fmt == "html":
            content = export_html_tree(self._last_tree, show_size=show_size)
        else:
            content = ""

        self.text_preview.setPlainText(content)

    def _on_copy(self) -> None:
        txt = self.text_preview.toPlainText()
        if txt:
            QApplication.clipboard().setText(txt)
            self.lbl_status.setText("Conteúdo copiado para a área de transferência!")

    def _on_save(self) -> None:
        txt = self.text_preview.toPlainText()
        if not txt:
            return

        fmt = self.combo_fmt.currentData()
        ext_map = {"ascii": ".txt", "markdown": ".md", "csv": ".csv", "html": ".html"}
        ext = ext_map.get(fmt, ".txt")

        path, _ = QFileDialog.getSaveFileName(None, "Salvar Árvore", f"arvore{ext}", f"Arquivo (*{ext})")
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(txt)
            self.lbl_status.setText(f"Salvo com sucesso em: {path}")
        except Exception as exc:
            QMessageBox.critical(None, "Erro ao Salvar", str(exc))
