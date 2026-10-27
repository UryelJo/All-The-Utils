"""
Interface de usuário para a Calculadora da Folha de Pagamento Brasileira (CLT).
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.salary_br.logic import (
    calculate_ferias,
    calculate_folha_pagamento,
    calculate_rescisao,
)


def fmt_reais(val: float) -> str:
    """Formata número para padrão monetário brasileiro R$ 1.234,56."""
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@register
class SalaryBrTool(Tool):
    """Calculadora da Folha de Pagamento Brasileira (CLT, INSS, IRRF, Férias e Rescisão)."""

    id = "calc.salary_br"
    name = "Calculadora Salarial CLT (Folha de Pagamento)"
    description = "Calcule salário líquido, deduções progressivas de INSS e IRRF, alíquota efetiva, FGTS, férias e rescisão trabalhista."
    category = "calc"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        title = QLabel("Calculadora Salarial & Trabalhista (CLT)")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Cálculo preciso com as tabelas progressivas oficiais de INSS e IRRF (comparativo simplificado vs. deduções legais)."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        tabs.addTab(self._build_salario_tab(), "Salário Líquido")
        tabs.addTab(self._build_ferias_tab(), "Cálculo de Férias")
        tabs.addTab(self._build_rescisao_tab(), "Simulador de Rescisão")

        return widget

    # -------------------------------------------------------------
    # ABA SALÁRIO LÍQUIDO
    # -------------------------------------------------------------
    def _build_salario_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        # Formulário à esquerda
        form_frame = QFrame()
        form_frame.setFixedWidth(360)
        v_form = QVBoxLayout(form_frame)
        v_form.setSpacing(10)

        f_layout = QFormLayout()

        self.spn_sal_bruto = QDoubleSpinBox()
        self.spn_sal_bruto.setRange(0, 1000000.0)
        self.spn_sal_bruto.setPrefix("R$ ")
        self.spn_sal_bruto.setValue(4500.0)
        self.spn_sal_bruto.setDecimals(2)
        self.spn_sal_bruto.valueChanged.connect(self._recalc_salario)
        f_layout.addRow("Salário Bruto:", self.spn_sal_bruto)

        self.spn_dep = QSpinBox()
        self.spn_dep.setRange(0, 20)
        self.spn_dep.setValue(0)
        self.spn_dep.valueChanged.connect(self._recalc_salario)
        f_layout.addRow("Número de Dependentes:", self.spn_dep)

        self.spn_pensao = QDoubleSpinBox()
        self.spn_pensao.setRange(0, 1000000.0)
        self.spn_pensao.setPrefix("R$ ")
        self.spn_pensao.setValue(0.0)
        self.spn_pensao.valueChanged.connect(self._recalc_salario)
        f_layout.addRow("Pensão Alimentícia:", self.spn_pensao)

        self.spn_outros_desc = QDoubleSpinBox()
        self.spn_outros_desc.setRange(0, 1000000.0)
        self.spn_outros_desc.setPrefix("R$ ")
        self.spn_outros_desc.setValue(0.0)
        self.spn_outros_desc.valueChanged.connect(self._recalc_salario)
        f_layout.addRow("Outros Descontos (VT, VR):", self.spn_outros_desc)

        self.spn_outros_prov = QDoubleSpinBox()
        self.spn_outros_prov.setRange(0, 1000000.0)
        self.spn_outros_prov.setPrefix("R$ ")
        self.spn_outros_prov.setValue(0.0)
        self.spn_outros_prov.valueChanged.connect(self._recalc_salario)
        f_layout.addRow("Outros Proventos (Bônus):", self.spn_outros_prov)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        layout.addWidget(form_frame)

        # Painel de Resultados à direita
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        v_res.addWidget(QLabel("<b>Resultado do Contracheque:</b>"))

        # Card Salário Líquido
        card_liq = QFrame()
        card_liq.setStyleSheet("background-color: rgba(22, 163, 74, 0.15); border-radius: 6px; padding: 12px;")
        v_liq = QVBoxLayout(card_liq)
        v_liq.addWidget(QLabel("SALÁRIO LÍQUIDO A RECEBER:"))
        self.lbl_sal_liq = QLabel("R$ 0,00")
        self.lbl_sal_liq.setStyleSheet("font-size: 26px; font-weight: bold; color: #16a34a;")
        v_liq.addWidget(self.lbl_sal_liq)
        v_res.addWidget(card_liq)

        # Grid de detalhes
        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Desconto INSS:"), 0, 0)
        self.lbl_inss = QLabel("R$ 0,00")
        self.lbl_inss.setStyleSheet("font-weight: bold; color: #dc2626;")
        grid.addWidget(self.lbl_inss, 0, 1)

        grid.addWidget(QLabel("Alíquota Efetiva INSS:"), 1, 0)
        self.lbl_aliq_inss = QLabel("0,00%")
        grid.addWidget(self.lbl_aliq_inss, 1, 1)

        grid.addWidget(QLabel("Desconto IRRF:"), 2, 0)
        self.lbl_irrf = QLabel("R$ 0,00")
        self.lbl_irrf.setStyleSheet("font-weight: bold; color: #dc2626;")
        grid.addWidget(self.lbl_irrf, 2, 1)

        grid.addWidget(QLabel("Alíquota Efetiva IRRF:"), 3, 0)
        self.lbl_aliq_irrf = QLabel("0,00% (Método)")
        grid.addWidget(self.lbl_aliq_irrf, 3, 1)

        grid.addWidget(QLabel("FGTS (Depósito da Empresa 8%):"), 4, 0)
        self.lbl_fgts = QLabel("R$ 0,00")
        self.lbl_fgts.setStyleSheet("font-weight: bold; color: #0284c7;")
        grid.addWidget(self.lbl_fgts, 4, 1)

        grid.addWidget(QLabel("Total de Descontos:"), 5, 0)
        self.lbl_tot_desc = QLabel("R$ 0,00")
        self.lbl_tot_desc.setStyleSheet("font-weight: bold; color: #dc2626;")
        grid.addWidget(self.lbl_tot_desc, 5, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_salario()
        return page

    def _recalc_salario(self) -> None:
        sal = self.spn_sal_bruto.value()
        dep = self.spn_dep.value()
        pensao = self.spn_pensao.value()
        outros_d = self.spn_outros_desc.value()
        outros_p = self.spn_outros_prov.value()

        res = calculate_folha_pagamento(sal, dep, outros_d, outros_p, pensao)

        self.lbl_sal_liq.setText(fmt_reais(res["salario_liquido"]))
        self.lbl_inss.setText(fmt_reais(res["inss"]))
        self.lbl_aliq_inss.setText(f"{res['aliq_inss']:.2f}%")
        self.lbl_irrf.setText(fmt_reais(res["irrf"]))
        self.lbl_aliq_irrf.setText(f"{res['aliq_irrf']:.2f}% ({res['metodo_irrf']})")
        self.lbl_fgts.setText(fmt_reais(res["fgts"]))
        self.lbl_tot_desc.setText(fmt_reais(res["total_descontos"]))

    # -------------------------------------------------------------
    # ABA FÉRIAS
    # -------------------------------------------------------------
    def _build_ferias_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        form_frame = QFrame()
        form_frame.setFixedWidth(360)
        v_form = QVBoxLayout(form_frame)
        f_layout = QFormLayout()

        self.spn_ferias_sal = QDoubleSpinBox()
        self.spn_ferias_sal.setRange(0, 1000000.0)
        self.spn_ferias_sal.setPrefix("R$ ")
        self.spn_ferias_sal.setValue(4500.0)
        self.spn_ferias_sal.valueChanged.connect(self._recalc_ferias)
        f_layout.addRow("Salário Base:", self.spn_ferias_sal)

        self.spn_ferias_dias = QSpinBox()
        self.spn_ferias_dias.setRange(10, 30)
        self.spn_ferias_dias.setValue(30)
        self.spn_ferias_dias.valueChanged.connect(self._recalc_ferias)
        f_layout.addRow("Dias de Férias:", self.spn_ferias_dias)

        self.spn_ferias_abono = QSpinBox()
        self.spn_ferias_abono.setRange(0, 10)
        self.spn_ferias_abono.setValue(0)
        self.spn_ferias_abono.valueChanged.connect(self._recalc_ferias)
        f_layout.addRow("Abono Pecuniário (Venda de Dias):", self.spn_ferias_abono)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        layout.addWidget(form_frame)

        # Resultados de férias
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(10)

        card_liq = QFrame()
        card_liq.setStyleSheet("background-color: rgba(22, 163, 74, 0.15); border-radius: 6px; padding: 12px;")
        v_liq = QVBoxLayout(card_liq)
        v_liq.addWidget(QLabel("VALOR LÍQUIDO DAS FÉRIAS:"))
        self.lbl_ferias_liq = QLabel("R$ 0,00")
        self.lbl_ferias_liq.setStyleSheet("font-size: 26px; font-weight: bold; color: #16a34a;")
        v_liq.addWidget(self.lbl_ferias_liq)
        v_res.addWidget(card_liq)

        grid = QGridLayout()
        grid.addWidget(QLabel("Remuneração dos Dias:"), 0, 0)
        self.lbl_ferias_dias_val = QLabel("R$ 0,00")
        grid.addWidget(self.lbl_ferias_dias_val, 0, 1)

        grid.addWidget(QLabel("1/3 Constitucional de Férias:"), 1, 0)
        self.lbl_ferias_terco = QLabel("R$ 0,00")
        grid.addWidget(self.lbl_ferias_terco, 1, 1)

        grid.addWidget(QLabel("Abono Pecuniário (+ 1/3):"), 2, 0)
        self.lbl_ferias_abono_val = QLabel("R$ 0,00")
        grid.addWidget(self.lbl_ferias_abono_val, 2, 1)

        grid.addWidget(QLabel("Descontos (INSS + IRRF):"), 3, 0)
        self.lbl_ferias_desc = QLabel("R$ 0,00")
        self.lbl_ferias_desc.setStyleSheet("color: #dc2626; font-weight: bold;")
        grid.addWidget(self.lbl_ferias_desc, 3, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_ferias()
        return page

    def _recalc_ferias(self) -> None:
        sal = self.spn_ferias_sal.value()
        dias = self.spn_ferias_dias.value()
        abono = self.spn_ferias_abono.value()

        res = calculate_ferias(sal, dias, abono)
        self.lbl_ferias_liq.setText(fmt_reais(res["total_liquido"]))
        self.lbl_ferias_dias_val.setText(fmt_reais(res["valor_gozo"]))
        self.lbl_ferias_terco.setText(fmt_reais(res["terco_constitucional"]))
        self.lbl_ferias_abono_val.setText(fmt_reais(res["total_abono"]))
        self.lbl_ferias_desc.setText(fmt_reais(res["total_descontos"]))

    # -------------------------------------------------------------
    # ABA RESCISÃO
    # -------------------------------------------------------------
    def _build_rescisao_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        form_frame = QFrame()
        form_frame.setFixedWidth(360)
        v_form = QVBoxLayout(form_frame)
        f_layout = QFormLayout()

        self.spn_resc_sal = QDoubleSpinBox()
        self.spn_resc_sal.setRange(0, 1000000.0)
        self.spn_resc_sal.setPrefix("R$ ")
        self.spn_resc_sal.setValue(4500.0)
        self.spn_resc_sal.valueChanged.connect(self._recalc_rescisao)
        f_layout.addRow("Salário Base:", self.spn_resc_sal)

        self.cmb_resc_motivo = QComboBox()
        self.cmb_resc_motivo.addItem("Demissão Sem Justa Causa", "sem_justa_causa")
        self.cmb_resc_motivo.addItem("Pedido de Demissão", "pedido_demissao")
        self.cmb_resc_motivo.addItem("Demissão Com Justa Causa", "com_justa_causa")
        self.cmb_resc_motivo.addItem("Acordo Mútuo (Art. 484-A)", "acordo_mutuo")
        self.cmb_resc_motivo.currentIndexChanged.connect(self._recalc_rescisao)
        f_layout.addRow("Motivo do Desligamento:", self.cmb_resc_motivo)

        self.spn_resc_meses = QSpinBox()
        self.spn_resc_meses.setRange(1, 360)
        self.spn_resc_meses.setValue(18)
        self.spn_resc_meses.valueChanged.connect(self._recalc_rescisao)
        f_layout.addRow("Meses Trabalhados:", self.spn_resc_meses)

        self.spn_resc_saldo = QSpinBox()
        self.spn_resc_saldo.setRange(0, 31)
        self.spn_resc_saldo.setValue(15)
        self.spn_resc_saldo.valueChanged.connect(self._recalc_rescisao)
        f_layout.addRow("Dias de Saldo no Mês:", self.spn_resc_saldo)

        self.chk_resc_ferias_venc = QCheckBox("Possui Férias Vencidas")
        self.chk_resc_ferias_venc.stateChanged.connect(self._recalc_rescisao)
        f_layout.addRow("", self.chk_resc_ferias_venc)

        self.chk_resc_aviso = QCheckBox("Aviso Prévio Indenizado")
        self.chk_resc_aviso.setChecked(True)
        self.chk_resc_aviso.stateChanged.connect(self._recalc_rescisao)
        f_layout.addRow("", self.chk_resc_aviso)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        layout.addWidget(form_frame)

        # Resultados da rescisão
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(10)

        card_liq = QFrame()
        card_liq.setStyleSheet("background-color: rgba(22, 163, 74, 0.15); border-radius: 6px; padding: 12px;")
        v_liq = QVBoxLayout(card_liq)
        v_liq.addWidget(QLabel("TOTAL ESTIMADO DA RESCISÃO:"))
        self.lbl_resc_total = QLabel("R$ 0,00")
        self.lbl_resc_total.setStyleSheet("font-size: 26px; font-weight: bold; color: #16a34a;")
        v_liq.addWidget(self.lbl_resc_total)
        v_res.addWidget(card_liq)

        grid = QGridLayout()
        grid.addWidget(QLabel("Saldo de Salário:"), 0, 0)
        self.lbl_resc_saldo = QLabel("R$ 0,00")
        grid.addWidget(self.lbl_resc_saldo, 0, 1)

        grid.addWidget(QLabel("13º Salário Proporcional:"), 1, 0)
        self.lbl_resc_13 = QLabel("R$ 0,00")
        grid.addWidget(self.lbl_resc_13, 1, 1)

        grid.addWidget(QLabel("Férias Proporcionais (+ 1/3):"), 2, 0)
        self.lbl_resc_ferias_prop = QLabel("R$ 0,00")
        grid.addWidget(self.lbl_resc_ferias_prop, 2, 1)

        grid.addWidget(QLabel("Aviso Prévio:"), 3, 0)
        self.lbl_resc_aviso = QLabel("R$ 0,00")
        grid.addWidget(self.lbl_resc_aviso, 3, 1)

        grid.addWidget(QLabel("Multa Rescisória do FGTS:"), 4, 0)
        self.lbl_resc_multa_fgts = QLabel("R$ 0,00")
        self.lbl_resc_multa_fgts.setStyleSheet("color: #0284c7; font-weight: bold;")
        grid.addWidget(self.lbl_resc_multa_fgts, 4, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_rescisao()
        return page

    def _recalc_rescisao(self) -> None:
        sal = self.spn_resc_sal.value()
        motivo = self.cmb_resc_motivo.currentData()
        meses = self.spn_resc_meses.value()
        dias = self.spn_resc_saldo.value()
        ferias_v = self.chk_resc_ferias_venc.isChecked()
        aviso = self.chk_resc_aviso.isChecked()

        res = calculate_rescisao(sal, meses, motivo, dias, ferias_v, aviso)
        self.lbl_resc_total.setText(fmt_reais(res["total_liquido"]))
        self.lbl_resc_saldo.setText(fmt_reais(res["saldo_salario"]))
        self.lbl_resc_13.setText(fmt_reais(res["decimo_terceiro_prop"]))
        tot_ferias = res["ferias_prop"] + res["terco_ferias_prop"] + res["ferias_vencidas"]
        self.lbl_resc_ferias_prop.setText(fmt_reais(tot_ferias))
        self.lbl_resc_aviso.setText(fmt_reais(res["aviso_previo"]))
        self.lbl_resc_multa_fgts.setText(fmt_reais(res["multa_fgts"]))
