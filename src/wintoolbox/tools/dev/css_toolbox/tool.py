"""
Interface de usuário para a ferramenta CSS Developer Toolbox.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.css_toolbox.logic import (
    calculate_contrast_ratio,
    calculate_fluid_clamp,
    generate_box_shadow_css,
    px_to_rem,
    rem_to_px,
)


@register
class CssToolboxTool(Tool):
    """Ferramentas utilitárias visuais de CSS para desenvolvedores web modernos."""

    id = "dev.css_toolbox"
    name = "CSS Developer Toolbox"
    description = "Gerador visual de gradientes, sombras multicamadas (box-shadow), cálculo de clamp() fluido, conversor px/rem e contraste WCAG."
    category = "dev"

    def build_view(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cabeçalho
        title = QLabel("CSS Developer Toolbox")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        desc = QLabel(
            "Conjunto de ferramentas para front-end: tipografia fluida com clamp(), "
            "gerador de sombras box-shadow, auditoria de acessibilidade WCAG e conversão de unidades."
        )
        desc.setStyleSheet("color: #888888;")
        layout.addWidget(title)
        layout.addWidget(desc)

        tabs = QTabWidget()

        # Aba 1: Clamp Fluido
        tab_clamp = QWidget()
        v_clamp = QVBoxLayout(tab_clamp)
        grid_clamp = QGridLayout()

        grid_clamp.addWidget(QLabel("Tamanho Mínimo (px):"), 0, 0)
        self.spin_min_sz = QDoubleSpinBox()
        self.spin_min_sz.setRange(8, 200)
        self.spin_min_sz.setValue(16.0)
        grid_clamp.addWidget(self.spin_min_sz, 0, 1)

        grid_clamp.addWidget(QLabel("Tamanho Máximo (px):"), 0, 2)
        self.spin_max_sz = QDoubleSpinBox()
        self.spin_max_sz.setRange(8, 200)
        self.spin_max_sz.setValue(32.0)
        grid_clamp.addWidget(self.spin_max_sz, 0, 3)

        grid_clamp.addWidget(QLabel("Viewport Mínima (px):"), 1, 0)
        self.spin_min_vp = QDoubleSpinBox()
        self.spin_min_vp.setRange(200, 3840)
        self.spin_min_vp.setValue(320.0)
        grid_clamp.addWidget(self.spin_min_vp, 1, 1)

        grid_clamp.addWidget(QLabel("Viewport Máxima (px):"), 1, 2)
        self.spin_max_vp = QDoubleSpinBox()
        self.spin_max_vp.setRange(200, 3840)
        self.spin_max_vp.setValue(1200.0)
        grid_clamp.addWidget(self.spin_max_vp, 1, 3)

        v_clamp.addLayout(grid_clamp)

        self.txt_clamp_res = QLineEdit()
        self.txt_clamp_res.setReadOnly(True)
        self.txt_clamp_res.setFont(QFont("Consolas", 11))

        btn_copy_clamp = QPushButton("Copiar Expressão clamp()")
        btn_copy_clamp.clicked.connect(lambda: self._copy_text(self.txt_clamp_res.text()))

        self.spin_min_sz.valueChanged.connect(self._recalc_clamp)
        self.spin_max_sz.valueChanged.connect(self._recalc_clamp)
        self.spin_min_vp.valueChanged.connect(self._recalc_clamp)
        self.spin_max_vp.valueChanged.connect(self._recalc_clamp)

        h_clamp_btn = QHBoxLayout()
        h_clamp_btn.addWidget(self.txt_clamp_res, 1)
        h_clamp_btn.addWidget(btn_copy_clamp)
        v_clamp.addLayout(h_clamp_btn)
        v_clamp.addStretch()
        tabs.addTab(tab_clamp, "Tipografia Fluida (clamp)")

        # Aba 2: Conversor PX / REM
        tab_px_rem = QWidget()
        v_px_rem = QVBoxLayout(tab_px_rem)
        grid_conv = QGridLayout()

        grid_conv.addWidget(QLabel("Valor em Pixels (px):"), 0, 0)
        self.spin_px = QDoubleSpinBox()
        self.spin_px.setRange(-2000, 2000)
        self.spin_px.setValue(24.0)
        grid_conv.addWidget(self.spin_px, 0, 1)

        grid_conv.addWidget(QLabel("Valor em REM:"), 0, 2)
        self.spin_rem = QDoubleSpinBox()
        self.spin_rem.setRange(-200, 200)
        self.spin_rem.setValue(1.5)
        self.spin_rem.setDecimals(4)
        grid_conv.addWidget(self.spin_rem, 0, 3)

        grid_conv.addWidget(QLabel("Tamanho Base (1rem = px):"), 1, 0)
        self.spin_base = QDoubleSpinBox()
        self.spin_base.setRange(8, 64)
        self.spin_base.setValue(16.0)
        grid_conv.addWidget(self.spin_base, 1, 1)

        self.spin_px.valueChanged.connect(self._sync_px_to_rem)
        self.spin_rem.valueChanged.connect(self._sync_rem_to_px)
        self.spin_base.valueChanged.connect(self._sync_px_to_rem)

        v_px_rem.addLayout(grid_conv)
        v_px_rem.addStretch()
        tabs.addTab(tab_px_rem, "Conversor PX ↔ REM")

        # Aba 3: Contraste WCAG 2.1
        tab_wcag = QWidget()
        v_wcag = QVBoxLayout(tab_wcag)
        grid_wcag = QGridLayout()

        grid_wcag.addWidget(QLabel("Cor do Texto:"), 0, 0)
        self.txt_fg = QLineEdit("#1E293B")
        self.btn_fg = QPushButton("Escolher...")
        self.btn_fg.clicked.connect(lambda: self._pick_color(self.txt_fg))
        grid_wcag.addWidget(self.txt_fg, 0, 1)
        grid_wcag.addWidget(self.btn_fg, 0, 2)

        grid_wcag.addWidget(QLabel("Cor de Fundo:"), 1, 0)
        self.txt_bg = QLineEdit("#FFFFFF")
        self.btn_bg = QPushButton("Escolher...")
        self.btn_bg.clicked.connect(lambda: self._pick_color(self.txt_bg))
        grid_wcag.addWidget(self.txt_bg, 1, 1)
        grid_wcag.addWidget(self.btn_bg, 1, 2)

        self.lbl_contrast = QLabel("Razão de Contraste: --:1")
        self.lbl_contrast.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.lbl_wcag_badges = QLabel("Nível WCAG: --")

        self.txt_fg.textChanged.connect(self._recalc_contrast)
        self.txt_bg.textChanged.connect(self._recalc_contrast)

        v_wcag.addLayout(grid_wcag)
        v_wcag.addWidget(self.lbl_contrast)
        v_wcag.addWidget(self.lbl_wcag_badges)
        v_wcag.addStretch()
        tabs.addTab(tab_wcag, "Contraste WCAG 2.1")

        # Aba 4: Box-Shadow
        tab_shadow = QWidget()
        v_shadow = QVBoxLayout(tab_shadow)
        grid_sh = QGridLayout()

        grid_sh.addWidget(QLabel("Offset X (px):"), 0, 0)
        self.spin_sh_x = QSpinBox()
        self.spin_sh_x.setRange(-100, 100)
        self.spin_sh_x.setValue(0)
        grid_sh.addWidget(self.spin_sh_x, 0, 1)

        grid_sh.addWidget(QLabel("Offset Y (px):"), 0, 2)
        self.spin_sh_y = QSpinBox()
        self.spin_sh_y.setRange(-100, 100)
        self.spin_sh_y.setValue(8)
        grid_sh.addWidget(self.spin_sh_y, 0, 3)

        grid_sh.addWidget(QLabel("Blur (px):"), 1, 0)
        self.spin_sh_blur = QSpinBox()
        self.spin_sh_blur.setRange(0, 200)
        self.spin_sh_blur.setValue(24)
        grid_sh.addWidget(self.spin_sh_blur, 1, 1)

        grid_sh.addWidget(QLabel("Spread (px):"), 1, 2)
        self.spin_sh_spread = QSpinBox()
        self.spin_sh_spread.setRange(-50, 100)
        self.spin_sh_spread.setValue(-4)
        grid_sh.addWidget(self.spin_sh_spread, 1, 3)

        self.chk_inset = QCheckBox("Sombra Interna (inset)")
        grid_sh.addWidget(self.chk_inset, 2, 0, 1, 2)

        v_shadow.addLayout(grid_sh)

        self.txt_shadow_res = QLineEdit()
        self.txt_shadow_res.setReadOnly(True)
        self.txt_shadow_res.setFont(QFont("Consolas", 11))

        btn_copy_sh = QPushButton("Copiar CSS")
        btn_copy_sh.clicked.connect(lambda: self._copy_text(self.txt_shadow_res.text()))

        self.spin_sh_x.valueChanged.connect(self._recalc_shadow)
        self.spin_sh_y.valueChanged.connect(self._recalc_shadow)
        self.spin_sh_blur.valueChanged.connect(self._recalc_shadow)
        self.spin_sh_spread.valueChanged.connect(self._recalc_shadow)
        self.chk_inset.toggled.connect(self._recalc_shadow)

        h_sh = QHBoxLayout()
        h_sh.addWidget(self.txt_shadow_res, 1)
        h_sh.addWidget(btn_copy_sh)
        v_shadow.addLayout(h_sh)
        v_shadow.addStretch()
        tabs.addTab(tab_shadow, "Sombras (Box-Shadow)")

        layout.addWidget(tabs, 1)

        self._recalc_clamp()
        self._recalc_contrast()
        self._recalc_shadow()
        return widget

    def _recalc_clamp(self):
        try:
            expr = calculate_fluid_clamp(
                min_size_px=self.spin_min_sz.value(),
                max_size_px=self.spin_max_sz.value(),
                min_viewport_px=self.spin_min_vp.value(),
                max_viewport_px=self.spin_max_vp.value()
            )
            self.txt_clamp_res.setText(f"font-size: {expr};")
        except Exception:
            pass

    def _sync_px_to_rem(self):
        self.spin_rem.blockSignals(True)
        val = px_to_rem(self.spin_px.value(), self.spin_base.value())
        self.spin_rem.setValue(val)
        self.spin_rem.blockSignals(False)

    def _sync_rem_to_px(self):
        self.spin_px.blockSignals(True)
        val = rem_to_px(self.spin_rem.value(), self.spin_base.value())
        self.spin_px.setValue(val)
        self.spin_px.blockSignals(False)

    def _pick_color(self, target_line_edit: QLineEdit):
        curr = target_line_edit.text()
        col = QColorDialog.getColor(QColor(curr) if QColor.isValidColor(curr) else QColor("white"))
        if col.isValid():
            target_line_edit.setText(col.name().upper())

    def _recalc_contrast(self):
        fg = self.txt_fg.text().strip()
        bg = self.txt_bg.text().strip()
        try:
            ratio = calculate_contrast_ratio(fg, bg)
            self.lbl_contrast.setText(f"Razão de Contraste: {ratio:.2f}:1")

            aa_norm = "✓ Aprovado" if ratio >= 4.5 else "✗ Reprovado"
            aa_large = "✓ Aprovado" if ratio >= 3.0 else "✗ Reprovado"
            aaa_norm = "✓ Aprovado" if ratio >= 7.0 else "✗ Reprovado"

            color_style = "color: #4caf50;" if ratio >= 4.5 else "color: #f44336;"
            self.lbl_contrast.setStyleSheet(f"font-size: 16px; font-weight: bold; {color_style}")
            self.lbl_wcag_badges.setText(
                f"WCAG AA Normal: {aa_norm}  |  WCAG AA Grande: {aa_large}  |  WCAG AAA Normal: {aaa_norm}"
            )
        except Exception:
            self.lbl_contrast.setText("Razão de Contraste: Cor Inválida")

    def _recalc_shadow(self):
        css = generate_box_shadow_css(
            offset_x=self.spin_sh_x.value(),
            offset_y=self.spin_sh_y.value(),
            blur=self.spin_sh_blur.value(),
            spread=self.spin_sh_spread.value(),
            color_rgba="rgba(0, 0, 0, 0.12)",
            inset=self.chk_inset.isChecked()
        )
        self.txt_shadow_res.setText(css)

    def _copy_text(self, text: str):
        if text:
            QGuiApplication.clipboard().setText(text)
            QMessageBox.information(None, "Copiado", "Código CSS copiado para a área de transferência!")
