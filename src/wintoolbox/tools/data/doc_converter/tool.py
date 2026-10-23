"""
Ferramenta: Conversor e Visualizador de Markdown para HTML.
Editor interativo com prévia em tempo real, suporte a código e exportação autônoma.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
    QTextBrowser, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.data.doc_converter.logic import markdown_to_html

SAMPLE_MARKDOWN = """# All the Utils — Documento de Demonstração

Bem-vindo ao **Conversor de Documentos Markdown para HTML**.

## Recursos Principais
- Suporte a tabelas estruturadas
- Blocos de código monoespaçados
- Tipografia moderna compatível com Windows 11 Fluent Design
- Exportação autônoma para arquivo `.html`

### Tabela de Exemplo
| Módulo | Tipo | Status |
| :--- | :--- | :--- |
| `pdf.split_merge` | Tool | Operacional |
| `pdf.compress` | FileTool | Operacional |
| `pdf.security` | Tool | Operacional |

### Bloco de Código Python
```python
def saudacao(nome: str) -> str:
    return f"Olá, {nome}! Bem-vindo ao All the Utils."
```

> Este documento pode ser visualizado diretamente no navegador ou exportado.
"""


@register
class DocConverterTool(Tool):
    id = "data.doc_converter"
    name = "Conversor de Markdown para HTML"
    category = "Dados e Estruturas"
    description = "Edite, visualize e converta documentos Markdown (.md) em páginas HTML autônomas estilizadas"
    keywords = ["markdown", "html", "documento", "converter", "md", "preview", "visualizador", "exportar"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QFrame(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QLabel("Conversor de Markdown para HTML")
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(header)

        # Barra de ferramentas superior
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        btn_open = QPushButton("Carregar Arquivo .md...")
        btn_open.clicked.connect(self._on_load_file)
        toolbar.addWidget(btn_open)

        btn_render = QPushButton("Renderizar Prévia")
        btn_render.setProperty("class", "primary")
        btn_render.clicked.connect(self._on_render_preview)
        toolbar.addWidget(btn_render)

        toolbar.addStretch()

        btn_copy = QPushButton("Copiar HTML")
        btn_copy.clicked.connect(self._on_copy_html)
        toolbar.addWidget(btn_copy)

        btn_export = QPushButton("Exportar como .html...")
        btn_export.clicked.connect(self._on_export_html)
        toolbar.addWidget(btn_export)

        btn_clear = QPushButton("Limpar")
        btn_clear.clicked.connect(self._on_clear)
        toolbar.addWidget(btn_clear)

        layout.addLayout(toolbar)

        # Divisor lado a lado (Editor vs Prévia)
        splitter = QSplitter(Qt.Horizontal)

        # Painel Esquerdo: Markdown
        panel_left = QFrame()
        layout_left = QVBoxLayout(panel_left)
        layout_left.setContentsMargins(0, 0, 0, 0)
        layout_left.setSpacing(4)

        lbl_editor = QLabel("Código Markdown de Origem:")
        lbl_editor.setStyleSheet("font-weight: 600; font-size: 12px;")
        layout_left.addWidget(lbl_editor)

        self.txt_markdown = QPlainTextEdit()
        self.txt_markdown.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        self.txt_markdown.setPlainText(SAMPLE_MARKDOWN)
        self.txt_markdown.textChanged.connect(self._on_render_preview)
        layout_left.addWidget(self.txt_markdown)
        splitter.addWidget(panel_left)

        # Painel Direito: Prévia HTML
        panel_right = QFrame()
        layout_right = QVBoxLayout(panel_right)
        layout_right.setContentsMargins(0, 0, 0, 0)
        layout_right.setSpacing(4)

        lbl_preview = QLabel("Pré-visualização do Documento:")
        lbl_preview.setStyleSheet("font-weight: 600; font-size: 12px;")
        layout_right.addWidget(lbl_preview)

        self.browser_preview = QTextBrowser()
        self.browser_preview.setOpenExternalLinks(True)
        layout_right.addWidget(self.browser_preview)
        splitter.addWidget(panel_right)

        splitter.setSizes([450, 450])
        layout.addWidget(splitter, stretch=1)

        # Render inicial
        self._on_render_preview()

        return container

    def _on_load_file(self):
        file, _ = QFileDialog.getOpenFileName(None, "Carregar Markdown", "", "Markdown (*.md *.txt);;Todos (*.*)")
        if file:
            try:
                content = Path(file).read_text(encoding="utf-8")
                self.txt_markdown.setPlainText(content)
                self._on_render_preview()
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao ler arquivo: {e}")

    def _on_render_preview(self):
        text = self.txt_markdown.toPlainText()
        html = markdown_to_html(text, full_html=True)
        self.browser_preview.setHtml(html)

    def _on_copy_html(self):
        text = self.txt_markdown.toPlainText()
        html = markdown_to_html(text, full_html=True)
        QApplication.clipboard().setText(html)
        QMessageBox.information(None, "Copiado", "Código HTML copiado para a área de transferência!")

    def _on_export_html(self):
        text = self.txt_markdown.toPlainText()
        if not text.strip():
            QMessageBox.warning(None, "Aviso", "O editor está vazio.")
            return

        file, _ = QFileDialog.getSaveFileName(None, "Exportar Documento HTML", "documento.html", "Página Web (*.html)")
        if file:
            try:
                html = markdown_to_html(text, full_html=True)
                Path(file).write_text(html, encoding="utf-8")
                QMessageBox.information(None, "Exportado", f"Arquivo HTML exportado com sucesso em:\n{file}")
            except Exception as e:
                QMessageBox.critical(None, "Erro", f"Falha ao salvar: {e}")

    def _on_clear(self):
        self.txt_markdown.clear()
        self.browser_preview.clear()
