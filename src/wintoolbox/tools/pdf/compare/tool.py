"""
Interface gráfica do Comparador de Documentos PDF (pdf.compare).
Permite comparar duas versões de um PDF lado a lado com realce de diferenças de texto e status por página.
"""
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.pdf.compare.logic import compare_pdf_documents


@register
class PdfCompareTool(Tool):
    id = "pdf.compare"
    name = "Comparador de Documentos PDF"
    description = "Compara duas versões de um documento PDF destacando alterações de texto, adições e exclusões."
    category = "PDF"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Seleção dos dois PDFs
        form_files = QFormLayout()

        # PDF A
        self._edit_pdf_a = QLineEdit()
        self._edit_pdf_a.setPlaceholderText("Selecione a primeira versão (PDF A)...")
        btn_browse_a = QPushButton("Procurar...")
        btn_browse_a.clicked.connect(self._on_browse_a)
        box_a = QHBoxLayout()
        box_a.addWidget(self._edit_pdf_a)
        box_a.addWidget(btn_browse_a)
        form_files.addRow("Documento A (Original):", box_a)

        # PDF B
        self._edit_pdf_b = QLineEdit()
        self._edit_pdf_b.setPlaceholderText("Selecione a segunda versão (PDF B)...")
        btn_browse_b = QPushButton("Procurar...")
        btn_browse_b.clicked.connect(self._on_browse_b)
        box_b = QHBoxLayout()
        box_b.addWidget(self._edit_pdf_b)
        box_b.addWidget(btn_browse_b)
        form_files.addRow("Documento B (Revisão):", box_b)

        layout.addLayout(form_files)

        # Botão Comparar
        self._btn_compare = QPushButton("Comparar Documentos")
        self._btn_compare.clicked.connect(self._on_compare_click)
        layout.addWidget(self._btn_compare)

        # Resumo de Estatísticas
        self._lbl_summary = QLabel("Selecione os dois arquivos PDF para iniciar a comparação.")
        self._lbl_summary.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._lbl_summary)

        # Barra de Navegação por Página
        nav_box = QHBoxLayout()
        nav_box.addWidget(QLabel("Navegar pela Página:"))
        self._combo_pages = QComboBox()
        self._combo_pages.currentIndexChanged.connect(self._on_page_selected)
        nav_box.addWidget(self._combo_pages)
        nav_box.addStretch()
        layout.addLayout(nav_box)

        # Divisor Lado a Lado
        splitter = QSplitter(Qt.Horizontal)

        # Painel A
        left_widget = QWidget()
        l_layout = QVBoxLayout(left_widget)
        l_layout.setContentsMargins(0, 0, 0, 0)
        l_layout.addWidget(QLabel("Conteúdo PDF A:"))
        self._text_a = QTextEdit()
        self._text_a.setReadOnly(True)
        l_layout.addWidget(self._text_a)
        splitter.addWidget(left_widget)

        # Painel B
        right_widget = QWidget()
        r_layout = QVBoxLayout(right_widget)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.addWidget(QLabel("Conteúdo PDF B:"))
        self._text_b = QTextEdit()
        self._text_b.setReadOnly(True)
        r_layout.addWidget(self._text_b)
        splitter.addWidget(right_widget)

        layout.addWidget(splitter, 1)

        self._diff_result: Dict[str, Any] = {}
        return widget

    def _on_browse_a(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Selecionar PDF A", "", "Arquivos PDF (*.pdf)")
        if path:
            self._edit_pdf_a.setText(path)

    def _on_browse_b(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Selecionar PDF B", "", "Arquivos PDF (*.pdf)")
        if path:
            self._edit_pdf_b.setText(path)

    def _on_compare_click(self) -> None:
        a_str = self._edit_pdf_a.text().strip()
        b_str = self._edit_pdf_b.text().strip()

        if not a_str or not b_str:
            QMessageBox.warning(None, "Aviso", "Selecione os dois documentos PDF para comparar.")
            return

        path_a = Path(a_str)
        path_b = Path(b_str)

        if not path_a.is_file() or not path_b.is_file():
            QMessageBox.critical(None, "Erro", "Um dos arquivos PDF selecionados não existe.")
            return

        self._lbl_summary.setText("Extraindo textos e analisando diferenças...")
        self._btn_compare.setEnabled(False)

        def worker():
            return compare_pdf_documents(path_a, path_b)

        def on_done(res: Dict[str, Any]):
            self._btn_compare.setEnabled(True)
            self._diff_result = res
            self._combo_pages.clear()

            pages = res.get("pages", [])
            identical = res.get("identical_pages", 0)
            modified = res.get("modified_pages", 0)
            total = res.get("total_pages_compared", 0)

            self._lbl_summary.setText(
                f"Comparação Concluída: {total} páginas avaliadas — {identical} idênticas, {modified} com alterações."
            )

            for p in pages:
                st = p["status"]
                sim = int(p["similarity"] * 100)
                lbl = f"Página {p['page']} [{st} — {sim}% similaridade]"
                self._combo_pages.addItem(lbl, p["page"] - 1)

            if pages:
                self._on_page_selected(0)

        def on_error(err: str):
            self._btn_compare.setEnabled(True)
            self._lbl_summary.setText(f"Erro na comparação: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao comparar PDFs: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _on_page_selected(self, idx: int) -> None:
        pages = self._diff_result.get("pages", [])
        if idx < 0 or idx >= len(pages):
            return

        page_data = pages[idx]
        self._text_a.setPlainText(page_data.get("text_a", ""))
        self._text_b.setPlainText(page_data.get("text_b", ""))
