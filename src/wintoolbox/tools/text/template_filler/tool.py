"""
Interface gráfica Fluent da ferramenta Mala Direta e Preenchimento de Modelos.
"""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.text.template_filler.logic import (
    extract_placeholders,
    fill_template,
    generate_batch_files,
    parse_csv_data,
)


@register
class TemplateFillerTool(Tool):
    """Ferramenta para preenchimento em lote de modelos de texto a partir de planilhas CSV."""
    id = "text.template_filler"
    name = "Mala Direta e Modelos"
    title = "Mala Direta e Modelos"
    category = "Texto e Redação"
    description = (
        "Preenchedor offline de modelos com sintaxe {{campo}} combinados com dados de planilhas CSV "
        "para geração em massa de contratos, certificados, mensagens e relatórios."
    )
    icon = "Mail"

    def __init__(self) -> None:
        super().__init__()
        self._current_index: int = 0
        self._headers: list[str] = []
        self._records: list[dict[str, str]] = []

    def build_view(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho
        header = QLabel("Mala Direta e Preenchimento de Modelos")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Crie um modelo com placeholders na forma {{nome}}, importe uma tabela CSV "
            "e gere dezenas de documentos individuais ou um arquivo consolidado com total privacidade offline."
        )
        desc.setStyleSheet("color: gray;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Tabs de Trabalho
        tabs = QTabWidget()

        # Tab 1: Modelo e Tags
        tab_template = QWidget()
        v_temp = QVBoxLayout(tab_template)
        v_temp.setContentsMargins(8, 8, 8, 8)
        v_temp.setSpacing(8)

        lbl_tags = QLabel("Placeholders detectados no modelo:")
        v_temp.addWidget(lbl_tags)
        self.lbl_detected_tags = QLabel("(Nenhum campo inserido ainda)")
        self.lbl_detected_tags.setStyleSheet("color: #0078D4; font-weight: bold;")
        v_temp.addWidget(self.lbl_detected_tags)

        self.edit_template = QTextEdit()
        self.edit_template.setPlaceholderText(
            "Digite o modelo aqui. Exemplo:\n\n"
            "Prezado(a) {{nome | title}},\n\n"
            "Confirmamos a sua inscrição no curso de {{curso}}.\n"
            "Sua matrícula é {{matricula}} e o vencimento da fatura é {{vencimento}}.\n\n"
            "Atenciosamente,\nEquipe da Escola."
        )
        self.edit_template.textChanged.connect(self._on_template_changed)
        v_temp.addWidget(self.edit_template)
        tabs.addTab(tab_template, "1. Modelo de Texto")

        # Tab 2: Dados CSV
        tab_csv = QWidget()
        v_csv = QVBoxLayout(tab_csv)
        v_csv.setContentsMargins(8, 8, 8, 8)
        v_csv.setSpacing(8)

        csv_bar = QHBoxLayout()
        btn_import_csv = QPushButton("Carregar Arquivo CSV...")
        btn_import_csv.clicked.connect(self._on_browse_csv)
        csv_bar.addWidget(btn_import_csv)

        btn_sample_csv = QPushButton("Preencher com Exemplo")
        btn_sample_csv.clicked.connect(self._load_sample_csv)
        csv_bar.addWidget(btn_sample_csv)

        self.lbl_csv_status = QLabel("Nenhum dado carregado")
        self.lbl_csv_status.setStyleSheet("font-weight: bold;")
        csv_bar.addWidget(self.lbl_csv_status)
        csv_bar.addStretch()
        v_csv.addLayout(csv_bar)

        self.edit_csv = QTextEdit()
        self.edit_csv.setPlaceholderText(
            "Cole os dados em formato CSV (com cabeçalhos na primeira linha). Exemplo:\n"
            "nome,curso,matricula,vencimento\n"
            "Ana Souza,Python Avançado,2024-001,10/11/2026\n"
            "Carlos Lima,Segurança Defensiva,2024-002,15/11/2026\n"
            "Mariana Silva,Machine Learning,2024-003,20/11/2026"
        )
        self.edit_csv.textChanged.connect(self._on_csv_changed)
        v_csv.addWidget(self.edit_csv)
        tabs.addTab(tab_csv, "2. Dados (CSV / Tabela)")

        # Tab 3: Pré-visualização
        tab_preview = QWidget()
        v_prev = QVBoxLayout(tab_preview)
        v_prev.setContentsMargins(8, 8, 8, 8)
        v_prev.setSpacing(8)

        nav_bar = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Registro Anterior")
        self.btn_prev.clicked.connect(self._prev_record)
        nav_bar.addWidget(self.btn_prev)

        self.lbl_nav_info = QLabel("Registro 0 de 0")
        self.lbl_nav_info.setStyleSheet("font-weight: bold; font-size: 14px;")
        nav_bar.addWidget(self.lbl_nav_info)

        self.btn_next = QPushButton("Próximo Registro ▶")
        self.btn_next.clicked.connect(self._next_record)
        nav_bar.addWidget(self.btn_next)
        nav_bar.addStretch()

        btn_copy_preview = QPushButton("Copiar Este Registro")
        btn_copy_preview.clicked.connect(self._on_copy_preview)
        nav_bar.addWidget(btn_copy_preview)

        v_prev.addLayout(nav_bar)

        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)
        v_prev.addWidget(self.text_preview)
        tabs.addTab(tab_preview, "3. Pré-visualização")

        # Tab 4: Exportação em Lote
        tab_export = QWidget()
        v_exp = QVBoxLayout(tab_export)
        v_exp.setContentsMargins(8, 8, 8, 8)
        v_exp.setSpacing(14)

        grp_individual = QGroupBox("Geração de Múltiplos Arquivos Individuais")
        v_ind = QVBoxLayout(grp_individual)
        v_ind.setSpacing(8)

        lbl_pattern = QLabel("Padrão de nome dos arquivos (use placeholders como {{nome}} ou {{index}}):")
        v_ind.addWidget(lbl_pattern)
        self.edit_filename_pattern = QLineEdit("documento_{{index}}_{{nome}}.txt")
        v_ind.addWidget(self.edit_filename_pattern)

        self.btn_batch_export = QPushButton("Gerar e Salvar Todos os Arquivos em uma Pasta...")
        self.btn_batch_export.setStyleSheet("font-weight: bold; padding: 8px;")
        self.btn_batch_export.clicked.connect(self._on_batch_export)
        v_ind.addWidget(self.btn_batch_export)
        v_exp.addWidget(grp_individual)

        grp_consolidated = QGroupBox("Exportar em Arquivo Único Consolidado")
        v_con = QVBoxLayout(grp_consolidated)
        v_con.setSpacing(8)

        lbl_sep = QLabel("Separador entre documentos:")
        v_con.addWidget(lbl_sep)
        self.edit_separator = QLineEdit("\n\n" + "=" * 50 + "\n\n")
        v_con.addWidget(self.edit_separator)

        self.btn_consolidated_export = QPushButton("Salvar Arquivo Único Consolidado...")
        self.btn_consolidated_export.setStyleSheet("padding: 8px;")
        self.btn_consolidated_export.clicked.connect(self._on_consolidated_export)
        v_con.addWidget(self.btn_consolidated_export)
        v_exp.addWidget(grp_consolidated)

        v_exp.addStretch()
        tabs.addTab(tab_export, "4. Exportar Lote")

        layout.addWidget(tabs, 1)

        # Iniciar com dados de exemplo
        self._load_sample_csv()
        self.edit_template.setPlainText(
            "Prezado(a) {{nome | title}},\n\n"
            "Confirmamos a sua inscrição no curso de {{curso}}.\n"
            "Sua matrícula é {{matricula}} e a data de início é {{vencimento}}.\n\n"
            "Atenciosamente,\nCoordenação Acadêmica."
        )

        return container

    def _load_sample_csv(self) -> None:
        sample = (
            "nome,curso,matricula,vencimento\n"
            "ana souza,Python Avançado,2024-001,10/11/2026\n"
            "carlos lima,Segurança Defensiva,2024-002,15/11/2026\n"
            "mariana silva,Machine Learning,2024-003,20/11/2026"
        )
        self.edit_csv.setPlainText(sample)

    def _on_template_changed(self) -> None:
        tpl = self.edit_template.toPlainText()
        tags = extract_placeholders(tpl)
        if tags:
            self.lbl_detected_tags.setText(", ".join(f"{{{{{t}}}}}" for t in tags))
        else:
            self.lbl_detected_tags.setText("(Nenhum campo inserido ainda)")
        self._update_preview()

    def _on_csv_changed(self) -> None:
        content = self.edit_csv.toPlainText()
        headers, rows = parse_csv_data(content)
        self._headers = headers
        self._records = rows
        total = len(rows)
        self.lbl_csv_status.setText(f"{total} registro(s) encontrado(s) com colunas: {', '.join(headers)}")
        if self._current_index >= total:
            self._current_index = max(0, total - 1)
        self._update_preview()

    def _on_browse_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Selecionar Planilha CSV",
            "",
            "Arquivos CSV (*.csv);;Arquivos de Texto (*.txt);;Todos os Arquivos (*.*)",
        )
        if path:
            try:
                text = Path(path).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = Path(path).read_text(encoding="latin-1")
            self.edit_csv.setPlainText(text)

    def _update_preview(self) -> None:
        total = len(self._records)
        if total == 0:
            self.lbl_nav_info.setText("Registro 0 de 0")
            self.text_preview.setPlainText("Nenhum dado CSV para visualizar.")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            return

        idx = max(0, min(self._current_index, total - 1))
        self._current_index = idx
        self.lbl_nav_info.setText(f"Registro {idx + 1} de {total}")
        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setEnabled(idx < total - 1)

        row = dict(self._records[idx])
        row["index"] = str(idx + 1)
        tpl = self.edit_template.toPlainText()
        filled = fill_template(tpl, row, default_val="[NÃO PREENCHIDO]")
        self.text_preview.setPlainText(filled)

    def _prev_record(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._update_preview()

    def _next_record(self) -> None:
        if self._current_index < len(self._records) - 1:
            self._current_index += 1
            self._update_preview()

    def _on_copy_preview(self) -> None:
        txt = self.text_preview.toPlainText()
        if txt:
            cb = QApplication.clipboard()
            if cb:
                cb.setText(txt)

    def _on_batch_export(self) -> None:
        if not self._records:
            QMessageBox.warning(None, "Aviso", "Não há registros de dados para gerar.")
            return

        dest_dir = QFileDialog.getExistingDirectory(None, "Selecione a Pasta para Salvar os Arquivos")
        if not dest_dir:
            return

        tpl = self.edit_template.toPlainText()
        pattern = self.edit_filename_pattern.text().strip() or "doc_{{index}}.txt"
        files = generate_batch_files(
            template=tpl,
            records=self._records,
            output_dir=Path(dest_dir),
            filename_template=pattern,
        )
        QMessageBox.information(
            None,
            "Sucesso",
            f"{len(files)} arquivos gerados com sucesso na pasta:\n{dest_dir}",
        )

    def _on_consolidated_export(self) -> None:
        if not self._records:
            QMessageBox.warning(None, "Aviso", "Não há registros de dados para gerar.")
            return

        dest_file, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Arquivo Consolidado",
            "documentos_consolidados.txt",
            "Arquivos de Texto (*.txt);;Todos os Arquivos (*.*)",
        )
        if not dest_file:
            return

        tpl = self.edit_template.toPlainText()
        sep = self.edit_separator.text().replace("\\n", "\n")
        chunks = []
        for idx, row in enumerate(self._records, start=1):
            ctx = dict(row)
            ctx["index"] = str(idx)
            chunks.append(fill_template(tpl, ctx))

        full_content = sep.join(chunks)
        Path(dest_file).write_text(full_content, encoding="utf-8")
        QMessageBox.information(
            None,
            "Sucesso",
            f"Arquivo consolidado gerado com {len(self._records)} registros:\n{dest_file}",
        )
