"""
Interface gráfica da ferramenta Avaliador e Extrator JSONPath (data.json_path).
Permite executar expressões JSONPath RFC 9535 interativas em documentos JSON,
com visualização estruturada em tabela (DataTableView) e saída JSON formatada.
"""
import json
import time
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.data.json_path.logic import (
    SAMPLE_JSON,
    query_jsonpath,
)
from wintoolbox.ui.widgets.data_table import Column, DataTableView


@register
class JsonPathTool(Tool):
    id = "data.json_path"
    name = "Avaliador e Extrator JSONPath"
    category = "Dados e Estruturas"
    description = (
        "Avalia e extrai dados de estruturas JSON complexas usando expressões JSONPath "
        "(curingas, descida recursiva, fatiamentos e filtros de predicados)."
    )
    keywords = ["json", "jsonpath", "extrair", "query", "consulta", "filtro", "dados", "rfc9535"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return JsonPathView(self, parent)


class JsonPathView(QWidget):
    def __init__(self, tool: JsonPathTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
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

        # Barra de Expressão JSONPath
        expr_box = QHBoxLayout()
        expr_box.addWidget(QLabel("Expressão JSONPath:"))
        self._txt_expr = QLineEdit("$.store.book[*].title")
        self._txt_expr.setFont(QFont("Consolas", 10))
        self._txt_expr.returnPressed.connect(self._run_query)
        expr_box.addWidget(self._txt_expr)

        # Exemplos rápidos
        self._combo_presets = QComboBox()
        self._combo_presets.addItem("Exemplos rápidos...", "")
        self._combo_presets.addItem("Todos os títulos de livros: $.store.book[*].title", "$.store.book[*].title")
        self._combo_presets.addItem("Todos os preços em qualquer nível: $..price", "$..price")
        self._combo_presets.addItem("Livros com preço < 60: $.store.book[?(@.price < 60)]", "$.store.book[?(@.price < 60)]")
        self._combo_presets.addItem("Primeiro e segundo livro: $.store.book[0:2]", "$.store.book[0:2]")
        self._combo_presets.addItem("Último livro: $.store.book[-1]", "$.store.book[-1]")
        self._combo_presets.currentIndexChanged.connect(self._on_preset_selected)
        expr_box.addWidget(self._combo_presets)

        btn_run = QPushButton("Executar Consulta")
        btn_run.clicked.connect(self._run_query)
        expr_box.addWidget(btn_run)

        root_layout.addLayout(expr_box)

        # Splitter Principal: JSON de Entrada à esquerda, Resultados à direita
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Painel Esquerdo: JSON de Entrada
        in_widget = QWidget()
        in_layout = QVBoxLayout(in_widget)
        in_layout.setContentsMargins(0, 0, 0, 0)
        in_layout.setSpacing(6)

        in_bar = QHBoxLayout()
        in_bar.addWidget(QLabel("Documento JSON de Origem:"))
        in_bar.addStretch()

        btn_sample = QPushButton("Carregar Exemplo")
        btn_sample.clicked.connect(self._load_sample_json)
        in_bar.addWidget(btn_sample)

        btn_format = QPushButton("Formatar")
        btn_format.clicked.connect(self._format_json)
        in_bar.addWidget(btn_format)
        in_layout.addLayout(in_bar)

        self._txt_json = QPlainTextEdit()
        self._txt_json.setFont(QFont("Consolas", 9))
        self._txt_json.setPlaceholderText("Cole o JSON aqui ou clique em 'Carregar Exemplo'...")
        in_layout.addWidget(self._txt_json)

        splitter.addWidget(in_widget)

        # Painel Direito: Resultados
        out_widget = QWidget()
        out_layout = QVBoxLayout(out_widget)
        out_layout.setContentsMargins(0, 0, 0, 0)
        out_layout.setSpacing(6)

        self._lbl_status = QLabel("Pronto")
        self._lbl_status.setStyleSheet("color: #4b5563; font-weight: bold; font-size: 11px;")
        out_layout.addWidget(self._lbl_status)

        self._result_tabs = QTabWidget()

        # Aba 1: Tabela de Nós Encontrados
        cols = [
            Column("path", "Caminho Normalizado", width=200),
            Column("type", "Tipo", width=80),
            Column("value", "Valor Extraído", width=280),
        ]
        self._table_view = DataTableView(cols, key="path", parent=self)
        self._result_tabs.addTab(self._table_view, "Tabela de Resultados")

        # Aba 2: JSON Bruto dos Resultados
        self._txt_raw_out = QPlainTextEdit()
        self._txt_raw_out.setFont(QFont("Consolas", 9))
        self._txt_raw_out.setReadOnly(True)
        self._result_tabs.addTab(self._txt_raw_out, "JSON Bruto")

        out_layout.addWidget(self._result_tabs)

        btn_copy = QPushButton("Copiar Resultados JSON")
        btn_copy.clicked.connect(self._copy_results)
        out_layout.addWidget(btn_copy)

        splitter.addWidget(out_widget)
        splitter.setSizes([400, 480])

        root_layout.addWidget(splitter)

        # Carrega o exemplo por padrão
        self._load_sample_json()

    def _load_sample_json(self):
        formatted = json.dumps(SAMPLE_JSON, indent=2, ensure_ascii=False)
        self._txt_json.setPlainText(formatted)
        self._run_query()

    def _format_json(self):
        raw = self._txt_json.toPlainText().strip()
        if not raw:
            return
        try:
            data = json.loads(raw)
            self._txt_json.setPlainText(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as exc:
            QMessageBox.warning(self, "JSON Inválido", f"Não foi possível formatar o JSON: {exc}")

    def _on_preset_selected(self, index: int):
        expr = self._combo_presets.currentData()
        if expr:
            self._txt_expr.setText(expr)
            self._run_query()

    def _run_query(self):
        raw_json = self._txt_json.toPlainText().strip()
        expr = self._txt_expr.text().strip()

        if not raw_json:
            self._lbl_status.setText("Insira um JSON válido para consultar.")
            return

        try:
            parsed_data = json.loads(raw_json)
        except Exception as exc:
            self._lbl_status.setText("Erro de sintaxe no JSON de entrada.")
            self._txt_raw_out.setPlainText(f"JSON inválido: {exc}")
            self._table_view.set_records([])
            return

        t0 = time.perf_counter()
        matches = query_jsonpath(parsed_data, expr)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        records = [m.to_dict() for m in matches]
        self._table_view.set_records(records)

        # Saída bruta
        raw_values = [m.raw_value for m in matches]
        self._txt_raw_out.setPlainText(json.dumps(raw_values, indent=2, ensure_ascii=False))

        self._lbl_status.setText(f"{len(matches)} nó(s) encontrado(s) em {elapsed_ms:.1f} ms.")

    def _copy_results(self):
        txt = self._txt_raw_out.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)
