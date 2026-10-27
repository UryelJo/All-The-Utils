"""
Interface gráfica Fluent para o Comparador Estrutural de Dados (JSON, YAML, TOML).
"""
import json
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.data.struct_diff.logic import (
    diff_structures,
    parse_structured_data,
    summarize_diffs,
)


@register
class StructDiffTool(Tool):
    id = "data.struct_diff"
    name = "Comparador Estrutural (JSON/YAML/TOML)"
    description = "Compara semanticamente estruturas de dados detectando adições, exclusões e alterações semânticas."
    category = "Dados e Estruturas"
    icon = "Diff"
    tags = ["diff", "json", "yaml", "toml", "comparador", "estruturas", "dados"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Barra Superior
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        top_bar.addWidget(QLabel("Formato A:"))
        self.combo_fmt_a = QComboBox()
        self.combo_fmt_a.addItems(["Auto", "JSON", "YAML", "TOML"])
        top_bar.addWidget(self.combo_fmt_a)

        top_bar.addWidget(QLabel("Formato B:"))
        self.combo_fmt_b = QComboBox()
        self.combo_fmt_b.addItems(["Auto", "JSON", "YAML", "TOML"])
        top_bar.addWidget(self.combo_fmt_b)

        btn_sample = QPushButton("Carregar Exemplo")
        btn_compare = QPushButton("Comparar Estruturas")
        btn_compare.setStyleSheet("font-weight: bold;")

        top_bar.addWidget(btn_sample)
        top_bar.addWidget(btn_compare)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        self.lbl_status = QLabel("Cole dois documentos para comparar suas estruturas ignorando formatações.")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Splitter Vertical: Editores de Texto em cima, Tabela de Diferenças embaixo
        v_splitter = QSplitter(Qt.Orientation.Vertical)

        # Splitter Horizontal: Editor A e Editor B
        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Editor A
        w_a = QWidget()
        lay_a = QVBoxLayout(w_a)
        lay_a.setContentsMargins(0, 0, 0, 0)
        lay_a.addWidget(QLabel("Documento A (Original):"))
        self.text_a = QPlainTextEdit()
        self.text_a.setPlaceholderText("Cole o primeiro documento JSON, YAML ou TOML aqui...")
        lay_a.addWidget(self.text_a)
        h_splitter.addWidget(w_a)

        # Editor B
        w_b = QWidget()
        lay_b = QVBoxLayout(w_b)
        lay_b.setContentsMargins(0, 0, 0, 0)
        lay_b.addWidget(QLabel("Documento B (Modificado):"))
        self.text_b = QPlainTextEdit()
        self.text_b.setPlaceholderText("Cole o segundo documento JSON, YAML ou TOML aqui...")
        lay_b.addWidget(self.text_b)
        h_splitter.addWidget(w_b)

        v_splitter.addWidget(h_splitter)

        # Tabela de Resultados
        results_widget = QWidget()
        results_lay = QVBoxLayout(results_widget)
        results_lay.setContentsMargins(0, 0, 0, 0)
        results_lay.setSpacing(6)

        results_lay.addWidget(QLabel("Diferenças Estruturais Encontradas:"))
        self.table_diff = QTableWidget()
        self.table_diff.setColumnCount(5)
        self.table_diff.setHorizontalHeaderLabels(["Tipo", "Caminho Semântico", "Valor Anterior (A)", "Novo Valor (B)", "Detalhes"])
        self.table_diff.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_diff.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_diff.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_diff.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_diff.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        results_lay.addWidget(self.table_diff)

        v_splitter.addWidget(results_widget)
        v_splitter.setSizes([320, 360])

        layout.addWidget(v_splitter, 1)

        # Conexões
        btn_sample.clicked.connect(self._on_load_sample)
        btn_compare.clicked.connect(self._on_compare)

        return container

    def _on_load_sample(self) -> None:
        doc_a = {
            "servidor": "api.producao.com",
            "porta": 443,
            "ssl": True,
            "limites": {
                "max_conexoes": 100,
                "timeout": 30,
            },
            "rotas_ativas": ["/v1/auth", "/v1/usuarios", "/v1/health"],
        }
        # doc_b possui mesma estrutura com ordem de chaves diferente, uma adição, uma alteração e uma remoção
        doc_b = {
            "rotas_ativas": ["/v1/auth", "/v1/usuarios", "/v1/health", "/v2/pagamentos"],
            "porta": 8443,
            "servidor": "api.producao.com",
            "limites": {
                "timeout": 60,
                "tentativas_max": 5,
            },
            "ssl": True,
        }
        self.text_a.setPlainText(json.dumps(doc_a, indent=2))
        self.text_b.setPlainText(json.dumps(doc_b, indent=4))
        self._on_compare()

    def _on_compare(self) -> None:
        raw_a = self.text_a.toPlainText().strip()
        raw_b = self.text_b.toPlainText().strip()

        if not raw_a or not raw_b:
            self.lbl_status.setText("Forneça o conteúdo dos dois documentos para comparar.")
            return

        fmt_a = self.combo_fmt_a.currentText().lower()
        fmt_b = self.combo_fmt_b.currentText().lower()

        ok_a, data_a, err_a = parse_structured_data(raw_a, fmt_a)
        if not ok_a:
            QMessageBox.warning(None, "Erro no Documento A", f"Falha ao decodificar Documento A: {err_a}")
            return

        ok_b, data_b, err_b = parse_structured_data(raw_b, fmt_b)
        if not ok_b:
            QMessageBox.warning(None, "Erro no Documento B", f"Falha ao decodificar Documento B: {err_b}")
            return

        diffs = diff_structures(data_a, data_b)
        summary = summarize_diffs(diffs)

        self.table_diff.clearContents()
        self.table_diff.setRowCount(len(diffs))

        for idx, d in enumerate(diffs):
            t = d["type"]
            path = d["path"]
            old_s = json.dumps(d["old_val"], ensure_ascii=False) if isinstance(d["old_val"], (dict, list)) else str(d["old_val"])
            new_s = json.dumps(d["new_val"], ensure_ascii=False) if isinstance(d["new_val"], (dict, list)) else str(d["new_val"])
            detail = d.get("detail", "")

            item_type = QTableWidgetItem(f"+ Adicionado" if t == "added" else ("- Removido" if t == "removed" else "~ Modificado"))
            item_path = QTableWidgetItem(path)
            item_old = QTableWidgetItem(old_s if t != "added" else "—")
            item_new = QTableWidgetItem(new_s if t != "removed" else "—")
            item_detail = QTableWidgetItem(detail)

            # Estilo por cor
            if t == "added":
                item_type.setForeground(QColor("#2e7d32"))
            elif t == "removed":
                item_type.setForeground(QColor("#c62828"))
            else:
                item_type.setForeground(QColor("#ef6c00"))

            self.table_diff.setItem(idx, 0, item_type)
            self.table_diff.setItem(idx, 1, item_path)
            self.table_diff.setItem(idx, 2, item_old)
            self.table_diff.setItem(idx, 3, item_new)
            self.table_diff.setItem(idx, 4, item_detail)

        if summary["is_identical"]:
            self.lbl_status.setText("✅ Estruturas semânticas idênticas! Nenhuma alteração detectada.")
        else:
            self.lbl_status.setText(
                f"Comparação concluída: {summary['total_diffs']} diferença(s) — "
                f"{summary['added']} adições, {summary['removed']} remoções, {summary['modified']} modificações."
            )
