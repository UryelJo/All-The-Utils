"""
Interface gráfica da ferramenta Extrator de Dados Estruturados via Regex (data.regex_extract).
Permite minerar e extrair e-mails, URLs, IPs, CPFs, UUIDs, telefones e expressões personalizadas,
apresentando em tabela ordenável (DataTableView) e exportando para CSV/TSV/JSON.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from wintoolbox.tools.data.regex_extract.logic import (
    BUILTIN_PATTERNS,
    export_records_to_text,
    extract_structured_data,
)
from wintoolbox.ui.widgets.data_table import Column, DataTableView


@register
class RegexExtractTool(Tool):
    id = "data.regex_extract"
    name = "Extrator de Dados com Regex"
    category = "Dados e Estruturas"
    description = (
        "Extrai em massa e-mails, URLs, IPs, CPFs, UUIDs, datas, telefones e expressões regulares "
        "personalizadas a partir de textos brutos, gerando listas e tabelas exportáveis."
    )
    keywords = ["regex", "extrair", "emails", "urls", "ips", "cpf", "uuid", "mineracao", "dados"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return RegexExtractView(self, parent)


class RegexExtractView(QWidget):
    def __init__(self, tool: RegexExtractTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_records = []
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

        # Barra de Configuração do Padrão
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Padrão Comum:"))
        self._combo_pattern = QComboBox()
        self._combo_pattern.addItem("Personalizado", "")
        for key, info in BUILTIN_PATTERNS.items():
            self._combo_pattern.addItem(f"{info['name']} ({key})", key)
        self._combo_pattern.currentIndexChanged.connect(self._on_preset_changed)
        top_bar.addWidget(self._combo_pattern)

        top_bar.addWidget(QLabel("Regex:"))
        self._txt_regex = QLineEdit(BUILTIN_PATTERNS["emails"]["pattern"])
        self._txt_regex.setFont(QFont("Consolas", 10))
        top_bar.addWidget(self._txt_regex)

        root_layout.addLayout(top_bar)

        # Opções
        opts_bar = QHBoxLayout()
        self._chk_dedup = QCheckBox("Remover duplicatas")
        self._chk_dedup.setChecked(True)
        opts_bar.addWidget(self._chk_dedup)

        self._chk_ignore_case = QCheckBox("Ignorar maiúsculas/minúsculas")
        self._chk_ignore_case.setChecked(True)
        opts_bar.addWidget(self._chk_ignore_case)

        opts_bar.addStretch()

        btn_run = QPushButton("Extrair Dados")
        btn_run.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        btn_run.clicked.connect(self._run_extraction)
        opts_bar.addWidget(btn_run)

        root_layout.addLayout(opts_bar)

        # Splitter Vertical: Entrada de Texto em cima, Tabela de Resultados embaixo
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Entrada
        in_group = QGroupBox("Texto Bruto de Entrada")
        in_layout = QVBoxLayout(in_group)
        self._txt_input = QPlainTextEdit()
        self._txt_input.setFont(QFont("Consolas", 9))
        self._txt_input.setPlaceholderText("Cole aqui o texto, logs ou relatório contendo os dados a serem extraídos...")
        in_layout.addWidget(self._txt_input)

        sample_btn = QPushButton("Carregar Exemplo com Dados Mistos")
        sample_btn.clicked.connect(self._load_sample_data)
        in_layout.addWidget(sample_btn)

        splitter.addWidget(in_group)

        # Resultados
        out_group = QGroupBox("Dados Extraídos")
        out_layout = QVBoxLayout(out_group)

        self._lbl_status = QLabel("Nenhum dado extraído.")
        self._lbl_status.setStyleSheet("color: #4b5563; font-weight: bold; font-size: 11px;")
        out_layout.addWidget(self._lbl_status)

        cols = [
            Column("index", "#", width=50),
            Column("value", "Dado Extraído", width=280),
            Column("type", "Tipo", width=140),
            Column("position", "Posição", width=100),
            Column("length", "Tamanho", width=80),
        ]
        self._table = DataTableView(cols, key="index", parent=self)
        out_layout.addWidget(self._table)

        # Ações de Exportação
        act_bar = QHBoxLayout()
        btn_copy_list = QPushButton("Copiar como Lista")
        btn_copy_list.clicked.connect(lambda: self._copy_export("list"))
        act_bar.addWidget(btn_copy_list)

        btn_copy_csv = QPushButton("Copiar como CSV")
        btn_copy_csv.clicked.connect(lambda: self._copy_export("csv"))
        act_bar.addWidget(btn_copy_csv)

        btn_copy_json = QPushButton("Copiar como JSON")
        btn_copy_json.clicked.connect(lambda: self._copy_export("json"))
        act_bar.addWidget(btn_copy_json)

        act_bar.addStretch()
        out_layout.addLayout(act_bar)

        splitter.addWidget(out_group)
        splitter.setSizes([200, 320])
        root_layout.addWidget(splitter)

    def _on_preset_changed(self, index: int):
        key = self._combo_pattern.currentData()
        if key in BUILTIN_PATTERNS:
            self._txt_regex.setText(BUILTIN_PATTERNS[key]["pattern"])

    def _run_extraction(self):
        raw_text = self._txt_input.toPlainText()
        pattern = self._txt_regex.text().strip()
        dedup = self._chk_dedup.isChecked()
        ign_case = self._chk_ignore_case.isChecked()

        lbl_type = self._combo_pattern.currentText()
        if not pattern:
            QMessageBox.warning(self, "Aviso", "Por favor, especifique uma expressão regular.")
            return

        try:
            records = extract_structured_data(
                raw_text, pattern, pattern_label=lbl_type, deduplicate=dedup, ignore_case=ign_case
            )
            self._current_records = records
            self._table.set_records(records)
            self._lbl_status.setText(f"{len(records)} registro(s) encontrado(s) com sucesso!")
        except Exception as exc:
            QMessageBox.critical(self, "Erro no Regex", f"Falha na execução do padrão: {exc}")
            self._lbl_status.setText("Erro ao executar Regex.")

    def _load_sample_data(self):
        sample = (
            "Logs do Sistema - 2026-10-27\n"
            "Usuário admin@wintoolbox.local conectou-se de 192.168.1.100 às 10:15:32.\n"
            "Contato de suporte: suporte@empresa.com.br ou suporte@empresa.com.br (duplicado).\n"
            "Chave de sessão: 550e8400-e29b-41d4-a716-446655440000 gerada com sucesso.\n"
            "Mais detalhes em https://wintoolbox.app/docs e http://intranet.local/status?id=42.\n"
            "Responsável CPF: 123.456.789-00 ou ligue para (11) 98765-4321."
        )
        self._txt_input.setPlainText(sample)
        self._combo_pattern.setCurrentIndex(1)  # Seleciona E-mails
        self._run_extraction()

    def _copy_export(self, format_type: str):
        if not self._current_records:
            return
        exported = export_records_to_text(self._current_records, format_type=format_type)
        QGuiApplication.clipboard().setText(exported)
        self._lbl_status.setText(f"Copiado para a área de transferência no formato {format_type.upper()}!")
