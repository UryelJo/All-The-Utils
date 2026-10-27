"""
Interface de usuário para a Calculadora de Saúde, Metabolismo e Hidratação.
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
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.health.logic import (
    calculate_imc,
    calculate_tdee_and_goals,
    calculate_tmb_mifflin_st_jeor,
    calculate_water_intake,
)


@register
class HealthCalcTool(Tool):
    """Calculadora de parâmetros biométricos, IMC, taxa metabólica (TMB/TDEE) e hidratação."""

    id = "calc.health"
    name = "Calculadora de Saúde & Metabolismo (IMC / TMB)"
    description = "Calcule IMC com classificação OMS, gasto calórico diário (TDEE), metas nutricionais e ingestão de água."
    category = "Calculadoras"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Cabeçalho
        title = QLabel("Calculadora de Saúde, Metabolismo & Nutrição")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Parâmetros biométricos baseados nos protocolos da OMS e equações de Mifflin-St Jeor para planejamento saudável."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        main_box = QHBoxLayout()
        main_box.setSpacing(15)

        # Painel Esquerdo: Entradas
        form_frame = QFrame()
        form_frame.setFixedWidth(340)
        v_form = QVBoxLayout(form_frame)
        v_form.setSpacing(10)

        f_layout = QFormLayout()

        # Sexo biológico
        sex_box = QHBoxLayout()
        self.rb_masc = QRadioButton("Masculino")
        self.rb_masc.setChecked(True)
        self.rb_masc.toggled.connect(self._recalculate)
        self.rb_fem = QRadioButton("Feminino")
        self.rb_fem.toggled.connect(self._recalculate)
        sex_box.addWidget(self.rb_masc)
        sex_box.addWidget(self.rb_fem)
        f_layout.addRow("Sexo Biológico:", sex_box)

        # Idade
        self.spn_idade = QSpinBox()
        self.spn_idade.setRange(10, 120)
        self.spn_idade.setValue(30)
        self.spn_idade.setSuffix(" anos")
        self.spn_idade.valueChanged.connect(self._recalculate)
        f_layout.addRow("Idade:", self.spn_idade)

        # Peso
        self.spn_peso = QDoubleSpinBox()
        self.spn_peso.setRange(20.0, 300.0)
        self.spn_peso.setValue(75.0)
        self.spn_peso.setDecimals(1)
        self.spn_peso.setSuffix(" kg")
        self.spn_peso.valueChanged.connect(self._recalculate)
        f_layout.addRow("Peso Atual:", self.spn_peso)

        # Altura
        self.spn_altura = QDoubleSpinBox()
        self.spn_altura.setRange(80.0, 240.0)
        self.spn_altura.setValue(175.0)
        self.spn_altura.setDecimals(1)
        self.spn_altura.setSuffix(" cm")
        self.spn_altura.valueChanged.connect(self._recalculate)
        f_layout.addRow("Altura:", self.spn_altura)

        # Atividade física
        self.cmb_atividade = QComboBox()
        self.cmb_atividade.addItem("Sedentário (pouco ou nenhum exercício)", "sedentario")
        self.cmb_atividade.addItem("Leve (exercício 1 a 3 dias/semana)", "leve")
        self.cmb_atividade.addItem("Moderado (exercício 3 a 5 dias/semana)", "moderado")
        self.cmb_atividade.addItem("Intenso (exercício pesado 6 a 7 dias)", "intenso")
        self.cmb_atividade.addItem("Extremo (treino 2x ao dia / atleta)", "extremo")
        self.cmb_atividade.setCurrentIndex(2)
        self.cmb_atividade.currentIndexChanged.connect(self._recalculate)
        f_layout.addRow("Nível de Atividade:", self.cmb_atividade)

        # Tempo de treino diário para hidratação
        self.spn_treino_min = QSpinBox()
        self.spn_treino_min.setRange(0, 240)
        self.spn_treino_min.setValue(45)
        self.spn_treino_min.setSuffix(" minutos/dia")
        self.spn_treino_min.valueChanged.connect(self._recalculate)
        f_layout.addRow("Tempo Médio de Exercício:", self.spn_treino_min)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        main_box.addWidget(form_frame)

        # Painel Direito: Resultados
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 12px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        # 1. Card IMC
        card_imc = QFrame()
        card_imc.setStyleSheet("background-color: rgba(128, 128, 128, 0.1); border-radius: 6px; padding: 10px;")
        v_imc = QVBoxLayout(card_imc)
        v_imc.addWidget(QLabel("<b>Índice de Massa Corporal (IMC):</b>"))

        imc_h = QHBoxLayout()
        self.lbl_imc_val = QLabel("24.5")
        self.lbl_imc_val.setStyleSheet("font-size: 24px; font-weight: bold; color: #16a34a;")
        imc_h.addWidget(self.lbl_imc_val)

        self.lbl_imc_class = QLabel("Peso normal")
        self.lbl_imc_class.setStyleSheet("font-size: 16px; font-weight: bold; color: #16a34a;")
        imc_h.addWidget(self.lbl_imc_class, 1)
        v_imc.addLayout(imc_h)

        self.lbl_peso_ideal = QLabel("Faixa de Peso Ideal: 56.7 kg a 76.3 kg")
        self.lbl_peso_ideal.setStyleSheet("color: #888888; font-size: 12px;")
        v_imc.addWidget(self.lbl_peso_ideal)
        v_res.addWidget(card_imc)

        # 2. Card Metabolismo e Gasto Calórico
        card_tmb = QFrame()
        card_tmb.setStyleSheet("background-color: rgba(128, 128, 128, 0.1); border-radius: 6px; padding: 10px;")
        v_tmb = QVBoxLayout(card_tmb)
        v_tmb.addWidget(QLabel("<b>Gasto Calórico e Taxa Metabólica:</b>"))

        grid_tmb = QGridLayout()
        grid_tmb.setSpacing(8)

        grid_tmb.addWidget(QLabel("Taxa Metabólica Basal (TMB em repouso):"), 0, 0)
        self.lbl_tmb_val = QLabel("1.690 kcal")
        self.lbl_tmb_val.setStyleSheet("font-weight: bold; color: #0284c7;")
        grid_tmb.addWidget(self.lbl_tmb_val, 0, 1)

        grid_tmb.addWidget(QLabel("Gasto Total para Manter Peso (TDEE):"), 1, 0)
        self.lbl_tdee_val = QLabel("2.620 kcal")
        self.lbl_tdee_val.setStyleSheet("font-weight: bold; color: #16a34a;")
        grid_tmb.addWidget(self.lbl_tdee_val, 1, 1)

        grid_tmb.addWidget(QLabel("Meta para Perda de Gordura (-500 kcal):"), 2, 0)
        self.lbl_perda_val = QLabel("2.120 kcal")
        self.lbl_perda_val.setStyleSheet("font-weight: bold; color: #ea580c;")
        grid_tmb.addWidget(self.lbl_perda_val, 2, 1)

        grid_tmb.addWidget(QLabel("Meta para Ganho de Massa Muscular:"), 3, 0)
        self.lbl_ganho_val = QLabel("2.970 kcal")
        self.lbl_ganho_val.setStyleSheet("font-weight: bold; color: #3b82f6;")
        grid_tmb.addWidget(self.lbl_ganho_val, 3, 1)

        v_tmb.addLayout(grid_tmb)
        v_res.addWidget(card_tmb)

        # 3. Card Hidratação
        card_water = QFrame()
        card_water.setStyleSheet("background-color: rgba(128, 128, 128, 0.1); border-radius: 6px; padding: 10px;")
        v_water = QVBoxLayout(card_water)
        v_water.addWidget(QLabel("<b>Ingestão Diária Recomendada de Água:</b>"))

        w_h = QHBoxLayout()
        self.lbl_water_val = QLabel("3,1 L")
        self.lbl_water_val.setStyleSheet("font-size: 24px; font-weight: bold; color: #06b6d4;")
        w_h.addWidget(self.lbl_water_val)

        self.lbl_water_detail = QLabel("(aprox. 3.125 ml ou 12 copos de 250 ml)")
        self.lbl_water_detail.setStyleSheet("font-size: 13px; color: #888888;")
        w_h.addWidget(self.lbl_water_detail, 1)
        v_water.addLayout(w_h)
        v_res.addWidget(card_water)

        v_res.addStretch()
        main_box.addWidget(res_frame, 1)

        layout.addLayout(main_box, 1)

        self._recalculate()
        return widget

    def _recalculate(self) -> None:
        peso = self.spn_peso.value()
        altura = self.spn_altura.value()
        idade = self.spn_idade.value()
        sexo = "M" if self.rb_masc.isChecked() else "F"
        atividade = self.cmb_atividade.currentData()
        treino_min = self.spn_treino_min.value()

        # 1. IMC
        imc, imc_class, peso_ideal_str = calculate_imc(peso, altura)
        self.lbl_imc_val.setText(f"{imc:.2f}")
        self.lbl_imc_class.setText(imc_class)
        self.lbl_peso_ideal.setText(f"Faixa de Peso Ideal recomendada: {peso_ideal_str}")

        if "normal" in imc_class.lower():
            cor = "#16a34a"
        elif "sobrepeso" in imc_class.lower() or "abaixo" in imc_class.lower():
            cor = "#ea580c"
        else:
            cor = "#dc2626"
        self.lbl_imc_val.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {cor};")
        self.lbl_imc_class.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {cor};")

        # 2. TMB e TDEE
        tmb = calculate_tmb_mifflin_st_jeor(peso, altura, idade, sexo)
        tdee_goals = calculate_tdee_and_goals(tmb, atividade)
        self.lbl_tmb_val.setText(f"{tmb:,.0f} kcal/dia".replace(",", "."))
        self.lbl_tdee_val.setText(f"{tdee_goals['tdee_manutencao']:,.0f} kcal/dia".replace(",", "."))
        self.lbl_perda_val.setText(f"{tdee_goals['emagrecimento_moderado']:,.0f} kcal/dia".replace(",", "."))
        self.lbl_ganho_val.setText(f"{tdee_goals['hipertrofia_ganho']:,.0f} kcal/dia".replace(",", "."))

        # 3. Água
        water = calculate_water_intake(peso, treino_min)
        self.lbl_water_val.setText(f"{water['total_litros']:.2f} Litros".replace(".", ","))
        self.lbl_water_detail.setText(f"(aprox. {water['total_ml']} ml ou {water['copos_250ml']} copos de 250 ml)")
