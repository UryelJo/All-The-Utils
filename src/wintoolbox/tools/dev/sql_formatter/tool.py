"""
Interface gráfica da ferramenta Formatador e Minificador SQL (dev.sql_formatter).
Permite embelezar consultas com indentação, maiúsculas automáticas em palavras-chave e minificação para código.
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
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.sql_formatter.logic import (
    format_sql,
    minify_sql,
)


@register
class SqlFormatterTool(Tool):
    id = "dev.sql_formatter"
    name = "Formatador e Embelezador SQL"
    category = "Desenvolvimento"
    description = (
        "Formata, embeleza e minifica consultas e scripts SQL (SELECT, JOIN, WHERE, GROUP BY, INSERT), "
        "com palavras-chave em maiúsculas e preservação de comentários e literais."
    )
    keywords = ["sql", "formatar", "embelezar", "beautify", "minify", "query", "banco de dados", "queries"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return SqlFormatterView(self, parent)


class SqlFormatterView(QWidget):
    def __init__(self, tool: SqlFormatterTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937;")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        root_layout.addWidget(lbl_desc)

        # Barra de Opções
        opts_bar = QHBoxLayout()
        self._chk_upper = QCheckBox("Palavras-chave em MAIÚSCULAS")
        self._chk_upper.setChecked(True)
        opts_bar.addWidget(self._chk_upper)

        opts_bar.addWidget(QLabel("Indentação:"))
        self._combo_indent = QComboBox()
        self._combo_indent.addItem("2 espaços", 2)
        self._combo_indent.addItem("4 espaços", 4)
        opts_bar.addWidget(self._combo_indent)

        opts_bar.addStretch()

        btn_sample = QPushButton("Carregar Exemplo SQL")
        btn_sample.clicked.connect(self._load_sample)
        opts_bar.addWidget(btn_sample)

        root_layout.addLayout(opts_bar)

        # Splitter Vertical: Entrada em cima, Saída embaixo
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Painel Entrada
        in_group = QGroupBox("Consulta SQL Bruta")
        in_layout = QVBoxLayout(in_group)
        self._txt_in = QPlainTextEdit()
        self._txt_in.setFont(QFont("Consolas", 10))
        self._txt_in.setPlaceholderText("Cole ou digite sua consulta SQL aqui...")
        in_layout.addWidget(self._txt_in)
        splitter.addWidget(in_group)

        # Painel Saída
        out_group = QGroupBox("Consulta Formatada / Minificada")
        out_layout = QVBoxLayout(out_group)
        self._txt_out = QPlainTextEdit()
        self._txt_out.setFont(QFont("Consolas", 10))
        self._txt_out.setReadOnly(True)
        out_layout.addWidget(self._txt_out)
        splitter.addWidget(out_group)

        splitter.setSizes([200, 260])
        root_layout.addWidget(splitter)

        # Barra de Ações Inferior
        act_bar = QHBoxLayout()
        btn_format = QPushButton("Formatar SQL")
        btn_format.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        btn_format.clicked.connect(self._run_format)
        act_bar.addWidget(btn_format)

        btn_minify = QPushButton("Minificar SQL")
        btn_minify.clicked.connect(self._run_minify)
        act_bar.addWidget(btn_minify)

        btn_copy = QPushButton("Copiar Resultado")
        btn_copy.clicked.connect(self._copy_result)
        act_bar.addWidget(btn_copy)

        act_bar.addStretch()
        self._lbl_status = QLabel("Pronto")
        self._lbl_status.setStyleSheet("color: #4b5563; font-size: 11px;")
        act_bar.addWidget(self._lbl_status)

        root_layout.addLayout(act_bar)

    def _run_format(self):
        raw = self._txt_in.toPlainText()
        upper = self._chk_upper.isChecked()
        indent = self._combo_indent.currentData()
        res = format_sql(raw, uppercase_keywords=upper, indent_spaces=indent)
        self._txt_out.setPlainText(res)
        self._lbl_status.setText(f"{len(res.splitlines())} linha(s) formatadas.")

    def _run_minify(self):
        raw = self._txt_in.toPlainText()
        res = minify_sql(raw)
        self._txt_out.setPlainText(res)
        self._lbl_status.setText(f"Minificado: {len(res)} caracteres.")

    def _load_sample(self):
        sample = (
            "select u.id, u.nome, p.descricao, p.preco "
            "from usuarios u inner join pedidos p on u.id = p.usuario_id "
            "where p.valor > 100 and p.status = 'pago' "
            "order by p.data desc limit 10;"
        )
        self._txt_in.setPlainText(sample)
        self._run_format()

    def _copy_result(self):
        txt = self._txt_out.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)
            self._lbl_status.setText("Copiado para a área de transferência!")
