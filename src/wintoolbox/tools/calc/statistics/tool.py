"""
Interface de usuário para a Calculadora de Estatística Descritiva e Regressão Linear.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.statistics.logic import (
    calculate_descriptive_statistics,
    calculate_linear_regression,
    parse_numeric_dataset,
)


@register
class StatisticsTool(Tool):
    """Calculadora de estatística descritiva e regressão linear simples."""

    id = "calc.statistics"
    name = "Calculadora Estatística (Descritiva & Regressão)"
    description = "Analise conjuntos de dados com média, mediana, desvio padrão, variância, quartis e regressão linear simples."
    category = "calc"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        title = QLabel("Calculadora Estatística & Análise de Dados")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Análise quantitativa completa de dados numéricos com medidas de tendência central, dispersão e modelagem linear."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        tabs.addTab(self._build_descriptive_tab(), "Estatística Descritiva")
        tabs.addTab(self._build_regression_tab(), "Regressão Linear Simples")

        return widget

    # -------------------------------------------------------------
    # ABA ESTATÍSTICA DESCRITIVA
    # -------------------------------------------------------------
    def _build_descriptive_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        # Lado Esquerdo: Entrada de dados
        left_box = QWidget()
        left_box.setFixedWidth(340)
        v_left = QVBoxLayout(left_box)
        v_left.setSpacing(8)

        v_left.addWidget(QLabel("<b>Conjunto de Dados (Valores):</b>"))
        self.txt_data = QTextEdit()
        self.txt_data.setPlaceholderText("Cole seus números aqui...\nEx: 12, 15.5, 18, 22, 25, 30\n(separados por vírgula, espaço ou linha)")
        self.txt_data.setPlainText("14.5, 18.2, 22.0, 19.8, 25.4, 21.3, 17.6, 29.1, 23.5, 20.0, 18.2")
        self.txt_data.textChanged.connect(self._recalc_descriptive)
        v_left.addWidget(self.txt_data, 1)

        btn_box = QHBoxLayout()
        btn_sample = QPushButton("Carregar Exemplo")
        btn_sample.clicked.connect(self._load_sample_data)
        btn_clear = QPushButton("Limpar")
        btn_clear.clicked.connect(self.txt_data.clear)
        btn_box.addWidget(btn_sample)
        btn_box.addWidget(btn_clear)
        v_left.addLayout(btn_box)

        layout.addWidget(left_box)

        # Lado Direito: Tabela de Métricas
        right_box = QWidget()
        v_right = QVBoxLayout(right_box)
        v_right.setSpacing(8)

        v_right.addWidget(QLabel("<b>Métricas Calculadas:</b>"))
        self.tbl_metrics = QTableWidget(0, 2)
        self.tbl_metrics.setHorizontalHeaderLabels(["Parâmetro Estatístico", "Valor Calculado"])
        self.tbl_metrics.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_metrics.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.tbl_metrics.setColumnWidth(1, 160)
        self.tbl_metrics.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_metrics.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v_right.addWidget(self.tbl_metrics, 1)

        layout.addWidget(right_box, 1)

        self._recalc_descriptive()
        return page

    def _load_sample_data(self) -> None:
        self.txt_data.setPlainText("10, 12, 12, 14, 15, 17, 18, 18, 19, 20, 22, 25, 28, 30, 35")

    def _recalc_descriptive(self) -> None:
        raw = self.txt_data.toPlainText()
        numbers = parse_numeric_dataset(raw)

        if not numbers:
            self.tbl_metrics.setRowCount(0)
            return

        res = calculate_descriptive_statistics(numbers)

        metrics = [
            ("Número de Amostras (n)", f"{res['count']}"),
            ("Soma Total (Σx)", f"{res['sum']:g}"),
            ("Média Aritmética (x̄)", f"{res['mean']}"),
            ("Mediana (Q2)", f"{res['median']}"),
            ("Moda", f"{res['mode']}"),
            ("Valor Mínimo (Mín)", f"{res['min']:g}"),
            ("Valor Máximo (Máx)", f"{res['max']:g}"),
            ("Amplitude Total (Range)", f"{res['range']}"),
            ("Variância Amostral (s²)", f"{res['var_sample']}"),
            ("Desvio Padrão Amostral (s)", f"{res['stdev_sample']}"),
            ("Erro Padrão da Média (SE)", f"{res['std_error']}"),
            ("Variância Populacional (σ²)", f"{res['var_pop']}"),
            ("Desvio Padrão Populacional (σ)", f"{res['stdev_pop']}"),
            ("Primeiro Quartil (Q1 - 25%)", f"{res['q1']}"),
            ("Terceiro Quartil (Q3 - 75%)", f"{res['q3']}"),
            ("Intervalo Interquartil (IQR)", f"{res['iqr']}"),
        ]

        self.tbl_metrics.setRowCount(len(metrics))
        for r, (label, val) in enumerate(metrics):
            it_l = QTableWidgetItem(label)
            it_v = QTableWidgetItem(val)
            it_v.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_metrics.setItem(r, 0, it_l)
            self.tbl_metrics.setItem(r, 1, it_v)

    # -------------------------------------------------------------
    # ABA REGRESSÃO LINEAR
    # -------------------------------------------------------------
    def _build_regression_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        form_frame = QFrame()
        form_frame.setFixedWidth(360)
        v_form = QVBoxLayout(form_frame)
        v_form.setSpacing(10)

        v_form.addWidget(QLabel("<b>Valores da Variável Independente (X):</b>"))
        self.txt_reg_x = QTextEdit("1, 2, 3, 4, 5, 6, 7, 8")
        self.txt_reg_x.setMaximumHeight(90)
        self.txt_reg_x.textChanged.connect(self._recalc_regression)
        v_form.addWidget(self.txt_reg_x)

        v_form.addWidget(QLabel("<b>Valores da Variável Dependente (Y):</b>"))
        self.txt_reg_y = QTextEdit("2.5, 4.8, 6.2, 8.5, 10.1, 12.3, 14.0, 16.2")
        self.txt_reg_y.setMaximumHeight(90)
        self.txt_reg_y.textChanged.connect(self._recalc_regression)
        v_form.addWidget(self.txt_reg_y)

        v_form.addStretch()
        layout.addWidget(form_frame)

        # Resultados de Regressão
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        card_eq = QFrame()
        card_eq.setStyleSheet("background-color: rgba(2, 132, 199, 0.15); border-radius: 6px; padding: 12px;")
        v_eq = QVBoxLayout(card_eq)
        v_eq.addWidget(QLabel("EQUAÇÃO DA RETA DE REGRESSÃO:"))
        self.lbl_equacao = QLabel("y = mx + b")
        self.lbl_equacao.setStyleSheet("font-size: 22px; font-weight: bold; color: #0284c7;")
        v_eq.addWidget(self.lbl_equacao)
        v_res.addWidget(card_eq)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Coeficiente de Determinação (R²):"), 0, 0)
        self.lbl_r2 = QLabel("0.998")
        self.lbl_r2.setStyleSheet("font-size: 16px; font-weight: bold; color: #16a34a;")
        grid.addWidget(self.lbl_r2, 0, 1)

        grid.addWidget(QLabel("Coeficiente de Correlação de Pearson (r):"), 1, 0)
        self.lbl_r = QLabel("0.999")
        self.lbl_r.setStyleSheet("font-size: 16px; font-weight: bold;")
        grid.addWidget(self.lbl_r, 1, 1)

        grid.addWidget(QLabel("Inclinação da Reta (Slope / m):"), 2, 0)
        self.lbl_slope = QLabel("0.0")
        grid.addWidget(self.lbl_slope, 2, 1)

        grid.addWidget(QLabel("Intercepto Y (b):"), 3, 0)
        self.lbl_intercept = QLabel("0.0")
        grid.addWidget(self.lbl_intercept, 3, 1)

        grid.addWidget(QLabel("Número de Pares de Dados (n):"), 4, 0)
        self.lbl_reg_n = QLabel("0")
        grid.addWidget(self.lbl_reg_n, 4, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_regression()
        return page

    def _recalc_regression(self) -> None:
        x_vals = parse_numeric_dataset(self.txt_reg_x.toPlainText())
        y_vals = parse_numeric_dataset(self.txt_reg_y.toPlainText())

        res = calculate_linear_regression(x_vals, y_vals)
        if "error" in res:
            self.lbl_equacao.setText(res["error"])
            self.lbl_r2.setText("-")
            self.lbl_r.setText("-")
            self.lbl_slope.setText("-")
            self.lbl_intercept.setText("-")
            self.lbl_reg_n.setText("-")
            return

        self.lbl_equacao.setText(res["equation"])
        self.lbl_r2.setText(f"{res['r_squared']:.4f}")
        self.lbl_r.setText(f"{res['correlation_r']:.4f}")
        self.lbl_slope.setText(f"{res['slope']:.6f}")
        self.lbl_intercept.setText(f"{res['intercept']:.6f}")
        self.lbl_reg_n.setText(f"{res['n']}")
