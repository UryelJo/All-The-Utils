"""
Interface gráfica da ferramenta Tarjamento e Censura em PDF (pdf.redact).
Permite censurar palavras-chave sensíveis ou áreas com tarjas opacas permanentes.
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.pdf.redact.logic import redact_terms_and_regions


@register
class RedactTool(Tool):
    id = "pdf.redact"
    name = "Censura e Tarjamento em PDF"
    description = "Aplica tarjamento permanente (Redaction) sobre termos confidenciais ou áreas sensíveis em PDFs."
    category = "PDF"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Seleção de arquivo
        form_file = QFormLayout()
        self._edit_pdf = QLineEdit()
        self._edit_pdf.setPlaceholderText("Selecione o arquivo PDF para censurar...")
        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_pdf)

        box_f = QHBoxLayout()
        box_f.addWidget(self._edit_pdf)
        box_f.addWidget(btn_browse)
        form_file.addRow("Arquivo PDF:", box_f)
        layout.addLayout(form_file)

        # Termos para censura
        lbl_terms = QLabel("Palavras-chave e Termos Confidenciais (um por linha):")
        lbl_terms.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_terms)

        self._text_terms = QTextEdit()
        self._text_terms.setPlaceholderText("Exemplos:\n123.456.789-00\nconfidencial\nsegredo\nvalor_salario")
        layout.addWidget(self._text_terms)

        # Opções
        opt_box = QHBoxLayout()
        self._chk_case = QCheckBox("Diferenciar maiúsculas/minúsculas (Case Sensitive)")
        self._chk_case.setChecked(False)
        opt_box.addWidget(self._chk_case)

        self._combo_color = QComboBox()
        self._combo_color.addItem("Tarja Preta Opaca (Padrão de Censura)", True)
        self._combo_color.addItem("Tarja Branca (Ocultamento)", False)
        opt_box.addWidget(QLabel("Cor da Tarja:"))
        opt_box.addWidget(self._combo_color)
        opt_box.addStretch()
        layout.addLayout(opt_box)

        # Botão de Ação
        self._btn_redact = QPushButton("Censurar Documento e Salvar PDF...")
        self._btn_redact.clicked.connect(self._on_redact_click)
        layout.addWidget(self._btn_redact)

        self._lbl_status = QLabel("Informe o PDF e os termos confidenciais.")
        layout.addWidget(self._lbl_status)
        return widget

    def _on_browse_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Selecionar PDF", "", "Arquivos PDF (*.pdf)")
        if path:
            self._edit_pdf.setText(path)

    def _on_redact_click(self) -> None:
        raw_pdf = self._edit_pdf.text().strip()
        if not raw_pdf:
            QMessageBox.warning(None, "Aviso", "Por favor, selecione o arquivo PDF.")
            return

        pdf_path = Path(raw_pdf)
        if not pdf_path.is_file():
            QMessageBox.critical(None, "Erro", f"Arquivo não encontrado: {pdf_path}")
            return

        terms_text = self._text_terms.toPlainText()
        terms = [line.strip() for line in terms_text.splitlines() if line.strip()]
        if not terms:
            QMessageBox.warning(None, "Aviso", "Informe ao menos um termo ou palavra-chave para censurar.")
            return

        out_path_str, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar PDF Censurado Como",
            str(pdf_path.parent / f"{pdf_path.stem}_censurado.pdf"),
            "Arquivos PDF (*.pdf)",
        )
        if not out_path_str:
            return

        out_path = Path(out_path_str)
        case_sens = self._chk_case.isChecked()
        black_fill = self._combo_color.currentData()

        self._lbl_status.setText("Localizando termos e aplicando tarjas opacas...")
        self._btn_redact.setEnabled(False)

        def worker():
            return redact_terms_and_regions(
                pdf_path=pdf_path,
                output_pdf_path=out_path,
                terms=terms,
                case_sensitive=case_sens,
                fill_color_black=black_fill,
            )

        def on_done(res: Dict[str, Any]):
            self._btn_redact.setEnabled(True)
            total = res.get("total_redactions", 0)
            pages = res.get("pages_affected", 0)
            self._lbl_status.setText(
                f"Censura concluída: {total} ocorrências tarjadas em {pages} páginas."
            )
            QMessageBox.information(
                None,
                "Censura Concluída",
                f"{total} ocorrências confidenciais foram tarjadas com sucesso em:\n{out_path}",
            )

        def on_error(err: str):
            self._btn_redact.setEnabled(True)
            self._lbl_status.setText(f"Erro na censura: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao censurar PDF: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)
