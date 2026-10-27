"""
Interface de usuário para o Comparador de Combustíveis (Etanol vs. Gasolina) e Custo de Viagem.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.fuel.logic import (
    calculate_fuel_advantage,
    calculate_trip_cost,
)


def fmt_reais(val: float) -> str:
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@register
class FuelCalcTool(Tool):
    """Comparador de abastecimento Etanol vs. Gasolina e estimador de custos de viagem."""

    id = "calc.fuel"
    name = "Calculadora de Combustível (Etanol vs. Gasolina)"
    description = "Descubra qual combustível é mais econômico para seu carro e calcule os custos totais e rateio de viagens."
    category = "Calculadoras"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Cabeçalho
        title = QLabel("Calculadora de Combustíveis & Custos de Viagem")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Economize na bomba comparando a paridade real do seu veículo e faça a projeção financeira de suas viagens."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        tabs.addTab(self._build_compare_tab(), "Etanol vs. Gasolina")
        tabs.addTab(self._build_trip_tab(), "Estimador de Custo de Viagem")

        return widget

    # -------------------------------------------------------------
    # ABA ETANOL VS GASOLINA
    # -------------------------------------------------------------
    def _build_compare_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        form_frame = QFrame()
        form_frame.setFixedWidth(340)
        v_form = QVBoxLayout(form_frame)
        v_form.setSpacing(10)

        f_layout = QFormLayout()

        self.spn_preco_etanol = QDoubleSpinBox()
        self.spn_preco_etanol.setRange(0.01, 20.0)
        self.spn_preco_etanol.setPrefix("R$ ")
        self.spn_preco_etanol.setValue(3.89)
        self.spn_preco_etanol.setDecimals(2)
        self.spn_preco_etanol.valueChanged.connect(self._recalc_fuel)
        f_layout.addRow("Preço do Etanol (Litro):", self.spn_preco_etanol)

        self.spn_preco_gasolina = QDoubleSpinBox()
        self.spn_preco_gasolina.setRange(0.01, 20.0)
        self.spn_preco_gasolina.setPrefix("R$ ")
        self.spn_preco_gasolina.setValue(5.89)
        self.spn_preco_gasolina.setDecimals(2)
        self.spn_preco_gasolina.valueChanged.connect(self._recalc_fuel)
        f_layout.addRow("Preço da Gasolina (Litro):", self.spn_preco_gasolina)

        self.spn_fator = QDoubleSpinBox()
        self.spn_fator.setRange(50.0, 90.0)
        self.spn_fator.setSuffix(" %")
        self.spn_fator.setValue(70.0)
        self.spn_fator.setDecimals(1)
        self.spn_fator.valueChanged.connect(self._recalc_fuel)
        f_layout.addRow("Fator de Eficiência do Carro:", self.spn_fator)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        layout.addWidget(form_frame)

        # Painel de Resultado
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        card_rec = QFrame()
        card_rec.setStyleSheet("background-color: rgba(2, 132, 199, 0.15); border-radius: 6px; padding: 12px;")
        v_rec = QVBoxLayout(card_rec)
        v_rec.addWidget(QLabel("RECOMENDAÇÃO ECONÔMICA:"))
        self.lbl_recomendacao = QLabel("Abasteça com ETANOL")
        self.lbl_recomendacao.setStyleSheet("font-size: 20px; font-weight: bold; color: #0284c7;")
        self.lbl_recomendacao.setWordWrap(True)
        v_rec.addWidget(self.lbl_recomendacao)
        v_res.addWidget(card_rec)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Relação de Preço (Etanol / Gasolina):"), 0, 0)
        self.lbl_relacao = QLabel("66.04%")
        self.lbl_relacao.setStyleSheet("font-size: 16px; font-weight: bold;")
        grid.addWidget(self.lbl_relacao, 0, 1)

        grid.addWidget(QLabel("Preço Máximo do Etanol para Compensar:"), 1, 0)
        self.lbl_limite_etanol = QLabel("R$ 4,12")
        self.lbl_limite_etanol.setStyleSheet("font-size: 16px; font-weight: bold; color: #16a34a;")
        grid.addWidget(self.lbl_limite_etanol, 1, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_fuel()
        return page

    def _recalc_fuel(self) -> None:
        et = self.spn_preco_etanol.value()
        gas = self.spn_preco_gasolina.value()
        fator = self.spn_fator.value() / 100.0

        res = calculate_fuel_advantage(et, gas, fator)
        self.lbl_recomendacao.setText(res["recomendacao"])
        self.lbl_relacao.setText(f"{res['relacao_percentual']:.2f}%")
        self.lbl_limite_etanol.setText(fmt_reais(res["preco_limite_etanol"]))

        if res["vantagem_etanol"]:
            self.lbl_recomendacao.setStyleSheet("font-size: 20px; font-weight: bold; color: #16a34a;")
        else:
            self.lbl_recomendacao.setStyleSheet("font-size: 20px; font-weight: bold; color: #0284c7;")

    # -------------------------------------------------------------
    # ABA ESTIMADOR DE CUSTO DE VIAGEM
    # -------------------------------------------------------------
    def _build_trip_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        form_frame = QFrame()
        form_frame.setFixedWidth(340)
        v_form = QVBoxLayout(form_frame)
        f_layout = QFormLayout()

        self.spn_distancia = QDoubleSpinBox()
        self.spn_distancia.setRange(1.0, 50000.0)
        self.spn_distancia.setValue(450.0)
        self.spn_distancia.setSuffix(" km")
        self.spn_distancia.valueChanged.connect(self._recalc_trip)
        f_layout.addRow("Distância Total (Ida ou Ida/Volta):", self.spn_distancia)

        self.spn_consumo = QDoubleSpinBox()
        self.spn_consumo.setRange(1.0, 50.0)
        self.spn_consumo.setValue(12.5)
        self.spn_consumo.setSuffix(" km/l")
        self.spn_consumo.valueChanged.connect(self._recalc_trip)
        f_layout.addRow("Consumo Médio do Carro:", self.spn_consumo)

        self.spn_preco_litro = QDoubleSpinBox()
        self.spn_preco_litro.setRange(0.01, 20.0)
        self.spn_preco_litro.setPrefix("R$ ")
        self.spn_preco_litro.setValue(5.89)
        self.spn_preco_litro.valueChanged.connect(self._recalc_trip)
        f_layout.addRow("Preço do Combustível (Litro):", self.spn_preco_litro)

        self.spn_pedagios = QDoubleSpinBox()
        self.spn_pedagios.setRange(0.0, 2000.0)
        self.spn_pedagios.setPrefix("R$ ")
        self.spn_pedagios.setValue(65.0)
        self.spn_pedagios.valueChanged.connect(self._recalc_trip)
        f_layout.addRow("Total Estimado de Pedágios:", self.spn_pedagios)

        self.spn_passageiros = QSpinBox()
        self.spn_passageiros.setRange(1, 15)
        self.spn_passageiros.setValue(2)
        self.spn_passageiros.valueChanged.connect(self._recalc_trip)
        f_layout.addRow("Número de Passageiros (Rateio):", self.spn_passageiros)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        layout.addWidget(form_frame)

        # Resultados de viagem
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        card_tot = QFrame()
        card_tot.setStyleSheet("background-color: rgba(22, 163, 74, 0.15); border-radius: 6px; padding: 12px;")
        v_tot = QVBoxLayout(card_tot)
        v_tot.addWidget(QLabel("CUSTO TOTAL DA VIAGEM:"))
        self.lbl_trip_total = QLabel("R$ 0,00")
        self.lbl_trip_total.setStyleSheet("font-size: 26px; font-weight: bold; color: #16a34a;")
        v_tot.addWidget(self.lbl_trip_total)
        v_res.addWidget(card_tot)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Combustível Necessário:"), 0, 0)
        self.lbl_trip_litros = QLabel("0,0 Litros")
        grid.addWidget(self.lbl_trip_litros, 0, 1)

        grid.addWidget(QLabel("Gasto com Combustível:"), 1, 0)
        self.lbl_trip_comb = QLabel("R$ 0,00")
        grid.addWidget(self.lbl_trip_comb, 1, 1)

        grid.addWidget(QLabel("Custo por Quilômetro Rodado:"), 2, 0)
        self.lbl_trip_km = QLabel("R$ 0,00 / km")
        grid.addWidget(self.lbl_trip_km, 2, 1)

        grid.addWidget(QLabel("Valor por Passageiro (Rateio):"), 3, 0)
        self.lbl_trip_pass = QLabel("R$ 0,00")
        self.lbl_trip_pass.setStyleSheet("font-size: 18px; font-weight: bold; color: #0284c7;")
        grid.addWidget(self.lbl_trip_pass, 3, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_trip()
        return page

    def _recalc_trip(self) -> None:
        dist = self.spn_distancia.value()
        cons = self.spn_consumo.value()
        preco = self.spn_preco_litro.value()
        ped = self.spn_pedagios.value()
        passag = self.spn_passageiros.value()

        res = calculate_trip_cost(dist, cons, preco, ped, passag)
        self.lbl_trip_total.setText(fmt_reais(res["custo_total"]))
        self.lbl_trip_litros.setText(f"{res['litros_necessarios']:.1f} Litros")
        self.lbl_trip_comb.setText(fmt_reais(res["custo_combustivel"]))
        self.lbl_trip_km.setText(f"{fmt_reais(res['custo_por_km'])} / km")
        self.lbl_trip_pass.setText(fmt_reais(res["custo_por_passageiro"]))
