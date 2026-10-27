"""
Interface gráfica do Extrator de Tabelas de PDF para CSV e Excel (pdf.tables_to_csv).
Permite detectar tabelas estruturadas em relatórios PDF e exportar para CSV ou Excel (.xlsx).
"""
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtWidgets import (
    QComboBox,
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
from wintoolbox.tools.pdf.tables_to_csv.logic import (
    extract_tables_from_pdf,
    export_tables_to_csv,
    export_tables_to_excel,
)


@register
class TablesToCsvTool(Tool):
    id = "pdf.tables_to_csv"
    name = "Extrator de Tabelas de PDF (CSV / Excel)"
    description = "Extrator de tabelas de PDF: detecta grades e tabelas em relatórios em PDF e exporta os dados estruturados para planilhas CSV e Excel."
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
        self._edit_pdf.setPlaceholderText("Selecione o arquivo PDF contendo tabelas...")
        top_box.addWidget(self._edit_pdf)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_pdf)
        top_box.addWidget(btn_browse)

        self._btn_extract = QPushButton("Extrair Tabelas")
        self._btn_extract.clicked.connect(self._on_extract_click)
        top_box.addWidget(self._btn_extract)
        layout.addLayout(top_box)

        # Seletor de Tabela Encontrada
        sel_box = QHBoxLayout()
        sel_box.addWidget(QLabel("Tabela:"))
        self._combo_tables = QComboBox()
        self._combo_tables.currentIndexChanged.connect(self._on_table_selected)
        sel_box.addWidget(self._combo_tables)
        sel_box.addStretch()
        layout.addLayout(sel_box)

        # Visualizador da Tabela Selecionada
        self._table_preview = QTableWidget(0, 0)
        layout.addWidget(self._table_preview)

        # Botões de Exportação
        btn_box = QHBoxLayout()
        self._btn_export_csv = QPushButton("Exportar Todas para CSV...")
        self._btn_export_csv.setEnabled(False)
        self._btn_export_csv.clicked.connect(self._on_export_csv_click)
        btn_box.addWidget(self._btn_export_csv)

        self._btn_export_excel = QPushButton("Exportar para Excel (.xlsx)...")
        self._btn_export_excel.setEnabled(False)
        self._btn_export_excel.clicked.connect(self._on_export_excel_click)
        btn_box.addWidget(self._btn_export_excel)
        btn_box.addStretch()
        layout.addLayout(btn_box)

        self._lbl_status = QLabel("Selecione um arquivo PDF para iniciar a extração de tabelas.")
        layout.addWidget(self._lbl_status)

        self._extracted_tables: List[Dict[str, Any]] = []
        return widget

    def _on_browse_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Selecionar PDF", "", "Arquivos PDF (*.pdf)")
        if path:
            self._edit_pdf.setText(path)
            self._on_extract_click()

    def _on_extract_click(self) -> None:
        raw_pdf = self._edit_pdf.text().strip()
        if not raw_pdf:
            QMessageBox.warning(None, "Aviso", "Selecione o arquivo PDF.")
            return

        pdf_path = Path(raw_pdf)
        if not pdf_path.is_file():
            QMessageBox.critical(None, "Erro", f"Arquivo não encontrado: {pdf_path}")
            return

        self._lbl_status.setText("Analisando páginas e extraindo tabelas estruturadas...")
        self._btn_extract.setEnabled(False)

        def worker():
            return extract_tables_from_pdf(pdf_path)

        def on_done(tables: List[Dict[str, Any]]):
            self._btn_extract.setEnabled(True)
            self._extracted_tables = tables
            self._combo_tables.clear()

            if not tables:
                self._lbl_status.setText("Nenhuma tabela estruturada detectada nas páginas deste PDF.")
                self._btn_export_csv.setEnabled(False)
                self._btn_export_excel.setEnabled(False)
                self._table_preview.setRowCount(0)
                self._table_preview.setColumnCount(0)
                return

            for idx, t in enumerate(tables):
                lbl = f"Tabela {idx+1} (Página {t['page']} — {t['row_count']} linhas x {t['col_count']} colunas)"
                self._combo_tables.addItem(lbl, idx)

            self._btn_export_csv.setEnabled(True)
            self._btn_export_excel.setEnabled(True)
            self._lbl_status.setText(f"{len(tables)} tabelas detectadas com sucesso!")
            self._on_table_selected(0)

        def on_error(err: str):
            self._btn_extract.setEnabled(True)
            self._lbl_status.setText(f"Erro: {err}")
            QMessageBox.critical(None, "Erro", f"Falha ao extrair tabelas: {err}")

        TaskRunner.run(worker, on_success=on_done, on_error=on_error)

    def _on_table_selected(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._extracted_tables):
            return

        t = self._extracted_tables[idx]
        rows = t.get("rows", [])
        if not rows:
            self._table_preview.setRowCount(0)
            self._table_preview.setColumnCount(0)
            return

        cols = t.get("col_count", 0)
        self._table_preview.setRowCount(len(rows))
        self._table_preview.setColumnCount(cols)

        for r_idx, row in enumerate(rows):
            for c_idx in range(cols):
                val = row[c_idx] if c_idx < len(row) else ""
                self._table_preview.setItem(r_idx, c_idx, QTableWidgetItem(val))

    def _on_export_csv_click(self) -> None:
        if not self._extracted_tables:
            return

        out_dir = QFileDialog.getExistingDirectory(None, "Selecione a Pasta para Salvar os Arquivos CSV")
        if not out_dir:
            return

        target_dir = Path(out_dir)
        files = export_tables_to_csv(self._extracted_tables, target_dir)
        QMessageBox.information(
            None,
            "Exportação Concluída",
            f"{len(files)} arquivos CSV gerados com sucesso na pasta:\n{out_dir}",
        )

    def _on_export_excel_click(self) -> None:
        if not self._extracted_tables:
            return

        out_path_str, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Pasta de Trabalho do Excel",
            "tabelas_extraidas.xlsx",
            "Planilhas do Excel (*.xlsx)",
        )
        if not out_path_str:
            return

        out_path = Path(out_path_str)
        export_tables_to_excel(self._extracted_tables, out_path)
        QMessageBox.information(
            None,
            "Exportação Concluída",
            f"Arquivo Excel gerado com sucesso com {len(self._extracted_tables)} abas em:\n{out_path}",
        )
