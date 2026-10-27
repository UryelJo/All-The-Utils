"""
Interface de usuário para a Calculadora Elétrica, Lei de Ohm e Código de Cores de Resistores.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.electrical.logic import (
    RESISTOR_DIGITS,
    RESISTOR_MULTIPLIERS,
    RESISTOR_TOLERANCES,
    calculate_energy_consumption,
    calculate_ohm_law,
    calculate_resistor_value,
)


def fmt_reais(val: float) -> str:
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


PRESET_APPLIANCES = [
    ("Personalizado", 0),
    ("Chuveiro Elétrico (Potência Máxima)", 5500),
    ("Ar-Condicionado 9.000 BTUs Inverter", 800),
    ("Ar-Condicionado 12.000 BTUs", 1200),
    ("Geladeira Frost-Free Duplex", 150),
    ("Computador / PC Gamer em Carga", 450),
    ("Notebook / Laptop em Trabalho", 65),
    ("Televisor 55 polegadas 4K", 120),
    ("Air Fryer / Fritadeira Elétrica", 1500),
    ("Ferro de Passar Roupas", 1200),
    ("Lâmpada LED Residencial", 10),
]


@register
class ElectricalCalcTool(Tool):
    """Calculadora de consumo de energia, custo de eletricidade, Lei de Ohm e resistores."""

    id = "calc.electrical"
    name = "Calculadora Elétrica Residencial (Consumo, Ohm & Resistores)"
    description = "Estime custos em kWh na conta de luz, resolva circuitos com a Lei de Ohm e decodifique faixas de cores de resistores."
    category = "Calculadoras"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Cabeçalho
        title = QLabel("Calculadora Elétrica & Código de Cores de Resistores")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Cálculo de consumo em kWh na tarifa brasileira, análise de grandezas pela Lei de Ohm e decodificação de resistores."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        tabs.addTab(self._build_energy_tab(), "Consumo & Fatura de Luz")
        tabs.addTab(self._build_ohm_tab(), "Lei de Ohm & Potência")
        tabs.addTab(self._build_resistor_tab(), "Código de Cores de Resistores")

        return widget

    # -------------------------------------------------------------
    # ABA CONSUMO DE ENERGIA
    # -------------------------------------------------------------
    def _build_energy_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        form_frame = QFrame()
        form_frame.setFixedWidth(360)
        v_form = QVBoxLayout(form_frame)
        f_layout = QFormLayout()

        self.cmb_appliance = QComboBox()
        for name, watts in PRESET_APPLIANCES:
            self.cmb_appliance.addItem(name, watts)
        self.cmb_appliance.currentIndexChanged.connect(self._on_preset_appliance_changed)
        f_layout.addRow("Aparelho Sugerido:", self.cmb_appliance)

        self.spn_watts = QDoubleSpinBox()
        self.spn_watts.setRange(1.0, 50000.0)
        self.spn_watts.setValue(800.0)
        self.spn_watts.setSuffix(" Watts")
        self.spn_watts.valueChanged.connect(self._recalc_energy)
        f_layout.addRow("Potência Nominal:", self.spn_watts)

        self.spn_hours_day = QDoubleSpinBox()
        self.spn_hours_day.setRange(0.1, 24.0)
        self.spn_hours_day.setValue(8.0)
        self.spn_hours_day.setSuffix(" horas/dia")
        self.spn_hours_day.valueChanged.connect(self._recalc_energy)
        f_layout.addRow("Tempo de Uso Diário:", self.spn_hours_day)

        self.spn_days_month = QSpinBox()
        self.spn_days_month.setRange(1, 31)
        self.spn_days_month.setValue(30)
        self.spn_days_month.setSuffix(" dias/mês")
        self.spn_days_month.valueChanged.connect(self._recalc_energy)
        f_layout.addRow("Frequência Mensal:", self.spn_days_month)

        self.spn_tarifa = QDoubleSpinBox()
        self.spn_tarifa.setRange(0.10, 5.0)
        self.spn_tarifa.setPrefix("R$ ")
        self.spn_tarifa.setValue(0.85)
        self.spn_tarifa.setSuffix(" / kWh")
        self.spn_tarifa.setDecimals(2)
        self.spn_tarifa.valueChanged.connect(self._recalc_energy)
        f_layout.addRow("Tarifa de Energia (com impostos):", self.spn_tarifa)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        layout.addWidget(form_frame)

        # Resultados de consumo
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        card_cost = QFrame()
        card_cost.setStyleSheet("background-color: rgba(234, 88, 12, 0.15); border-radius: 6px; padding: 12px;")
        v_c = QVBoxLayout(card_cost)
        v_c.addWidget(QLabel("CUSTO MENSAL ESTIMADO:"))
        self.lbl_cost_month = QLabel("R$ 0,00")
        self.lbl_cost_month.setStyleSheet("font-size: 26px; font-weight: bold; color: #ea580c;")
        v_c.addWidget(self.lbl_cost_month)
        v_res.addWidget(card_cost)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Consumo Mensal em Energia:"), 0, 0)
        self.lbl_kwh_month = QLabel("0,00 kWh")
        self.lbl_kwh_month.setStyleSheet("font-size: 16px; font-weight: bold;")
        grid.addWidget(self.lbl_kwh_month, 0, 1)

        grid.addWidget(QLabel("Consumo Diário:"), 1, 0)
        self.lbl_kwh_day = QLabel("0,00 kWh/dia")
        grid.addWidget(self.lbl_kwh_day, 1, 1)

        grid.addWidget(QLabel("Projeção de Custo Anual:"), 2, 0)
        self.lbl_cost_year = QLabel("R$ 0,00")
        self.lbl_cost_year.setStyleSheet("font-size: 16px; font-weight: bold; color: #dc2626;")
        grid.addWidget(self.lbl_cost_year, 2, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_energy()
        return page

    def _on_preset_appliance_changed(self) -> None:
        val = self.cmb_appliance.currentData()
        if val > 0:
            self.spn_watts.setValue(float(val))

    def _recalc_energy(self) -> None:
        w = self.spn_watts.value()
        h = self.spn_hours_day.value()
        d = self.spn_days_month.value()
        t = self.spn_tarifa.value()

        res = calculate_energy_consumption(w, h, d, t)
        self.lbl_cost_month.setText(fmt_reais(res["custo_mensal"]))
        self.lbl_kwh_month.setText(f"{res['consumo_mensal_kwh']:.2f} kWh/mês")
        self.lbl_kwh_day.setText(f"{res['consumo_diario_kwh']:.3f} kWh/dia")
        self.lbl_cost_year.setText(fmt_reais(res["custo_anual"]))

    # -------------------------------------------------------------
    # ABA LEI DE OHM
    # -------------------------------------------------------------
    def _build_ohm_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        form_frame = QFrame()
        form_frame.setFixedWidth(360)
        v_form = QVBoxLayout(form_frame)
        f_layout = QFormLayout()

        self.cmb_ohm_mode = QComboBox()
        self.cmb_ohm_mode.addItem("Tensão (V) e Corrente (A)", "v_i")
        self.cmb_ohm_mode.addItem("Tensão (V) e Resistência (Ω)", "v_r")
        self.cmb_ohm_mode.addItem("Tensão (V) e Potência (W)", "v_p")
        self.cmb_ohm_mode.addItem("Corrente (A) e Resistência (Ω)", "i_r")
        self.cmb_ohm_mode.addItem("Corrente (A) e Potência (W)", "i_p")
        self.cmb_ohm_mode.addItem("Resistência (Ω) e Potência (W)", "r_p")
        self.cmb_ohm_mode.currentIndexChanged.connect(self._recalc_ohm)
        f_layout.addRow("Grandezas Conhecidas:", self.cmb_ohm_mode)

        self.spn_ohm_val1 = QDoubleSpinBox()
        self.spn_ohm_val1.setRange(0.0001, 1000000.0)
        self.spn_ohm_val1.setValue(127.0)
        self.spn_ohm_val1.setDecimals(3)
        self.spn_ohm_val1.valueChanged.connect(self._recalc_ohm)
        self.lbl_ohm_val1 = QLabel("Tensão (V):")
        f_layout.addRow(self.lbl_ohm_val1, self.spn_ohm_val1)

        self.spn_ohm_val2 = QDoubleSpinBox()
        self.spn_ohm_val2.setRange(0.0001, 1000000.0)
        self.spn_ohm_val2.setValue(10.0)
        self.spn_ohm_val2.setDecimals(3)
        self.spn_ohm_val2.valueChanged.connect(self._recalc_ohm)
        self.lbl_ohm_val2 = QLabel("Corrente (A):")
        f_layout.addRow(self.lbl_ohm_val2, self.spn_ohm_val2)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        layout.addWidget(form_frame)

        # Resultados Ohm
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        v_res.addWidget(QLabel("<b>Grandezas Elétricas Resultantes:</b>"))

        grid = QGridLayout()
        grid.setSpacing(12)

        grid.addWidget(QLabel("Tensão Elétrica (V):"), 0, 0)
        self.lbl_ohm_v = QLabel("127,0 V")
        self.lbl_ohm_v.setStyleSheet("font-size: 16px; font-weight: bold; color: #0284c7;")
        grid.addWidget(self.lbl_ohm_v, 0, 1)

        grid.addWidget(QLabel("Corrente Elétrica (I):"), 1, 0)
        self.lbl_ohm_i = QLabel("10,0 A")
        self.lbl_ohm_i.setStyleSheet("font-size: 16px; font-weight: bold; color: #16a34a;")
        grid.addWidget(self.lbl_ohm_i, 1, 1)

        grid.addWidget(QLabel("Resistência Elétrica (R):"), 2, 0)
        self.lbl_ohm_r = QLabel("12,7 Ω")
        self.lbl_ohm_r.setStyleSheet("font-size: 16px; font-weight: bold; color: #ea580c;")
        grid.addWidget(self.lbl_ohm_r, 2, 1)

        grid.addWidget(QLabel("Potência Elétrica Ativa (P):"), 3, 0)
        self.lbl_ohm_p = QLabel("1.270,0 W")
        self.lbl_ohm_p.setStyleSheet("font-size: 16px; font-weight: bold; color: #dc2626;")
        grid.addWidget(self.lbl_ohm_p, 3, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_ohm()
        return page

    def _recalc_ohm(self) -> None:
        mode = self.cmb_ohm_mode.currentData()
        val1 = self.spn_ohm_val1.value()
        val2 = self.spn_ohm_val2.value()

        kw = {}
        if mode == "v_i":
            self.lbl_ohm_val1.setText("Tensão (V):")
            self.lbl_ohm_val2.setText("Corrente (A):")
            kw = {"tensao_v": val1, "corrente_a": val2}
        elif mode == "v_r":
            self.lbl_ohm_val1.setText("Tensão (V):")
            self.lbl_ohm_val2.setText("Resistência (Ω):")
            kw = {"tensao_v": val1, "resistencia_ohm": val2}
        elif mode == "v_p":
            self.lbl_ohm_val1.setText("Tensão (V):")
            self.lbl_ohm_val2.setText("Potência (W):")
            kw = {"tensao_v": val1, "potencia_w": val2}
        elif mode == "i_r":
            self.lbl_ohm_val1.setText("Corrente (A):")
            self.lbl_ohm_val2.setText("Resistência (Ω):")
            kw = {"corrente_a": val1, "resistencia_ohm": val2}
        elif mode == "i_p":
            self.lbl_ohm_val1.setText("Corrente (A):")
            self.lbl_ohm_val2.setText("Potência (W):")
            kw = {"corrente_a": val1, "potencia_w": val2}
        elif mode == "r_p":
            self.lbl_ohm_val1.setText("Resistência (Ω):")
            self.lbl_ohm_val2.setText("Potência (W):")
            kw = {"resistencia_ohm": val1, "potencia_w": val2}

        res = calculate_ohm_law(**kw)
        if res:
            self.lbl_ohm_v.setText(f"{res['tensao_v']:.2f} V")
            self.lbl_ohm_i.setText(f"{res['corrente_a']:.3f} A")
            self.lbl_ohm_r.setText(f"{res['resistencia_ohm']:.3f} Ω")
            self.lbl_ohm_p.setText(f"{res['potencia_w']:.2f} W")

    # -------------------------------------------------------------
    # ABA RESISTORES
    # -------------------------------------------------------------
    def _build_resistor_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        form_frame = QFrame()
        form_frame.setFixedWidth(360)
        v_form = QVBoxLayout(form_frame)
        f_layout = QFormLayout()

        # Tipo 4 ou 5 faixas
        band_box = QHBoxLayout()
        self.rb_4faixas = QRadioButton("4 Faixas")
        self.rb_4faixas.setChecked(True)
        self.rb_4faixas.toggled.connect(self._on_resistor_mode_changed)
        self.rb_5faixas = QRadioButton("5 Faixas (Precisão)")
        band_box.addWidget(self.rb_4faixas)
        band_box.addWidget(self.rb_5faixas)
        f_layout.addRow("Padrão de Faixas:", band_box)

        cores_dig = list(RESISTOR_DIGITS.keys())

        self.cmb_f1 = QComboBox()
        self.cmb_f1.addItems(cores_dig[1:])  # Sem preto no primeiro dígito
        self.cmb_f1.setCurrentText("Amarelo")
        self.cmb_f1.currentTextChanged.connect(self._recalc_resistor)
        f_layout.addRow("1ª Faixa (Dígito 1):", self.cmb_f1)

        self.cmb_f2 = QComboBox()
        self.cmb_f2.addItems(cores_dig)
        self.cmb_f2.setCurrentText("Violeta")
        self.cmb_f2.currentTextChanged.connect(self._recalc_resistor)
        f_layout.addRow("2ª Faixa (Dígito 2):", self.cmb_f2)

        self.cmb_f3 = QComboBox()
        self.cmb_f3.addItems(cores_dig)
        self.cmb_f3.setCurrentText("Preto")
        self.cmb_f3.setVisible(False)
        self.lbl_f3_label = QLabel("3ª Faixa (Dígito 3):")
        self.lbl_f3_label.setVisible(False)
        self.cmb_f3.currentTextChanged.connect(self._recalc_resistor)
        f_layout.addRow(self.lbl_f3_label, self.cmb_f3)

        self.cmb_mult = QComboBox()
        self.cmb_mult.addItems(list(RESISTOR_MULTIPLIERS.keys()))
        self.cmb_mult.setCurrentText("Laranja")
        self.cmb_mult.currentTextChanged.connect(self._recalc_resistor)
        f_layout.addRow("Multiplicador:", self.cmb_mult)

        self.cmb_tol = QComboBox()
        self.cmb_tol.addItems(list(RESISTOR_TOLERANCES.keys()))
        self.cmb_tol.setCurrentText("Dourado")
        self.cmb_tol.currentTextChanged.connect(self._recalc_resistor)
        f_layout.addRow("Tolerância:", self.cmb_tol)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        layout.addWidget(form_frame)

        # Resultados Resistor
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        card_res = QFrame()
        card_res.setStyleSheet("background-color: rgba(22, 163, 74, 0.15); border-radius: 6px; padding: 12px;")
        v_r = QVBoxLayout(card_res)
        v_r.addWidget(QLabel("VALOR NOMINAL DA RESISTÊNCIA:"))
        self.lbl_res_nominal = QLabel("47 kΩ ±5%")
        self.lbl_res_nominal.setStyleSheet("font-size: 26px; font-weight: bold; color: #16a34a;")
        v_r.addWidget(self.lbl_res_nominal)
        v_res.addWidget(card_res)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Valor Exato em Ohms:"), 0, 0)
        self.lbl_res_ohms = QLabel("47.000 Ω")
        self.lbl_res_ohms.setStyleSheet("font-size: 16px; font-weight: bold;")
        grid.addWidget(self.lbl_res_ohms, 0, 1)

        grid.addWidget(QLabel("Faixa Aceitável Mínima:"), 1, 0)
        self.lbl_res_min = QLabel("44.650 Ω")
        grid.addWidget(self.lbl_res_min, 1, 1)

        grid.addWidget(QLabel("Faixa Aceitável Máxima:"), 2, 0)
        self.lbl_res_max = QLabel("49.350 Ω")
        grid.addWidget(self.lbl_res_max, 2, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_resistor()
        return page

    def _on_resistor_mode_changed(self) -> None:
        is_5 = self.rb_5faixas.isChecked()
        self.lbl_f3_label.setVisible(is_5)
        self.cmb_f3.setVisible(is_5)
        self._recalc_resistor()

    def _recalc_resistor(self) -> None:
        f1 = self.cmb_f1.currentText()
        f2 = self.cmb_f2.currentText()
        mult = self.cmb_mult.currentText()
        tol = self.cmb_tol.currentText()
        f3 = self.cmb_f3.currentText() if self.rb_5faixas.isChecked() else None

        res = calculate_resistor_value(f1, f2, mult, tol, f3)
        self.lbl_res_nominal.setText(res["formatado"])
        self.lbl_res_ohms.setText(f"{res['valor_ohms']:,.2f} Ω".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_res_min.setText(f"{res['valor_minimo']:,.2f} Ω".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_res_max.setText(f"{res['valor_maximo']:,.2f} Ω".replace(",", "X").replace(".", ",").replace("X", "."))
