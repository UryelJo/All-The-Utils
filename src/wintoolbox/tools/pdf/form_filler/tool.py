"""
Interface gráfica do Preenchedor de Formulários PDF (pdf.form_filler).
Permite visualizar todos os campos de um formulário PDF (AcroForm), preencher valores e achatar o documento.
"""
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.pdf.form_filler.logic import (
    get_pdf_form_fields,
    fill_pdf_form,
    export_form_values_json,
)


@register
class FormFillerTool(Tool):
    id = "pdf.form_filler"
    name = "Preenchedor de Formulários PDF"
    description = "Preenchedor de formulários PDF: preenche campos interativos AcroForm automaticamente e achata (flatten) o documento para evitar alterações posteriores."
    category = "PDF"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Seleção de arquivo
        form_file = QFormLayout()
        self._edit_pdf = QLineEdit()
        self._edit_pdf.setPlaceholderText("Selecione o arquivo PDF contendo campos de formulário...")
        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_pdf)

        box_f = QHBoxLayout()
        box_f.addWidget(self._edit_pdf)
        box_f.addWidget(btn_browse)

        self._btn_load = QPushButton("Carregar Campos")
        self._btn_load.clicked.connect(self._on_load_fields)
        box_f.addWidget(self._btn_load)

        form_file.addRow("Arquivo PDF:", box_f)
        layout.addLayout(form_file)

        # Tabela de Campos
        lbl_tbl = QLabel("Campos Detectados no Formulário (Edite os valores na coluna 'Valor'):")
        lbl_tbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_tbl)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Nome do Campo", "Tipo", "Valor / Conteúdo"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self._table)

        # Opções e Ações
        bot_box = QHBoxLayout()
        self._chk_flatten = QCheckBox("Achatar formulário (Flatten - torna o PDF preenchido não-editável)")
        self._chk_flatten.setChecked(True)
        bot_box.addWidget(self._chk_flatten)
        bot_box.addStretch()

        btn_export_json = QPushButton("Exportar JSON...")
        btn_export_json.clicked.connect(self._on_export_json)
        bot_box.addWidget(btn_export_json)

        self._btn_fill = QPushButton("Preencher e Salvar PDF...")
        self._btn_fill.clicked.connect(self._on_fill_click)
        bot_box.addWidget(self._btn_fill)

        layout.addLayout(bot_box)

        self._lbl_status = QLabel("Selecione um PDF de formulário para carregar os campos.")
        layout.addWidget(self._lbl_status)
        return widget

    def _on_browse_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Selecionar PDF", "", "Arquivos PDF (*.pdf)")
        if path:
            self._edit_pdf.setText(path)
            self._on_load_fields()

    def _on_load_fields(self) -> None:
        pdf_str = self._edit_pdf.text().strip()
        if not pdf_str:
            QMessageBox.warning(None, "Aviso", "Selecione o arquivo PDF primeiro.")
            return

        pdf_path = Path(pdf_str)
        if not pdf_path.is_file():
            QMessageBox.critical(None, "Erro", f"Arquivo não encontrado: {pdf_path}")
            return

        self._lbl_status.setText("Carregando campos do formulário...")
        self._btn_load.setEnabled(False)

        def worker():
            return get_pdf_form_fields(pdf_path)

        def on_done(fields: List[Dict[str, Any]]):
            self._btn_load.setEnabled(True)
            self._table.setRowCount(len(fields))
            for row, f in enumerate(fields):
                # Campo nome (não-editável)
                item_name = QTableWidgetItem(f["name"])
                item_name.setFlags(item_name.flags() & ~item_name.flags().ItemIsEditable)
                self._table.setItem(row, 0, item_name)

                # Tipo (não-editável)
                item_type = QTableWidgetItem(f["type"])
                item_type.setFlags(item_type.flags() & ~item_type.flags().ItemIsEditable)
                self._table.setItem(row, 1, item_type)

                # Valor (editável)
                item_val = QTableWidgetItem(f["value"])
                self._table.setItem(row, 2, item_val)

            count = len(fields)
            if count > 0:
                self._lbl_status.setText(f"{count} campos de formulário carregados com sucesso.")
            else:
                self._lbl_status.setText("Nenhum campo de formulário interativo (AcroForm) encontrado neste PDF.")

        def on_error(err: str):
            self._btn_load.setEnabled(True)
            self._lbl_status.setText(f"Erro: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao carregar campos: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _collect_field_values(self) -> Dict[str, str]:
        values: Dict[str, str] = {}
        for row in range(self._table.rowCount()):
            name_item = self._table.item(row, 0)
            val_item = self._table.item(row, 2)
            if name_item and val_item:
                values[name_item.text()] = val_item.text()
        return values

    def _on_export_json(self) -> None:
        values = self._collect_field_values()
        if not values:
            QMessageBox.warning(None, "Aviso", "Nenhum valor preenchido para exportar.")
            return

        path, _ = QFileDialog.getSaveFileName(None, "Exportar Dados do Formulário", "dados_formulario.json", "Arquivos JSON (*.json)")
        if path:
            export_form_values_json(values, Path(path))
            QMessageBox.information(None, "Sucesso", f"Dados exportados com sucesso em:\n{path}")

    def _on_fill_click(self) -> None:
        pdf_str = self._edit_pdf.text().strip()
        if not pdf_str:
            return

        values = self._collect_field_values()
        if not values:
            QMessageBox.warning(None, "Aviso", "Carregue os campos do formulário antes de preencher.")
            return

        pdf_path = Path(pdf_str)
        out_path_str, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar PDF Preenchido Como",
            str(pdf_path.parent / f"{pdf_path.stem}_preenchido.pdf"),
            "Arquivos PDF (*.pdf)",
        )
        if not out_path_str:
            return

        out_path = Path(out_path_str)
        flatten = self._chk_flatten.isChecked()

        self._lbl_status.setText("Preenchendo formulário...")
        self._btn_fill.setEnabled(False)

        def worker():
            return fill_pdf_form(pdf_path, values, out_path, flatten=flatten)

        def on_done(res_path: Path):
            self._btn_fill.setEnabled(True)
            self._lbl_status.setText(f"Formulário preenchido com sucesso: {res_path.name}")
            QMessageBox.information(
                None,
                "Preenchimento Concluído",
                f"O documento preenchido foi gerado com sucesso em:\n{res_path}",
            )

        def on_error(err: str):
            self._btn_fill.setEnabled(True)
            self._lbl_status.setText(f"Erro: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao preencher formulário: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)
