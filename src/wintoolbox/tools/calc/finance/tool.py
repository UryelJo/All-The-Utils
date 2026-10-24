"""
Interface gráfica da Calculadora Financeira (Juros Compostos, Financiamentos e Margens).
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.finance.logic import (
    calculate_compound_interest, calculate_financing, calculate_margin_and_markup
)
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("calc.finance.ui")


@register
class FinanceTool(Tool):
    id = "calc.finance"
    name = "Calculadora Financeira"
    category = "Calculadoras"
    description = "Simulações de juros compostos com aportes, financiamentos (Price e SAC) e margem/markup"
    keywords = ["financeiro", "juros", "compostos", "investimento", "financiamento", "price", "sac", "markup", "margem", "dinheiro"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return FinanceView(self, parent)


class FinanceView(QWidget):
    def __init__(self, tool: FinanceTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Calculadora Financeira",
            "Simulação de investimentos de longo prazo, cálculos de amortização de financiamentos e precificação comercial."
        ))

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_compound_tab(), "Juros Compostos")
        self.tabs.addTab(self._build_financing_tab(), "Financiamentos (Price/SAC)")
        self.tabs.addTab(self._build_margin_tab(), "Margem e Markup")
        root.addWidget(self.tabs, stretch=1)

    # 1. Juros Compostos
    def _build_compound_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        input_box = QGroupBox("Parâmetros do Investimento")
        grid = QGridLayout(input_box)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Aporte Inicial (R$):"), 0, 0)
        self.spin_initial = QDoubleSpinBox()
        self.spin_initial.setRange(0, 1e9)
        self.spin_initial.setValue(5000.0)
        self.spin_initial.valueChanged.connect(self._calculate_compound)
        grid.addWidget(self.spin_initial, 0, 1)

        grid.addWidget(QLabel("Aporte Mensal (R$):"), 0, 2)
        self.spin_monthly = QDoubleSpinBox()
        self.spin_monthly.setRange(0, 1e8)
        self.spin_monthly.setValue(500.0)
        self.spin_monthly.valueChanged.connect(self._calculate_compound)
        grid.addWidget(self.spin_monthly, 0, 3)

        grid.addWidget(QLabel("Taxa de Juros Anual (% ao ano):"), 1, 0)
        self.spin_rate = QDoubleSpinBox()
        self.spin_rate.setRange(0, 500)
        self.spin_rate.setValue(11.5)
        self.spin_rate.setDecimals(2)
        self.spin_rate.valueChanged.connect(self._calculate_compound)
        grid.addWidget(self.spin_rate, 1, 1)

        grid.addWidget(QLabel("Período (Anos):"), 1, 2)
        self.spin_years = QSpinBox()
        self.spin_years.setRange(1, 50)
        self.spin_years.setValue(10)
        self.spin_years.valueChanged.connect(self._calculate_compound)
        grid.addWidget(self.spin_years, 1, 3)

        layout.addWidget(input_box)

        # Resultados Cards
        res_frame = QFrame()
        res_frame.setProperty("class", "card")
        res_frame.setStyleSheet("QFrame { border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 12px; }")
        res_grid = QGridLayout(res_frame)
        res_grid.setSpacing(12)

        self.lbl_comp_invested = QLabel("Total Investido: R$ 0,00")
        self.lbl_comp_invested.setFont(QFont("Segoe UI", 11))
        res_grid.addWidget(self.lbl_comp_invested, 0, 0)

        self.lbl_comp_interest = QLabel("Total em Juros: R$ 0,00")
        self.lbl_comp_interest.setFont(QFont("Segoe UI", 11))
        res_grid.addWidget(self.lbl_comp_interest, 0, 1)

        self.lbl_comp_final = QLabel("Saldo Final Bruto: R$ 0,00")
        self.lbl_comp_final.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.lbl_comp_final.setStyleSheet("color: #10B981;")
        res_grid.addWidget(self.lbl_comp_final, 1, 0, 1, 2)

        layout.addWidget(res_frame)

        # Tabela Histórico
        self.table_compound = QTableWidget()
        self.table_compound.setColumnCount(4)
        self.table_compound.setHorizontalHeaderLabels(["Ano", "Total Investido", "Juros Acumulados", "Saldo Total"])
        self.table_compound.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_compound, stretch=1)

        self._calculate_compound()
        return tab

    def _calculate_compound(self) -> None:
        p = self.spin_initial.value()
        pmt = self.spin_monthly.value()
        rate = self.spin_rate.value()
        months = self.spin_years.value() * 12

        res = calculate_compound_interest(p, pmt, rate, months)

        self.lbl_comp_invested.setText(f"Total Investido: R$ {res['total_invested']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_comp_interest.setText(f"Total em Juros: R$ {res['total_interest']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_comp_final.setText(f"Saldo Final Bruto: R$ {res['final_balance']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        history = res["history"]
        self.table_compound.setRowCount(len(history))
        for row, h in enumerate(history):
            self.table_compound.setItem(row, 0, QTableWidgetItem(f"Ano {h['year']}"))
            self.table_compound.setItem(row, 1, QTableWidgetItem(f"R$ {h['invested']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")))
            self.table_compound.setItem(row, 2, QTableWidgetItem(f"R$ {h['total_interest']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")))
            self.table_compound.setItem(row, 3, QTableWidgetItem(f"R$ {h['balance']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")))

    # 2. Financiamentos
    def _build_financing_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        input_box = QGroupBox("Parâmetros do Financiamento")
        grid = QGridLayout(input_box)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Valor do Financiamento (R$):"), 0, 0)
        self.spin_fin_amount = QDoubleSpinBox()
        self.spin_fin_amount.setRange(100, 1e9)
        self.spin_fin_amount.setValue(250000.0)
        self.spin_fin_amount.valueChanged.connect(self._calculate_financing)
        grid.addWidget(self.spin_fin_amount, 0, 1)

        grid.addWidget(QLabel("Taxa de Juros Anual (% ao ano):"), 0, 2)
        self.spin_fin_rate = QDoubleSpinBox()
        self.spin_fin_rate.setRange(0.1, 100)
        self.spin_fin_rate.setValue(9.5)
        self.spin_fin_rate.valueChanged.connect(self._calculate_financing)
        grid.addWidget(self.spin_fin_rate, 0, 3)

        grid.addWidget(QLabel("Prazo Total (Meses):"), 1, 0)
        self.spin_fin_months = QSpinBox()
        self.spin_fin_months.setRange(1, 480)
        self.spin_fin_months.setValue(240)
        self.spin_fin_months.valueChanged.connect(self._calculate_financing)
        grid.addWidget(self.spin_fin_months, 1, 1)

        grid.addWidget(QLabel("Sistema de Amortização:"), 1, 2)
        self.combo_fin_sys = QComboBox()
        self.combo_fin_sys.addItem("Tabela Price (Parcelas Fixas)", "PRICE")
        self.combo_fin_sys.addItem("Tabela SAC (Parcelas Decrescentes)", "SAC")
        self.combo_fin_sys.currentIndexChanged.connect(self._calculate_financing)
        grid.addWidget(self.combo_fin_sys, 1, 3)

        layout.addWidget(input_box)

        # Resultados
        res_frame = QFrame()
        res_frame.setProperty("class", "card")
        res_frame.setStyleSheet("QFrame { border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 12px; }")
        res_grid = QGridLayout(res_frame)
        res_grid.setSpacing(10)

        self.lbl_fin_first = QLabel("Primeira Parcela: R$ 0,00")
        self.lbl_fin_first.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        res_grid.addWidget(self.lbl_fin_first, 0, 0)

        self.lbl_fin_last = QLabel("Última Parcela: R$ 0,00")
        self.lbl_fin_last.setFont(QFont("Segoe UI", 11))
        res_grid.addWidget(self.lbl_fin_last, 0, 1)

        self.lbl_fin_total = QLabel("Total a Pagar: R$ 0,00")
        self.lbl_fin_total.setFont(QFont("Segoe UI", 11))
        res_grid.addWidget(self.lbl_fin_total, 1, 0)

        self.lbl_fin_interest = QLabel("Total Pago em Juros: R$ 0,00")
        self.lbl_fin_interest.setFont(QFont("Segoe UI", 11))
        res_grid.addWidget(self.lbl_fin_interest, 1, 1)

        layout.addWidget(res_frame)

        # Tabela
        self.table_fin = QTableWidget()
        self.table_fin.setColumnCount(5)
        self.table_fin.setHorizontalHeaderLabels(["Mês", "Parcela", "Amortização", "Juros", "Saldo Devedor"])
        self.table_fin.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_fin, stretch=1)

        self._calculate_financing()
        return tab

    def _calculate_financing(self) -> None:
        pv = self.spin_fin_amount.value()
        rate = self.spin_fin_rate.value()
        months = self.spin_fin_months.value()
        sys_type = self.combo_fin_sys.currentData() or "PRICE"

        res = calculate_financing(pv, rate, months, system=sys_type)
        if "error" in res:
            return

        self.lbl_fin_first.setText(f"Primeira Parcela: R$ {res['first_payment']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_fin_last.setText(f"Última Parcela: R$ {res['last_payment']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_fin_total.setText(f"Total a Pagar: R$ {res['total_paid']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_fin_interest.setText(f"Total Pago em Juros: R$ {res['total_interest']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        sched = res["schedule"]
        self.table_fin.setRowCount(len(sched))
        for row, s in enumerate(sched):
            self.table_fin.setItem(row, 0, QTableWidgetItem(f"Mês {s['month']}"))
            self.table_fin.setItem(row, 1, QTableWidgetItem(f"R$ {s['payment']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")))
            self.table_fin.setItem(row, 2, QTableWidgetItem(f"R$ {s['amortization']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")))
            self.table_fin.setItem(row, 3, QTableWidgetItem(f"R$ {s['interest']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")))
            self.table_fin.setItem(row, 4, QTableWidgetItem(f"R$ {s['balance']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")))

    # 3. Margem e Markup
    def _build_margin_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(12)

        box = QGroupBox("Custo e Venda")
        grid = QGridLayout(box)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Preço de Custo (R$):"), 0, 0)
        self.spin_cost = QDoubleSpinBox()
        self.spin_cost.setRange(0, 1e7)
        self.spin_cost.setValue(50.0)
        self.spin_cost.valueChanged.connect(self._calculate_margin)
        grid.addWidget(self.spin_cost, 0, 1)

        grid.addWidget(QLabel("Preço de Venda (R$):"), 0, 2)
        self.spin_sell = QDoubleSpinBox()
        self.spin_sell.setRange(0, 1e7)
        self.spin_sell.setValue(85.0)
        self.spin_sell.valueChanged.connect(self._calculate_margin)
        grid.addWidget(self.spin_sell, 0, 3)

        layout.addWidget(box)

        res_frame = QFrame()
        res_frame.setProperty("class", "card")
        res_frame.setStyleSheet("QFrame { border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 16px; }")
        res_lay = QVBoxLayout(res_frame)
        res_lay.setSpacing(8)

        self.lbl_margin_profit = QLabel("Lucro Bruto: R$ 35,00")
        self.lbl_margin_profit.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_margin_profit.setStyleSheet("color: #10B981;")
        res_lay.addWidget(self.lbl_margin_profit)

        self.lbl_margin_pct = QLabel("Margem de Lucro (sobre Venda): 41,18%")
        self.lbl_margin_pct.setFont(QFont("Segoe UI", 11))
        res_lay.addWidget(self.lbl_margin_pct)

        self.lbl_markup_pct = QLabel("Markup (sobre Custo): 70,00%")
        self.lbl_markup_pct.setFont(QFont("Segoe UI", 11))
        res_lay.addWidget(self.lbl_markup_pct)

        layout.addWidget(res_frame)
        layout.addStretch(1)

        self._calculate_margin()
        return tab

    def _calculate_margin(self) -> None:
        cost = self.spin_cost.value()
        sell = self.spin_sell.value()
        res = calculate_margin_and_markup(cost, sell)

        self.lbl_margin_profit.setText(f"Lucro Bruto por Unidade: R$ {res['profit']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_margin_pct.setText(f"Margem de Lucro Líquida (sobre Preço de Venda): {res['margin_percent']:.2f}%")
        self.lbl_markup_pct.setText(f"Markup Aplicado (Multiplicador sobre Custo): {res['markup_percent']:.2f}%")
