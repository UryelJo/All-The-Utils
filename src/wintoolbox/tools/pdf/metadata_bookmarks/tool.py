"""
Interface gráfica do Editor de Metadados e Marcadores de PDF (pdf.metadata_bookmarks).
Permite alterar propriedades do documento (Título, Autor) e gerenciar o sumário interativo.
"""
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.pdf.metadata_bookmarks.logic import (
    extract_metadata_and_bookmarks,
    save_metadata_and_bookmarks,
)


@register
class MetadataBookmarksTool(Tool):
    id = "pdf.metadata_bookmarks"
    name = "Editor de Metadados e Sumário de PDF"
    description = "Edita metadados (título, autor, assunto) e gerencia a árvore de marcadores de sumário (bookmarks) de PDFs."
    category = "PDF"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Seleção de arquivo
        top_box = QHBoxLayout()
        top_box.addWidget(QLabel("Arquivo PDF:"))
        self._edit_pdf = QLineEdit()
        self._edit_pdf.setPlaceholderText("Selecione o arquivo PDF...")
        top_box.addWidget(self._edit_pdf)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_pdf)
        top_box.addWidget(btn_browse)

        self._btn_load = QPushButton("Carregar Dados")
        self._btn_load.clicked.connect(self._on_load_click)
        top_box.addWidget(self._btn_load)
        layout.addLayout(top_box)

        tabs = QTabWidget()

        # Aba 1: Metadados
        tab_meta = QWidget()
        form_meta = QFormLayout(tab_meta)
        self._edit_title = QLineEdit()
        form_meta.addRow("Título:", self._edit_title)

        self._edit_author = QLineEdit()
        form_meta.addRow("Autor:", self._edit_author)

        self._edit_subject = QLineEdit()
        form_meta.addRow("Assunto:", self._edit_subject)

        self._edit_keywords = QLineEdit()
        self._edit_keywords.setPlaceholderText("Separadas por vírgula ou ponto-e-vírgula")
        form_meta.addRow("Palavras-chave:", self._edit_keywords)
        tabs.addTab(tab_meta, "Metadados do Documento")

        # Aba 2: Marcadores de Sumário
        tab_bm = QWidget()
        bm_layout = QVBoxLayout(tab_bm)

        bm_btn_box = QHBoxLayout()
        btn_add_bm = QPushButton("Adicionar Marcador")
        btn_add_bm.clicked.connect(self._on_add_bookmark)
        bm_btn_box.addWidget(btn_add_bm)

        btn_del_bm = QPushButton("Remover Selecionado")
        btn_del_bm.clicked.connect(self._on_remove_bookmark)
        bm_btn_box.addWidget(btn_del_bm)
        bm_btn_box.addStretch()
        bm_layout.addLayout(bm_btn_box)

        self._table_bm = QTableWidget(0, 2)
        self._table_bm.setHorizontalHeaderLabels(["Título do Marcador", "Página de Destino"])
        self._table_bm.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table_bm.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        bm_layout.addWidget(self._table_bm)

        tabs.addTab(tab_bm, "Marcadores de Sumário (TOC)")
        layout.addWidget(tabs)

        # Salvar
        self._btn_save = QPushButton("Salvar Alterações no PDF...")
        self._btn_save.clicked.connect(self._on_save_click)
        layout.addWidget(self._btn_save)

        self._lbl_status = QLabel("Pronto.")
        layout.addWidget(self._lbl_status)

        self._total_pages = 1
        return widget

    def _on_browse_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Selecionar PDF", "", "Arquivos PDF (*.pdf)")
        if path:
            self._edit_pdf.setText(path)
            self._on_load_click()

    def _on_load_click(self) -> None:
        pdf_str = self._edit_pdf.text().strip()
        if not pdf_str:
            QMessageBox.warning(None, "Aviso", "Selecione um arquivo PDF.")
            return

        pdf_path = Path(pdf_str)
        if not pdf_path.is_file():
            QMessageBox.critical(None, "Erro", f"Arquivo não encontrado: {pdf_path}")
            return

        self._lbl_status.setText("Lendo metadados e marcadores...")
        self._btn_load.setEnabled(False)

        def worker():
            return extract_metadata_and_bookmarks(pdf_path)

        def on_done(data: Dict[str, Any]):
            self._btn_load.setEnabled(True)
            self._total_pages = data.get("total_pages", 1)
            meta = data.get("metadata", {})
            self._edit_title.setText(meta.get("title", ""))
            self._edit_author.setText(meta.get("author", ""))
            self._edit_subject.setText(meta.get("subject", ""))
            self._edit_keywords.setText(meta.get("keywords", ""))

            bms = data.get("bookmarks", [])
            self._table_bm.setRowCount(len(bms))
            for row, b in enumerate(bms):
                self._table_bm.setItem(row, 0, QTableWidgetItem(b.get("title", "")))
                self._table_bm.setItem(row, 1, QTableWidgetItem(str(b.get("page", 1))))

            self._lbl_status.setText(f"Dados carregados: {len(bms)} marcadores de sumário encontrados.")

        def on_error(err: str):
            self._btn_load.setEnabled(True)
            self._lbl_status.setText(f"Erro: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao ler PDF: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _on_add_bookmark(self) -> None:
        row = self._table_bm.rowCount()
        self._table_bm.insertRow(row)
        self._table_bm.setItem(row, 0, QTableWidgetItem("Novo Marcador"))
        self._table_bm.setItem(row, 1, QTableWidgetItem("1"))

    def _on_remove_bookmark(self) -> None:
        row = self._table_bm.currentRow()
        if row >= 0:
            self._table_bm.removeRow(row)

    def _on_save_click(self) -> None:
        pdf_str = self._edit_pdf.text().strip()
        if not pdf_str:
            return

        pdf_path = Path(pdf_str)
        out_path_str, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar PDF Atualizado Como",
            str(pdf_path.parent / f"{pdf_path.stem}_editado.pdf"),
            "Arquivos PDF (*.pdf)",
        )
        if not out_path_str:
            return

        out_path = Path(out_path_str)

        metadata = {
            "title": self._edit_title.text().strip(),
            "author": self._edit_author.text().strip(),
            "subject": self._edit_subject.text().strip(),
            "keywords": self._edit_keywords.text().strip(),
        }

        bookmarks = []
        for row in range(self._table_bm.rowCount()):
            t_item = self._table_bm.item(row, 0)
            p_item = self._table_bm.item(row, 1)
            title = t_item.text().strip() if t_item else ""
            try:
                page_val = int(p_item.text().strip()) if p_item else 1
            except ValueError:
                page_val = 1
            if title:
                bookmarks.append({"title": title, "page": page_val})

        self._lbl_status.setText("Gravando metadados e marcadores no PDF...")
        self._btn_save.setEnabled(False)

        def worker():
            return save_metadata_and_bookmarks(pdf_path, out_path, metadata, bookmarks)

        def on_done(res_path: Path):
            self._btn_save.setEnabled(True)
            self._lbl_status.setText(f"PDF gravado com sucesso: {res_path.name}")
            QMessageBox.information(
                None,
                "Sucesso",
                f"O arquivo PDF com metadados e sumário atualizados foi salvo em:\n{res_path}",
            )

        def on_error(err: str):
            self._btn_save.setEnabled(True)
            self._lbl_status.setText(f"Erro: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao salvar PDF: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)
