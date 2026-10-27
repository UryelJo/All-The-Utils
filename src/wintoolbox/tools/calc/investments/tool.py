"""
Interface de usuário para o Simulador Comparativo de Investimentos de Renda Fixa.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.investments.logic import (
    simulate_all_investments,
)


def fmt_reais(val: float) -> str:
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@register
class InvestmentsCalcTool(Tool):
    """Simulador comparativo de investimentos de renda fixa com tabela regressiva de IR."""

    id = "calc.investments"
    name = "Simulador de Investimentos Renda Fixa (CDB, LCI, Poupança, Tesouro)"
    description = "Compare rendimentos líquidos reais de CDB, LCI/LCA, Poupança e Tesouro Direto com alíquotas regressivas do Imposto de Renda."
    category = "Calculadoras"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Cabeçalho
        title = QLabel("Simulador Comparativo de Renda Fixa (CDB vs. LCI vs. Tesouro)")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Cálculo exato de juros compostos e aplicação da tabela regressiva oficial do Imposto de Renda (22,5% a 15,0%)."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        main_box = QHBoxLayout()
        main_box.setSpacing(15)

        # Painel Esquerdo: Parâmetros
        form_frame = QFrame()
        form_frame.setFixedWidth(360)
        v_form = QVBoxLayout(form_frame)
        f_layout = QFormLayout()

        self.spn_init = QDoubleSpinBox()
        self.spn_init.setRange(0.0, 100000000.0)
        self.spn_init.setPrefix("R$ ")
        self.spn_init.setValue(10000.0)
        self.spn_init.valueChanged.connect(self._recalculate)
        f_layout.addRow("Aplicação Inicial:", self.spn_init)

        self.spn_monthly = QDoubleSpinBox()
        self.spn_monthly.setRange(0.0, 1000000.0)
        self.spn_monthly.setPrefix("R$ ")
        self.spn_monthly.setValue(500.0)
        self.spn_monthly.valueChanged.connect(self._recalculate)
        f_layout.addRow("Aporte Mensal:", self.spn_monthly)

        self.spn_months = QSpinBox()
        self.spn_months.setRange(1, 360)
        self.spn_months.setValue(24)
        self.spn_months.setSuffix(" meses (2 anos)")
        self.spn_months.valueChanged.connect(self._on_months_changed)
        f_layout.addRow("Prazo da Aplicação:", self.spn_months)

        self.spn_selic = QDoubleSpinBox()
        self.spn_selic.setRange(1.0, 30.0)
        self.spn_selic.setValue(10.75)
        self.spn_selic.setSuffix(" % a.a.")
        self.spn_selic.valueChanged.connect(self._recalculate)
        f_layout.addRow("Taxa Selic Referência:", self.spn_selic)

        self.spn_cdb = QDoubleSpinBox()
        self.spn_cdb.setRange(50.0, 200.0)
        self.spn_cdb.setValue(105.0)
        self.spn_cdb.setSuffix(" % do CDI")
        self.spn_cdb.valueChanged.connect(self._recalculate)
        f_layout.addRow("Rendimento do CDB:", self.spn_cdb)

        self.spn_lci = QDoubleSpinBox()
        self.spn_lci.setRange(50.0, 150.0)
        self.spn_lci.setValue(90.0)
        self.spn_lci.setSuffix(" % do CDI (Isenta)")
        self.spn_lci.valueChanged.connect(self._recalculate)
        f_layout.addRow("Rendimento da LCI / LCA:", self.spn_lci)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        main_box.addWidget(form_frame)

        # Painel Direito: Resultados e Comparativo
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 12px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(10)

        # Card de Destaque
        card_winner = QFrame()
        card_winner.setStyleSheet("background-color: rgba(22, 163, 74, 0.15); border-radius: 6px; padding: 12px;")
        v_w = QVBoxLayout(card_winner)
        v_w.addWidget(QLabel("MELHOR RENTABILIDADE LÍQUIDA:"))
        self.lbl_winner_title = QLabel("CDB (105% do CDI)")
        self.lbl_winner_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #16a34a;")
        v_w.addWidget(self.lbl_winner_title)
        self.lbl_winner_diff = QLabel("+ R$ 0,00 a mais de lucro do que na poupança")
        self.lbl_winner_diff.setStyleSheet("color: #888888; font-size: 12px;")
        v_w.addWidget(self.lbl_winner_diff)
        v_res.addWidget(card_winner)

        # Tabela Comparativa Completa
        v_res.addWidget(QLabel("<b>Comparativo Detalhado no Vencimento:</b>"))
        self.tbl_compare = QTableWidget(4, 6)
        self.tbl_compare.setHorizontalHeaderLabels([
            "Aplicação", "Taxa Bruta", "Total Investido", "Saldo Bruto", "IR Retido", "Saldo Líquido"
        ])
        self.tbl_compare.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_compare.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_compare.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_compare.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_compare.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_compare.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_compare.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v_res.addWidget(self.tbl_compare, 1)

        main_box.addWidget(res_frame, 1)
        layout.addLayout(main_box, 1)

        self._recalculate()
        return widget

    def _on_months_changed(self) -> None:
        m = self.spn_months.value()
        anos = m / 12.0
        if m % 12 == 0:
            txt = f"{m} meses ({int(anos)} ano{'s' if anos > 1 else ''})"
        else:
            txt = f"{m} meses ({anos:.1f} anos)"
        self.spn_months.setSuffix(f" meses ({txt.split('(')[1]}")
        self._recalculate()

    def _recalculate(self) -> None:
        v_init = self.spn_init.value()
        v_month = self.spn_monthly.value()
        m = self.spn_months.value()
        selic = self.spn_selic.value()
        cdb_p = self.spn_cdb.value()
        lci_p = self.spn_lci.value()

        data = simulate_all_investments(v_init, v_month, m, selic, cdb_p, lci_p)

        keys = ["poupanca", "cdb", "lci_lca", "tesouro_selic"]
        melhor_chave = max(keys, key=lambda k: data[k]["saldo_liquido"])
        melhor = data[melhor_chave]
        poup = data["poupanca"]
        dif = melhor["saldo_liquido"] - poup["saldo_liquido"]

        self.lbl_winner_title.setText(f"{melhor['nome']} → {fmt_reais(melhor['saldo_liquido'])}")
        self.lbl_winner_diff.setText(f"+ {fmt_reais(dif)} a mais no bolso do que deixando na Poupança!")

        for r, k in enumerate(keys):
            row_data = data[k]
            it_name = QTableWidgetItem(row_data["nome"])
            it_taxa = QTableWidgetItem(f"{row_data['taxa_anual']:.2f}% a.a.")
            it_inv = QTableWidgetItem(fmt_reais(row_data["total_investido"]))
            it_bruto = QTableWidgetItem(fmt_reais(row_data["saldo_bruto"]))

            ir_txt = "Isento" if row_data["isento"] else f"{fmt_reais(row_data['valor_ir'])} ({row_data['aliquota_ir']:.1f}%)"
            it_ir = QTableWidgetItem(ir_txt)

            it_liq = QTableWidgetItem(fmt_reais(row_data["saldo_liquido"]))
            it_liq.setForeground(Qt.GlobalColor.darkGreen)

            self.tbl_compare.setItem(r, 0, it_name)
            self.tbl_compare.setItem(r, 1, it_taxa)
            self.tbl_compare.setItem(r, 2, it_inv)
            self.tbl_compare.setItem(r, 3, it_bruto)
            self.tbl_compare.setItem(r, 4, it_ir)
            self.tbl_compare.setItem(r, 5, it_liq)
