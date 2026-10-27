"""
Interface de usuário para a Calculadora de Telas, PPI e Escala do Windows.
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
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.calc.screen.logic import (
    calculate_screen_metrics,
)

PRESET_RESOLUTIONS = [
    ("Personalizado", 0, 0),
    ("Full HD 1080p (1920 × 1080)", 1920, 1080),
    ("QHD / 2.5K 1440p (2560 × 1440)", 2560, 1440),
    ("4K Ultra HD (3840 × 2160)", 3840, 2160),
    ("Ultrawide UWQHD (3440 × 1440)", 3440, 1440),
    ("Super Ultrawide (5120 × 1440)", 5120, 1440),
    ("HD+ Notebook (1366 × 768)", 1366, 768),
    ("Full HD+ 16:10 (1920 × 1200)", 1920, 1200),
    ("QHD+ 16:10 (2560 × 1600)", 2560, 1600),
    ("Microsoft Surface 3:2 (2880 × 1920)", 2880, 1920),
]

PRESET_DIAGONALS = [
    ("Personalizado", 0.0),
    ('Notebook 13,3" (Portátil)', 13.3),
    ('Notebook 14,0" (Corporativo)', 14.0),
    ('Notebook 15,6" (Padrão)', 15.6),
    ('Notebook 16,0" (Produtividade)', 16.0),
    ('Monitor 21,5" (Escritório)', 21.5),
    ('Monitor 23,8" / 24" (Desktop)', 23.8),
    ('Monitor 27,0" (Gamer / Pro)', 27.0),
    ('Monitor 31,5" / 32" (Grande)', 31.5),
    ('Monitor 34,0" (Ultrawide Curvo)', 34.0),
    ('Televisor 55,0" (Sala)', 55.0),
]


@register
class ScreenCalcTool(Tool):
    """Calculadora de densidade de pixels (PPI), proporção de tela e escala recomendada de DPI no Windows."""

    id = "calc.screen"
    name = "Calculadora de Telas & Monitores (PPI & Proporção)"
    description = "Calcule densidade de pixels (PPI), proporção dimensional (Aspect Ratio), tamanho físico em cm e escala ideal do Windows."
    category = "calc"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Cabeçalho
        title = QLabel("Calculadora de Telas, PPI & Escala de Exibição")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Análise dimensional de displays, cálculo exato de densidade de pixels (PPI) e recomendação de DPI no Windows 11."
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

        self.cmb_res_preset = QComboBox()
        for name, w, h in PRESET_RESOLUTIONS:
            self.cmb_res_preset.addItem(name, (w, h))
        self.cmb_res_preset.setCurrentIndex(2)  # QHD
        self.cmb_res_preset.currentIndexChanged.connect(self._on_res_preset_changed)
        f_layout.addRow("Resolução Pré-definida:", self.cmb_res_preset)

        res_box = QHBoxLayout()
        self.spn_w = QSpinBox()
        self.spn_w.setRange(100, 30000)
        self.spn_w.setValue(2560)
        self.spn_w.valueChanged.connect(self._recalculate)
        self.spn_h = QSpinBox()
        self.spn_h.setRange(100, 30000)
        self.spn_h.setValue(1440)
        self.spn_h.valueChanged.connect(self._recalculate)
        res_box.addWidget(self.spn_w)
        res_box.addWidget(QLabel("×"))
        res_box.addWidget(self.spn_h)
        res_box.addWidget(QLabel("px"))
        f_layout.addRow("Dimensão em Pixels:", res_box)

        self.cmb_diag_preset = QComboBox()
        for name, d in PRESET_DIAGONALS:
            self.cmb_diag_preset.addItem(name, d)
        self.cmb_diag_preset.setCurrentIndex(7)  # 27"
        self.cmb_diag_preset.currentIndexChanged.connect(self._on_diag_preset_changed)
        f_layout.addRow("Tamanho de Tela Popular:", self.cmb_diag_preset)

        self.spn_diag = QDoubleSpinBox()
        self.spn_diag.setRange(1.0, 200.0)
        self.spn_diag.setValue(27.0)
        self.spn_diag.setDecimals(1)
        self.spn_diag.setSuffix(' " polegadas')
        self.spn_diag.valueChanged.connect(self._recalculate)
        f_layout.addRow("Diagonal Exata:", self.spn_diag)

        v_form.addLayout(f_layout)
        v_form.addStretch()
        main_box.addWidget(form_frame)

        # Painel Direito: Resultados
        res_frame = QFrame()
        res_frame.setStyleSheet(
            "QFrame { background-color: rgba(128, 128, 128, 0.08); border-radius: 8px; padding: 15px; }"
        )
        v_res = QVBoxLayout(res_frame)
        v_res.setSpacing(12)

        # Card PPI
        card_ppi = QFrame()
        card_ppi.setStyleSheet("background-color: rgba(2, 132, 199, 0.15); border-radius: 6px; padding: 12px;")
        v_p = QVBoxLayout(card_ppi)
        v_p.addWidget(QLabel("DENSIDADE DE PIXELS (PPI):"))
        self.lbl_ppi = QLabel("108,79 PPI")
        self.lbl_ppi.setStyleSheet("font-size: 26px; font-weight: bold; color: #0284c7;")
        v_p.addWidget(self.lbl_ppi)
        self.lbl_ppi_clarity = QLabel("Excelente equilíbrio para visualização confortável em 100% de escala")
        self.lbl_ppi_clarity.setStyleSheet("color: #888888; font-size: 11px;")
        v_p.addWidget(self.lbl_ppi_clarity)
        v_res.addWidget(card_ppi)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Proporção de Tela (Aspect Ratio):"), 0, 0)
        self.lbl_ratio = QLabel("16:9 (Widescreen)")
        self.lbl_ratio.setStyleSheet("font-size: 15px; font-weight: bold;")
        grid.addWidget(self.lbl_ratio, 0, 1)

        grid.addWidget(QLabel("Escala Recomendada no Windows:"), 1, 0)
        self.lbl_win_scale = QLabel("100% (Padrão)")
        self.lbl_win_scale.setStyleSheet("font-size: 15px; font-weight: bold; color: #16a34a;")
        grid.addWidget(self.lbl_win_scale, 1, 1)

        grid.addWidget(QLabel("Largura Física da Tela:"), 2, 0)
        self.lbl_phys_w = QLabel("59,77 cm")
        grid.addWidget(self.lbl_phys_w, 2, 1)

        grid.addWidget(QLabel("Altura Física da Tela:"), 3, 0)
        self.lbl_phys_h = QLabel("33,62 cm")
        grid.addWidget(self.lbl_phys_h, 3, 1)

        grid.addWidget(QLabel("Área de Exibição Útil:"), 4, 0)
        self.lbl_phys_area = QLabel("2.009,47 cm²")
        grid.addWidget(self.lbl_phys_area, 4, 1)

        grid.addWidget(QLabel("Resolução Total:"), 5, 0)
        self.lbl_tot_pixels = QLabel("3,69 Megapixels")
        grid.addWidget(self.lbl_tot_pixels, 5, 1)

        v_res.addLayout(grid)
        v_res.addStretch()
        main_box.addWidget(res_frame, 1)

        layout.addLayout(main_box, 1)

        self._recalculate()
        return widget

    def _on_res_preset_changed(self) -> None:
        val = self.cmb_res_preset.currentData()
        if val and val[0] > 0:
            self.spn_w.setValue(val[0])
            self.spn_h.setValue(val[1])

    def _on_diag_preset_changed(self) -> None:
        val = self.cmb_diag_preset.currentData()
        if val and val > 0:
            self.spn_diag.setValue(val)

    def _recalculate(self) -> None:
        w = self.spn_w.value()
        h = self.spn_h.value()
        d = self.spn_diag.value()

        res = calculate_screen_metrics(w, h, d)
        self.lbl_ppi.setText(f"{res['ppi']:.2f} PPI")
        self.lbl_ratio.setText(res["aspect_ratio"])
        self.lbl_win_scale.setText(res["escala_windows_sugerida"])
        self.lbl_phys_w.setText(f"{res['largura_cm']:.2f} cm")
        self.lbl_phys_h.setText(f"{res['altura_cm']:.2f} cm")
        self.lbl_phys_area.setText(f"{res['area_cm2']:,.2f} cm²".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_tot_pixels.setText(f"{res['total_pixels_mp']:.2f} Megapixels ({w}×{h})")

        if res["ppi"] >= 200:
            self.lbl_ppi_clarity.setText("Nitidez ultra-alta estilo Retina Display (necessita escala no Windows)")
        elif res["ppi"] >= 130:
            self.lbl_ppi_clarity.setText("Excelente nitidez de texto e detalhes finos")
        else:
            self.lbl_ppi_clarity.setText("Densidade padrão e confortável sem necessidade de escala")
