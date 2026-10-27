"""
Interface gráfica da ferramenta Gerador de PDF Pesquisável com OCR (pdf.ocr_searchable).
Permite converter scans, fotos de documentos e PDFs não-pesquisáveis em documentos PDF com texto selecionável (Ctrl+F).
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.pdf.ocr_searchable.logic import (
    convert_scanned_pdf_to_searchable,
)


@register
class OcrSearchablePdfTool(Tool):
    id = "pdf.ocr_searchable"
    name = "Gerador de PDF Pesquisável (OCR)"
    category = "PDF"
    description = (
        "Converte PDFs digitalizados (scans) e fotos de documentos em PDFs pesquisáveis (Searchable PDF), "
        "injetando camada de texto invisível sobre as imagens para permitir busca (Ctrl+F) e seleção de texto."
    )
    keywords = ["pdf", "ocr", "pesquisavel", "searchable", "scan", "digitalizado", "texto", "converter"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return OcrSearchablePdfView(self, parent)


class OcrSearchablePdfView(QWidget):
    def __init__(self, tool: OcrSearchablePdfTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._runner = TaskRunner()
        self._selected_input_file: Optional[Path] = None
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

        # Seleção de Arquivo
        top_bar = QHBoxLayout()
        self._txt_input_path = QLineEdit()
        self._txt_input_path.setPlaceholderText("Selecione um PDF digitalizado ou imagem (PNG, JPG, TIFF)...")
        self._txt_input_path.setReadOnly(True)
        top_bar.addWidget(self._txt_input_path)

        btn_browse = QPushButton("Selecionar Arquivo...")
        btn_browse.clicked.connect(self._on_browse_file)
        top_bar.addWidget(btn_browse)

        self._btn_run = QPushButton("Gerar PDF Pesquisável...")
        self._btn_run.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self._btn_run.clicked.connect(self._on_start_conversion)
        top_bar.addWidget(self._btn_run)

        root_layout.addLayout(top_bar)

        self._lbl_status = QLabel("Nenhum arquivo carregado.")
        self._lbl_status.setStyleSheet("color: #4b5563; font-size: 11px; font-weight: bold;")
        root_layout.addWidget(self._lbl_status)

        # Painel de Pré-visualização do Texto Reconhecido
        group_out = QGroupBox("Texto Reconhecido pelo OCR (Camada Injetada)")
        group_layout = QVBoxLayout(group_out)

        self._txt_preview = QPlainTextEdit()
        self._txt_preview.setFont(QFont("Consolas", 10))
        self._txt_preview.setReadOnly(True)
        self._txt_preview.setPlaceholderText("O texto reconhecido aparecerá aqui após o processamento...")
        group_layout.addWidget(self._txt_preview)

        act_bar = QHBoxLayout()
        btn_copy_text = QPushButton("Copiar Texto Extraído")
        btn_copy_text.clicked.connect(self._copy_extracted_text)
        act_bar.addWidget(btn_copy_text)
        act_bar.addStretch()
        group_layout.addLayout(act_bar)

        root_layout.addWidget(group_out)

    def _on_browse_file(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar PDF ou Imagem",
            "",
            "Arquivos Suportados (*.pdf *.png *.jpg *.jpeg *.bmp *.tiff);;Todos (*.*)",
        )
        if not fpath:
            return
        self._selected_input_file = Path(fpath)
        self._txt_input_path.setText(str(self._selected_input_file))
        self._lbl_status.setText("Arquivo pronto para conversão com OCR.")

    def _on_start_conversion(self):
        if not self._selected_input_file or not self._selected_input_file.is_file():
            QMessageBox.warning(self, "Aviso", "Por favor, selecione um arquivo de origem primeiro.")
            return

        default_out = f"pesquisavel_{self._selected_input_file.stem}.pdf"
        out_fpath, _ = QFileDialog.getSaveFileName(self, "Salvar PDF Pesquisável", default_out, "PDF (*.pdf)")
        if not out_fpath:
            return

        self._lbl_status.setText("Processando OCR e gerando camada de texto pesquisável...")
        self._btn_run.setEnabled(False)

        self._runner.run(
            convert_scanned_pdf_to_searchable,
            self._selected_input_file,
            Path(out_fpath),
            on_success=self._on_conversion_success,
            on_error=self._on_conversion_error,
        )

    def _on_conversion_success(self, res: dict):
        self._btn_run.setEnabled(True)
        self._txt_preview.setPlainText(res.get("extracted_text", ""))
        p_count = res.get("total_pages", 1)
        w_count = res.get("total_words", 0)

        msg = f"PDF pesquisável gerado com sucesso! ({p_count} página(s), {w_count} palavras indexadas)."
        self._lbl_status.setStyleSheet("color: #047857; font-weight: bold;")
        self._lbl_status.setText(msg)

    def _on_conversion_error(self, exc: Exception):
        self._btn_run.setEnabled(True)
        QMessageBox.critical(self, "Erro no OCR", f"Falha na conversão: {exc}")
        self._lbl_status.setStyleSheet("color: #b91c1c; font-weight: bold;")
        self._lbl_status.setText("Erro durante o processamento de OCR.")

    def _copy_extracted_text(self):
        txt = self._txt_preview.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)
