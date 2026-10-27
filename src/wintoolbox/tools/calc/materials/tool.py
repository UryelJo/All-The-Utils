"""
Interface de usuário para a Calculadora de Materiais de Construção e Reformas.
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
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.materials.logic import (
    calculate_concrete_volume,
    calculate_flooring_materials,
    calculate_paint_materials,
)


@register
class MaterialsCalcTool(Tool):
    """Calculadora de materiais de construção: tintas, revestimentos cerâmicos e concreto."""

    id = "calc.materials"
    name = "Calculadora de Materiais de Construção & Reforma"
    description = "Estime quantidades exatas de tinta, caixas de piso/porcelanato com perda, argamassa, rejunte e volume de concreto."
    category = "Calculadoras"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Cabeçalho
        title = QLabel("Calculadora de Materiais de Construção & Reformas")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Evite desperdícios e compras insuficientes calculando tintas, pisos, argamassa e concreto com margens técnicas."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        tabs.addTab(self._build_paint_tab(), "Pintura & Tintas")
        tabs.addTab(self._build_flooring_tab(), "Pisos & Revestimentos")
        tabs.addTab(self._build_concrete_tab(), "Concreto & Contrapiso")

        return widget

    # -------------------------------------------------------------
    # ABA TINTAS
    # -------------------------------------------------------------
    def _build_paint_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        form_frame = QFrame()
        form_frame.setFixedWidth(340)
        v_form = QVBoxLayout(form_frame)
        f_layout = QFormLayout()

        self.spn_paint_area = QDoubleSpinBox()
        self.spn_paint_area.setRange(1.0, 50000.0)
        self.spn_paint_area.setValue(45.0)
        self.spn_paint_area.setSuffix(" m²")
        self.spn_paint_area.valueChanged.connect(self._recalc_paint)
        f_layout.addRow("Área Total a Pintar:", self.spn_paint_area)

        self.spn_paint_demaos = QSpinBox()
        self.spn_paint_demaos.setRange(1, 5)
        self.spn_paint_demaos.setValue(2)
        self.spn_paint_demaos.setSuffix(" demãos")
        self.spn_paint_demaos.valueChanged.connect(self._recalc_paint)
        f_layout.addRow("Número de Demãos:", self.spn_paint_demaos)

        self.spn_paint_rend = QDoubleSpinBox()
        self.spn_paint_rend.setRange(4.0, 25.0)
        self.spn_paint_rend.setValue(10.0)
        self.spn_paint_rend.setSuffix(" m²/L")
        self.spn_paint_rend.valueChanged.connect(self._recalc_paint)
        f_layout.addRow("Rendimento da Tinta:", self.spn_paint_rend)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        layout.addWidget(form_frame)

        # Resultados de tinta
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        card_tot = QFrame()
        card_tot.setStyleSheet("background-color: rgba(2, 132, 199, 0.15); border-radius: 6px; padding: 12px;")
        v_tot = QVBoxLayout(card_tot)
        v_tot.addWidget(QLabel("TOTAL DE TINTA NECESSÁRIO:"))
        self.lbl_paint_vol = QLabel("9,0 Litros")
        self.lbl_paint_vol.setStyleSheet("font-size: 26px; font-weight: bold; color: #0284c7;")
        v_tot.addWidget(self.lbl_paint_vol)
        v_res.addWidget(card_tot)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Latas de 18 Litros:"), 0, 0)
        self.lbl_paint_18l = QLabel("0 lata(s)")
        self.lbl_paint_18l.setStyleSheet("font-size: 15px; font-weight: bold;")
        grid.addWidget(self.lbl_paint_18l, 0, 1)

        grid.addWidget(QLabel("Galões de 3,6 Litros:"), 1, 0)
        self.lbl_paint_3_6l = QLabel("2 galão(ões)")
        self.lbl_paint_3_6l.setStyleSheet("font-size: 15px; font-weight: bold;")
        grid.addWidget(self.lbl_paint_3_6l, 1, 1)

        grid.addWidget(QLabel("Quartos de 900 ml:"), 2, 0)
        self.lbl_paint_0_9l = QLabel("2 quarto(s)")
        self.lbl_paint_0_9l.setStyleSheet("font-size: 15px; font-weight: bold;")
        grid.addWidget(self.lbl_paint_0_9l, 2, 1)

        grid.addWidget(QLabel("Volume Comprado Total:"), 3, 0)
        self.lbl_paint_cap = QLabel("9,0 L")
        grid.addWidget(self.lbl_paint_cap, 3, 1)

        grid.addWidget(QLabel("Sobra Estimada:"), 4, 0)
        self.lbl_paint_sobra = QLabel("0,0 L")
        self.lbl_paint_sobra.setStyleSheet("color: #16a34a;")
        grid.addWidget(self.lbl_paint_sobra, 4, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_paint()
        return page

    def _recalc_paint(self) -> None:
        area = self.spn_paint_area.value()
        demaos = self.spn_paint_demaos.value()
        rend = self.spn_paint_rend.value()

        res = calculate_paint_materials(area, demaos, rend)
        self.lbl_paint_vol.setText(f"{res['litros_totais']:.1f} Litros")
        self.lbl_paint_18l.setText(f"{res['latas_18l']} unidade(s)")
        self.lbl_paint_3_6l.setText(f"{res['galoes_3_6l']} unidade(s)")
        self.lbl_paint_0_9l.setText(f"{res['quartos_0_9l']} unidade(s)")
        self.lbl_paint_cap.setText(f"{res['capacidade_total']:.1f} L")
        self.lbl_paint_sobra.setText(f"{res['sobra_litros']:.2f} L")

    # -------------------------------------------------------------
    # ABA PISOS & REVESTIMENTOS
    # -------------------------------------------------------------
    def _build_flooring_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        form_frame = QFrame()
        form_frame.setFixedWidth(340)
        v_form = QVBoxLayout(form_frame)
        f_layout = QFormLayout()

        self.spn_floor_area = QDoubleSpinBox()
        self.spn_floor_area.setRange(0.5, 50000.0)
        self.spn_floor_area.setValue(35.0)
        self.spn_floor_area.setSuffix(" m²")
        self.spn_floor_area.valueChanged.connect(self._recalc_flooring)
        f_layout.addRow("Área Líquida do Cômodo:", self.spn_floor_area)

        self.cmb_floor_layout = QComboBox()
        self.cmb_floor_layout.addItem("Assentamento Reto (10% de perda)", 10.0)
        self.cmb_floor_layout.addItem("Assentamento Diagonal / Espinha (15% de perda)", 15.0)
        self.cmb_floor_layout.addItem("Grandes Formatos / Recortes Complexos (20% de perda)", 20.0)
        self.cmb_floor_layout.currentIndexChanged.connect(self._recalc_flooring)
        f_layout.addRow("Margem de Perda / Cortes:", self.cmb_floor_layout)

        self.spn_floor_box_m2 = QDoubleSpinBox()
        self.spn_floor_box_m2.setRange(0.5, 10.0)
        self.spn_floor_box_m2.setValue(2.16)
        self.spn_floor_box_m2.setSuffix(" m²/caixa")
        self.spn_floor_box_m2.valueChanged.connect(self._recalc_flooring)
        f_layout.addRow("Metragem por Caixa do Piso:", self.spn_floor_box_m2)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        layout.addWidget(form_frame)

        # Resultados de pisos
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        card_cx = QFrame()
        card_cx.setStyleSheet("background-color: rgba(22, 163, 74, 0.15); border-radius: 6px; padding: 12px;")
        v_cx = QVBoxLayout(card_cx)
        v_cx.addWidget(QLabel("TOTAL DE CAIXAS A COMPRAR:"))
        self.lbl_floor_boxes = QLabel("18 caixas")
        self.lbl_floor_boxes.setStyleSheet("font-size: 26px; font-weight: bold; color: #16a34a;")
        v_cx.addWidget(self.lbl_floor_boxes)
        v_res.addWidget(card_cx)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Área Total com Margem de Perda:"), 0, 0)
        self.lbl_floor_tot_m2 = QLabel("38,50 m²")
        self.lbl_floor_tot_m2.setStyleSheet("font-size: 15px; font-weight: bold;")
        grid.addWidget(self.lbl_floor_tot_m2, 0, 1)

        grid.addWidget(QLabel("Metragem Total Comprada:"), 1, 0)
        self.lbl_floor_bought_m2 = QLabel("38,88 m²")
        grid.addWidget(self.lbl_floor_bought_m2, 1, 1)

        grid.addWidget(QLabel("Argamassa Necessária (Sacos 20kg):"), 2, 0)
        self.lbl_floor_mortar = QLabel("10 sacos")
        self.lbl_floor_mortar.setStyleSheet("font-size: 15px; font-weight: bold; color: #ea580c;")
        grid.addWidget(self.lbl_floor_mortar, 2, 1)

        grid.addWidget(QLabel("Rejunte Estimado:"), 3, 0)
        self.lbl_floor_grout = QLabel("19,25 kg")
        self.lbl_floor_grout.setStyleSheet("font-size: 15px; font-weight: bold; color: #0284c7;")
        grid.addWidget(self.lbl_floor_grout, 3, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_flooring()
        return page

    def _recalc_flooring(self) -> None:
        area = self.spn_floor_area.value()
        perda = self.cmb_floor_layout.currentData()
        box_m2 = self.spn_floor_box_m2.value()

        res = calculate_flooring_materials(area, perda, box_m2)
        self.lbl_floor_boxes.setText(f"{res['caixas_necessarias']} caixa(s)")
        self.lbl_floor_tot_m2.setText(f"{res['area_total_m2']:.2f} m²")
        self.lbl_floor_bought_m2.setText(f"{res['total_m2_comprado']:.2f} m²")
        self.lbl_floor_mortar.setText(f"{res['sacos_argamassa_20kg']} saco(s) de 20kg")
        self.lbl_floor_grout.setText(f"{res['kg_rejunte']:.2f} kg")

    # -------------------------------------------------------------
    # ABA CONCRETO & CONTRAPISO
    # -------------------------------------------------------------
    def _build_concrete_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)

        form_frame = QFrame()
        form_frame.setFixedWidth(340)
        v_form = QVBoxLayout(form_frame)
        f_layout = QFormLayout()

        self.spn_conc_area = QDoubleSpinBox()
        self.spn_conc_area.setRange(0.5, 50000.0)
        self.spn_conc_area.setValue(20.0)
        self.spn_conc_area.setSuffix(" m²")
        self.spn_conc_area.valueChanged.connect(self._recalc_concrete)
        f_layout.addRow("Área da Laje / Contrapiso:", self.spn_conc_area)

        self.spn_conc_esp = QDoubleSpinBox()
        self.spn_conc_esp.setRange(1.0, 50.0)
        self.spn_conc_esp.setValue(5.0)
        self.spn_conc_esp.setSuffix(" cm")
        self.spn_conc_esp.valueChanged.connect(self._recalc_concrete)
        f_layout.addRow("Espessura da Camada:", self.spn_conc_esp)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        layout.addWidget(form_frame)

        # Resultados de concreto
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        card_vol = QFrame()
        card_vol.setStyleSheet("background-color: rgba(2, 132, 199, 0.15); border-radius: 6px; padding: 12px;")
        v_vol = QVBoxLayout(card_vol)
        v_vol.addWidget(QLabel("VOLUME TOTAL DE CONCRETO:"))
        self.lbl_conc_vol = QLabel("1,000 m³")
        self.lbl_conc_vol.setStyleSheet("font-size: 26px; font-weight: bold; color: #0284c7;")
        v_vol.addWidget(self.lbl_conc_vol)
        v_res.addWidget(card_vol)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Cimento (Sacos de 50 kg):"), 0, 0)
        self.lbl_conc_cimento = QLabel("7 sacos")
        self.lbl_conc_cimento.setStyleSheet("font-size: 15px; font-weight: bold;")
        grid.addWidget(self.lbl_conc_cimento, 0, 1)

        grid.addWidget(QLabel("Areia Média / Grossa:"), 1, 0)
        self.lbl_conc_areia = QLabel("0,65 m³")
        self.lbl_conc_areia.setStyleSheet("font-size: 15px; font-weight: bold;")
        grid.addWidget(self.lbl_conc_areia, 1, 1)

        grid.addWidget(QLabel("Pedra Brita nº 1:"), 2, 0)
        self.lbl_conc_brita = QLabel("0,85 m³")
        self.lbl_conc_brita.setStyleSheet("font-size: 15px; font-weight: bold;")
        grid.addWidget(self.lbl_conc_brita, 2, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        layout.addWidget(res_frame, 1)

        self._recalc_concrete()
        return page

    def _recalc_concrete(self) -> None:
        area = self.spn_conc_area.value()
        esp = self.spn_conc_esp.value()

        res = calculate_concrete_volume(area, esp)
        self.lbl_conc_vol.setText(f"{res['volume_m3']:.3f} m³")
        self.lbl_conc_cimento.setText(f"{res['sacos_cimento_50kg']} saco(s) de 50kg")
        self.lbl_conc_areia.setText(f"{res['areia_m3']:.2f} m³")
        self.lbl_conc_brita.setText(f"{res['brita_m3']:.2f} m³")
