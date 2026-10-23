"""
Interface gráfica da ferramenta Gerador de Dados Fictícios para Testes e Desenvolvimento.
"""
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.fake_data.logic import (
    AVAILABLE_FIELDS, export_dataset, generate_dataset, generate_lorem_ipsum
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("dev.fake_data.ui")


@register
class FakeDataTool(Tool):
    id = "dev.fake_data"
    name = "Gerador de Dados Fictícios"
    category = "Desenvolvimento"
    description = "Geração em lote de dados sintéticos para testes (CPF, CNPJ, nomes, endereços, e-mails) e Lorem Ipsum"
    keywords = ["fake", "dados", "teste", "mock", "lorem", "ipsum", "cpf", "cnpj", "dev", "desenvolvimento", "gerador", "seed"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return FakeDataView(self, parent)


class FakeDataView(QWidget):
    def __init__(self, tool: FakeDataTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._checkboxes: Dict[str, QCheckBox] = {}
        self._last_generated_text = ""
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Gerador de Dados Fictícios",
            "Crie massas de dados realistas e válidas para bancos de dados, testes unitários e APIs sem necessidade de conexão."
        ))

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_dataset_tab(), "Dados Estruturados em Lote")
        self.tabs.addTab(self._build_lorem_tab(), "Gerador Lorem Ipsum")
        root.addWidget(self.tabs, stretch=1)

    def _build_dataset_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        # 1. Configurações e Campos
        cfg_box = QGroupBox("Campos para Geração")
        grid_fields = QGridLayout(cfg_box)
        grid_fields.setSpacing(6)

        default_checked = {"nome", "cpf", "email", "telefone", "cidade", "uf"}
        row, col = 0, 0
        for key, label in AVAILABLE_FIELDS.items():
            cb = QCheckBox(label)
            cb.setChecked(key in default_checked)
            self._checkboxes[key] = cb
            grid_fields.addWidget(cb, row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1

        layout.addWidget(cfg_box)

        # 2. Parâmetros de Exportação
        params_row = QHBoxLayout()
        params_row.setSpacing(12)

        params_row.addWidget(QLabel("Quantidade:"))
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 5000)
        self.spin_count.setValue(20)
        self.spin_count.setFixedWidth(90)
        params_row.addWidget(self.spin_count)

        params_row.addWidget(QLabel("Formato:"))
        self.cmb_format = QComboBox()
        self.cmb_format.addItems(["JSON", "CSV (Ponto e Vírgula)", "SQL INSERT", "Texto Legível"])
        self.cmb_format.currentIndexChanged.connect(self._on_format_changed)
        params_row.addWidget(self.cmb_format)

        self.lbl_table = QLabel("Tabela SQL:")
        self.txt_table = QLineEdit("usuarios")
        self.txt_table.setFixedWidth(110)
        self.lbl_table.setVisible(False)
        self.txt_table.setVisible(False)
        params_row.addWidget(self.lbl_table)
        params_row.addWidget(self.txt_table)

        self.cb_format_docs = QCheckBox("Formatar Documentos (Pontuação)")
        self.cb_format_docs.setChecked(True)
        params_row.addWidget(self.cb_format_docs)

        params_row.addStretch()

        self.btn_generate = QPushButton("Gerar Dados")
        self.btn_generate.setProperty("class", "primary")
        self.btn_generate.clicked.connect(self._on_generate_dataset)
        params_row.addWidget(self.btn_generate)

        layout.addLayout(params_row)

        # 3. Área de Prévia e Ações
        self.txt_preview = QTextEdit()
        self.txt_preview.setFont(QFont("Cascadia Mono, Consolas, Courier New", 9))
        self.txt_preview.setPlaceholderText("Clique em 'Gerar Dados' para visualizar o resultado...")
        layout.addWidget(self.txt_preview, stretch=1)

        actions_bar = QHBoxLayout()
        self.lbl_summary = QLabel("Nenhum dado gerado.")
        self.lbl_summary.setProperty("class", "secondary")
        actions_bar.addWidget(self.lbl_summary)
        actions_bar.addStretch()

        self.btn_copy = QPushButton("Copiar para Área de Transferência")
        self.btn_copy.clicked.connect(self._on_copy_dataset)
        actions_bar.addWidget(self.btn_copy)

        self.btn_save = QPushButton("Salvar em Arquivo...")
        self.btn_save.clicked.connect(self._on_save_dataset)
        actions_bar.addWidget(self.btn_save)

        layout.addLayout(actions_bar)
        return tab

    def _build_lorem_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(12)

        ctrl_row.addWidget(QLabel("Quantidade:"))
        self.spin_lorem_count = QSpinBox()
        self.spin_lorem_count.setRange(1, 100)
        self.spin_lorem_count.setValue(3)
        self.spin_lorem_count.setFixedWidth(80)
        ctrl_row.addWidget(self.spin_lorem_count)

        ctrl_row.addWidget(QLabel("Unidade:"))
        self.cmb_lorem_unit = QComboBox()
        self.cmb_lorem_unit.addItems(["Parágrafos", "Frases", "Palavras"])
        ctrl_row.addWidget(self.cmb_lorem_unit)

        ctrl_row.addStretch()

        btn_gen_lorem = QPushButton("Gerar Lorem Ipsum")
        btn_gen_lorem.setProperty("class", "primary")
        btn_gen_lorem.clicked.connect(self._on_generate_lorem)
        ctrl_row.addWidget(btn_gen_lorem)

        layout.addLayout(ctrl_row)

        self.txt_lorem = QTextEdit()
        self.txt_lorem.setFont(QFont("Segoe UI", 10))
        self.txt_lorem.setPlaceholderText("Texto gerado aparecerá aqui...")
        layout.addWidget(self.txt_lorem, stretch=1)

        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        btn_copy_lorem = QPushButton("Copiar Texto")
        btn_copy_lorem.clicked.connect(lambda: self._copy_text(self.txt_lorem.toPlainText()))
        bottom_bar.addWidget(btn_copy_lorem)
        layout.addLayout(bottom_bar)

        return tab

    def _on_format_changed(self, index: int) -> None:
        is_sql = (index == 2)
        self.lbl_table.setVisible(is_sql)
        self.txt_table.setVisible(is_sql)

    def _on_generate_dataset(self) -> None:
        selected_fields = [k for k, cb in self._checkboxes.items() if cb.isChecked()]
        if not selected_fields:
            show_toast(self, "Aviso", "Selecione ao menos um campo para gerar os dados.", kind="warning")
            return

        count = self.spin_count.value()
        fmt_idx = self.cmb_format.currentIndex()
        fmt_map = {0: "json", 1: "csv", 2: "sql", 3: "txt"}
        fmt_type = fmt_map.get(fmt_idx, "json")
        tbl = self.txt_table.text().strip() or "usuarios"

        data = generate_dataset(
            fields=selected_fields,
            count=count,
            formatted_docs=self.cb_format_docs.isChecked()
        )
        output = export_dataset(data, format_type=fmt_type, table_name=tbl)
        self._last_generated_text = output
        self.txt_preview.setPlainText(output)
        self.lbl_summary.setText(f"{count} registro(s) gerado(s) com sucesso em formato {fmt_type.upper()}.")
        show_toast(self, "Dados Gerados", f"{count} registro(s) sintéticos prontos para uso.", kind="success")

    def _on_generate_lorem(self) -> None:
        count = self.spin_lorem_count.value()
        unit_map = {0: "paragraphs", 1: "sentences", 2: "words"}
        unit = unit_map.get(self.cmb_lorem_unit.currentIndex(), "paragraphs")
        text = generate_lorem_ipsum(count=count, unit=unit)
        self.txt_lorem.setPlainText(text)
        show_toast(self, "Lorem Ipsum", f"{count} {self.cmb_lorem_unit.currentText().lower()} gerados.", kind="success")

    def _on_copy_dataset(self) -> None:
        text = self.txt_preview.toPlainText()
        if not text:
            show_toast(self, "Aviso", "Nenhum dado gerado para copiar.", kind="warning")
            return
        self._copy_text(text)

    def _copy_text(self, text: str) -> None:
        if not text:
            return
        QApplication.clipboard().setText(text)
        show_toast(self, "Copiado", "Texto copiado para a área de transferência!", kind="info")

    def _on_save_dataset(self) -> None:
        text = self.txt_preview.toPlainText()
        if not text:
            show_toast(self, "Aviso", "Nenhum dado disponível para salvar.", kind="warning")
            return

        fmt_idx = self.cmb_format.currentIndex()
        exts = {0: ("Arquivo JSON (*.json)", ".json"),
                1: ("Arquivo CSV (*.csv)", ".csv"),
                2: ("Arquivo SQL (*.sql)", ".sql"),
                3: ("Arquivo de Texto (*.txt)", ".txt")}
        filter_str, def_ext = exts.get(fmt_idx, ("Arquivo de Texto (*.txt)", ".txt"))

        path, _ = QFileDialog.getSaveFileName(self, "Salvar Dados Fictícios", f"dados_ficticios{def_ext}", filter_str)
        if path:
            Path(path).write_text(text, encoding="utf-8")
            show_toast(self, "Salvo", f"Arquivo gravado com sucesso em:\n{path}", kind="success")
