"""
Ferramenta: Editor e Pré-visualizador de Markdown (Markdown Editor).
Edição em duas colunas com renderização HTML em tempo real estilo GitHub e exportação.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QSplitter,
    QTextBrowser, QVBoxLayout, QWidget, QMessageBox
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.text.markdown_editor.logic import (
    export_markdown_file,
    render_markdown_to_html,
)


@register
class MarkdownEditorTool(Tool):
    id = "text.markdown_editor"
    name = "Editor de Markdown"
    category = "Texto e Redação"
    description = "Editor de Markdown em duas colunas com pré-visualização HTML em tempo real e exportação"
    keywords = ["markdown", "md", "editor", "preview", "html", "documento", "texto", "gfm"]

    def __init__(self) -> None:
        super().__init__()
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._render_preview)

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        # Barra de Ferramentas / Formatação Rápida
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        btn_bold = QPushButton("B")
        btn_bold.setStyleSheet("font-weight: bold; width: 30px;")
        btn_bold.setToolTip("Negrito (**texto**)")
        btn_bold.clicked.connect(lambda: self._wrap_selection("**", "**"))
        toolbar.addWidget(btn_bold)

        btn_italic = QPushButton("I")
        btn_italic.setStyleSheet("font-style: italic; width: 30px;")
        btn_italic.setToolTip("Itálico (*texto*)")
        btn_italic.clicked.connect(lambda: self._wrap_selection("*", "*"))
        toolbar.addWidget(btn_italic)

        btn_h2 = QPushButton("H2")
        btn_h2.setStyleSheet("font-weight: 600; width: 36px;")
        btn_h2.setToolTip("Título Nível 2")
        btn_h2.clicked.connect(lambda: self._insert_prefix("## "))
        toolbar.addWidget(btn_h2)

        btn_quote = QPushButton("❝")
        btn_quote.setToolTip("Citação (> bloco)")
        btn_quote.clicked.connect(lambda: self._insert_prefix("> "))
        toolbar.addWidget(btn_quote)

        btn_code = QPushButton("</>")
        btn_code.setToolTip("Bloco de Código")
        btn_code.clicked.connect(lambda: self._wrap_selection("```python\n", "\n```"))
        toolbar.addWidget(btn_code)

        btn_table = QPushButton("Tabela")
        btn_table.clicked.connect(self._insert_table_template)
        toolbar.addWidget(btn_table)

        toolbar.addStretch()

        btn_export_html = QPushButton("Exportar HTML...")
        btn_export_html.clicked.connect(self._export_html)
        toolbar.addWidget(btn_export_html)

        btn_save_md = QPushButton("Salvar Markdown (.md)...")
        btn_save_md.clicked.connect(self._save_md)
        toolbar.addWidget(btn_save_md)

        main_layout.addLayout(toolbar)

        # Splitter Horizontal Lado a Lado
        splitter = QSplitter(Qt.Horizontal)

        # Painel Esquerdo: Editor
        left_box = QWidget()
        l_layout = QVBoxLayout(left_box)
        l_layout.setContentsMargins(0, 0, 0, 0)
        l_layout.setSpacing(6)
        l_layout.addWidget(QLabel("<b>Código Markdown:</b>"))

        self.txt_editor = QPlainTextEdit()
        self.txt_editor.setStyleSheet("font-family: Consolas, monospace; font-size: 13px;")
        self.txt_editor.setPlainText(
            "# Bem-vindo ao WinToolbox\n\n"
            "Este é um editor **Markdown** com prévia em tempo real.\n\n"
            "## Recursos Disponíveis:\n"
            "- Suporte a tabelas GFM\n"
            "- Blocos de código com sintaxe limpa\n"
            "- Exportação para HTML\n\n"
            "### Exemplo de Tabela:\n\n"
            "| Ferramenta | Categoria | Status |\n"
            "| :--- | :--- | :--- |\n"
            "| Markdown Editor | Texto | Concluído |\n"
            "| RegEx Tester | Texto | Concluído |\n"
        )
        self.txt_editor.textChanged.connect(self._schedule_render)
        l_layout.addWidget(self.txt_editor)
        splitter.addWidget(left_box)

        # Painel Direito: Preview HTML
        right_box = QWidget()
        r_layout = QVBoxLayout(right_box)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(6)
        r_layout.addWidget(QLabel("<b>Visualização Formatada (HTML):</b>"))

        self.browser_preview = QTextBrowser()
        self.browser_preview.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;")
        r_layout.addWidget(self.browser_preview)
        splitter.addWidget(right_box)

        splitter.setSizes([450, 550])
        main_layout.addWidget(splitter)

        self._render_preview()
        return container

    def _schedule_render(self) -> None:
        self._debounce_timer.start()

    def _render_preview(self) -> None:
        text = self.txt_editor.toPlainText()
        html_code = render_markdown_to_html(text, include_css=True)
        self.browser_preview.setHtml(html_code)

    def _wrap_selection(self, prefix: str, suffix: str) -> None:
        cursor = self.txt_editor.textCursor()
        sel = cursor.selectedText()
        if sel:
            cursor.insertText(f"{prefix}{sel}{suffix}")
        else:
            cursor.insertText(f"{prefix}texto{suffix}")

    def _insert_prefix(self, prefix: str) -> None:
        cursor = self.txt_editor.textCursor()
        cursor.insertText(prefix)

    def _insert_table_template(self) -> None:
        template = "\n| Coluna 1 | Coluna 2 | Coluna 3 |\n| :--- | :--- | :--- |\n| Item A | Item B | Item C |\n"
        cursor = self.txt_editor.textCursor()
        cursor.insertText(template)

    def _export_html(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Exportar Documento HTML",
            "documento.html",
            "Páginas HTML (*.html)"
        )
        if file_path:
            text = self.txt_editor.toPlainText()
            export_markdown_file(text, Path(file_path), format_type="html")
            QMessageBox.information(None, "Sucesso", f"Documento HTML exportado com sucesso em:\n{file_path}")

    def _save_md(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Arquivo Markdown",
            "documento.md",
            "Arquivos Markdown (*.md)"
        )
        if file_path:
            text = self.txt_editor.toPlainText()
            export_markdown_file(text, Path(file_path), format_type="md")
            QMessageBox.information(None, "Sucesso", f"Arquivo Markdown salvo com sucesso em:\n{file_path}")
