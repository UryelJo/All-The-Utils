"""
Interface gráfica do Conversor de Cores para Desenvolvedores.
"""
from typing import Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QSpinBox,
    QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.color_converter.logic import (
    cmyk_to_rgb, get_all_color_formats, hsl_to_rgb, parse_hex_color,
    rgb_to_cmyk, rgb_to_hex, rgb_to_hsl, rgb_to_hsv
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("dev.color_converter.ui")


@register
class ColorConverterTool(Tool):
    id = "dev.color_converter"
    name = "Conversor de Cores"
    category = "Desenvolvimento"
    description = "Conversão instantânea entre HEX, RGB, HSL, HSV, CMYK, snippets de código dev e análise de contraste WCAG"
    keywords = ["cor", "color", "hex", "rgb", "hsl", "hsv", "cmyk", "wcag", "contraste", "paleta", "css", "dev"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ColorConverterView(self, parent)


class ColorConverterView(QWidget):
    def __init__(self, tool: ColorConverterTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._updating = False

        # Estado da cor atual (R, G, B, Alpha)
        self._r = 37
        self._g = 99
        self._b = 235
        self._a = 1.0

        self._snippet_labels: Dict[str, QLineEdit] = {}
        self._build_ui()
        self._refresh_from_rgb()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(ToolHeader(
            "Conversor de Cores",
            "Conversão matemática bidirecional entre formatos de cores com métricas de contraste WCAG 2.1 e snippets de código."
        ))

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Coluna da Esquerda: Controles de Cor
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        # 1. Preview da Cor e Seletor do Sistema
        preview_box = QGroupBox("Visualização da Cor")
        prev_layout = QVBoxLayout(preview_box)
        prev_layout.setSpacing(8)

        self.color_preview = QFrame()
        self.color_preview.setFixedHeight(90)
        self.color_preview.setStyleSheet("border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.15);")
        
        # Testes de legibilidade de texto sobre a cor
        prev_inner = QHBoxLayout(self.color_preview)
        prev_inner.setContentsMargins(16, 8, 16, 8)
        self.lbl_prev_white = QLabel("Texto Branco (Aa 123)")
        self.lbl_prev_white.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 13px; background: transparent;")
        self.lbl_prev_black = QLabel("Texto Preto (Aa 123)")
        self.lbl_prev_black.setStyleSheet("color: #000000; font-weight: bold; font-size: 13px; background: transparent;")
        prev_inner.addWidget(self.lbl_prev_white, alignment=Qt.AlignmentFlag.AlignCenter)
        prev_inner.addWidget(self.lbl_prev_black, alignment=Qt.AlignmentFlag.AlignCenter)

        prev_layout.addWidget(self.color_preview)

        btn_pick = QPushButton("Selecionar no Diálogo do Sistema...")
        btn_pick.clicked.connect(self._on_pick_system_color)
        prev_layout.addWidget(btn_pick)

        left_col.addWidget(preview_box)

        # 2. Entradas Numéricas (HEX, RGB, HSL)
        inputs_box = QGroupBox("Canais e Notações")
        grid = QGridLayout(inputs_box)
        grid.setSpacing(8)

        # HEX
        grid.addWidget(QLabel("HEX:"), 0, 0)
        self.edit_hex = QLineEdit("#2563EB")
        self.edit_hex.setFont(QFont("Cascadia Mono", 10))
        self.edit_hex.textEdited.connect(self._on_hex_edited)
        grid.addWidget(self.edit_hex, 0, 1, 1, 2)

        # Vermelho (R)
        grid.addWidget(QLabel("R (Vermelho):"), 1, 0)
        self.slider_r = QSlider(Qt.Orientation.Horizontal)
        self.slider_r.setRange(0, 255)
        self.spin_r = QSpinBox()
        self.spin_r.setRange(0, 255)
        self.slider_r.valueChanged.connect(self.spin_r.setValue)
        self.spin_r.valueChanged.connect(self.slider_r.setValue)
        self.slider_r.valueChanged.connect(self._on_rgb_slider_changed)
        grid.addWidget(self.slider_r, 1, 1)
        grid.addWidget(self.spin_r, 1, 2)

        # Verde (G)
        grid.addWidget(QLabel("G (Verde):"), 2, 0)
        self.slider_g = QSlider(Qt.Orientation.Horizontal)
        self.slider_g.setRange(0, 255)
        self.spin_g = QSpinBox()
        self.spin_g.setRange(0, 255)
        self.slider_g.valueChanged.connect(self.spin_g.setValue)
        self.spin_g.valueChanged.connect(self.slider_g.setValue)
        self.slider_g.valueChanged.connect(self._on_rgb_slider_changed)
        grid.addWidget(self.slider_g, 2, 1)
        grid.addWidget(self.spin_g, 2, 2)

        # Azul (B)
        grid.addWidget(QLabel("B (Azul):"), 3, 0)
        self.slider_b = QSlider(Qt.Orientation.Horizontal)
        self.slider_b.setRange(0, 255)
        self.spin_b = QSpinBox()
        self.spin_b.setRange(0, 255)
        self.slider_b.valueChanged.connect(self.spin_b.setValue)
        self.spin_b.valueChanged.connect(self.slider_b.setValue)
        self.slider_b.valueChanged.connect(self._on_rgb_slider_changed)
        grid.addWidget(self.slider_b, 3, 1)
        grid.addWidget(self.spin_b, 3, 2)

        # HSL - Hue
        grid.addWidget(QLabel("H (Matiz 0-360):"), 4, 0)
        self.slider_h = QSlider(Qt.Orientation.Horizontal)
        self.slider_h.setRange(0, 360)
        self.spin_h = QSpinBox()
        self.spin_h.setRange(0, 360)
        self.slider_h.valueChanged.connect(self.spin_h.setValue)
        self.spin_h.valueChanged.connect(self.slider_h.setValue)
        self.slider_h.valueChanged.connect(self._on_hsl_slider_changed)
        grid.addWidget(self.slider_h, 4, 1)
        grid.addWidget(self.spin_h, 4, 2)

        # HSL - Saturation
        grid.addWidget(QLabel("S (Saturação %):"), 5, 0)
        self.slider_s = QSlider(Qt.Orientation.Horizontal)
        self.slider_s.setRange(0, 100)
        self.spin_s = QSpinBox()
        self.spin_s.setRange(0, 100)
        self.slider_s.valueChanged.connect(self.spin_s.setValue)
        self.spin_s.valueChanged.connect(self.slider_s.setValue)
        self.slider_s.valueChanged.connect(self._on_hsl_slider_changed)
        grid.addWidget(self.slider_s, 5, 1)
        grid.addWidget(self.spin_s, 5, 2)

        # HSL - Lightness
        grid.addWidget(QLabel("L (Luminosidade %):"), 6, 0)
        self.slider_l = QSlider(Qt.Orientation.Horizontal)
        self.slider_l.setRange(0, 100)
        self.spin_l = QSpinBox()
        self.spin_l.setRange(0, 100)
        self.slider_l.valueChanged.connect(self.spin_l.setValue)
        self.spin_l.valueChanged.connect(self.slider_l.setValue)
        self.slider_l.valueChanged.connect(self._on_hsl_slider_changed)
        grid.addWidget(self.slider_l, 6, 1)
        grid.addWidget(self.spin_l, 6, 2)

        left_col.addWidget(inputs_box)
        left_col.addStretch(1)

        content_layout.addLayout(left_col, stretch=1)

        # Coluna da Direita: Acessibilidade WCAG e Snippets
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        # Box WCAG
        wcag_box = QGroupBox("Acessibilidade WCAG 2.1")
        wcag_layout = QVBoxLayout(wcag_box)
        wcag_layout.setSpacing(6)

        self.lbl_wcag_white = QLabel("Contraste com Branco (#FFFFFF): Calculando...")
        self.lbl_wcag_black = QLabel("Contraste com Preto (#000000): Calculando...")
        wcag_layout.addWidget(self.lbl_wcag_white)
        wcag_layout.addWidget(self.lbl_wcag_black)
        right_col.addWidget(wcag_box)

        # Box Snippets de Código
        snippets_box = QGroupBox("Snippets Prontos para Código")
        snip_layout = QGridLayout(snippets_box)
        snip_layout.setSpacing(8)

        snippet_keys = [
            "CSS HEX", "CSS RGB", "CSS HSL", "Tailwind",
            "Python (RGB)", "Normalized", "Android / Flutter (HEX)", "Unity C#"
        ]

        for row, key in enumerate(snippet_keys):
            snip_layout.addWidget(QLabel(f"{key}:"), row, 0)
            line_edit = QLineEdit()
            line_edit.setReadOnly(True)
            line_edit.setFont(QFont("Cascadia Mono", 9))
            self._snippet_labels[key] = line_edit
            snip_layout.addWidget(line_edit, row, 1)

            btn_copy = QPushButton("Copiar")
            btn_copy.setFixedWidth(65)
            btn_copy.clicked.connect(lambda checked=False, k=key: self._copy_snippet(k))
            snip_layout.addWidget(btn_copy, row, 2)

        right_col.addWidget(snippets_box, stretch=1)

        content_layout.addLayout(right_col, stretch=1)
        root.addLayout(content_layout, stretch=1)

    def _refresh_from_rgb(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            r, g, b, a = self._r, self._g, self._b, self._a
            data = get_all_color_formats(r, g, b, a)

            # Atualiza visual do Frame
            self.color_preview.setStyleSheet(
                f"background-color: {data['hex']}; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.15);"
            )

            # Inputs RGB
            self.slider_r.setValue(r)
            self.spin_r.setValue(r)
            self.slider_g.setValue(g)
            self.spin_g.setValue(g)
            self.slider_b.setValue(b)
            self.spin_b.setValue(b)

            # Inputs HEX
            self.edit_hex.setText(data["hex"])

            # Inputs HSL
            h, s, l = data["hsl"]
            self.slider_h.setValue(h)
            self.spin_h.setValue(h)
            self.slider_s.setValue(s)
            self.spin_s.setValue(s)
            self.slider_l.setValue(l)
            self.spin_l.setValue(l)

            # WCAG
            cw = data["contrast_white"]
            cb = data["contrast_black"]
            pass_white = "Aprovado (AA)" if cw >= 4.5 else "Reprovado (< 4.5)"
            pass_black = "Aprovado (AA)" if cb >= 4.5 else "Reprovado (< 4.5)"

            self.lbl_wcag_white.setText(f"Contraste com Branco (#FFFFFF): {cw:.2f}:1 — {pass_white}")
            self.lbl_wcag_black.setText(f"Contraste com Preto (#000000): {cb:.2f}:1 — {pass_black}")

            # Snippets
            for k, val in data["code_snippets"].items():
                if k in self._snippet_labels:
                    self._snippet_labels[k].setText(str(val))

        finally:
            self._updating = False

    def _on_rgb_slider_changed(self) -> None:
        if self._updating:
            return
        self._r = self.slider_r.value()
        self._g = self.slider_g.value()
        self._b = self.slider_b.value()
        self._refresh_from_rgb()

    def _on_hsl_slider_changed(self) -> None:
        if self._updating:
            return
        h = self.slider_h.value()
        s = self.slider_s.value()
        l = self.slider_l.value()
        r, g, b = hsl_to_rgb(h, s, l)
        self._r, self._g, self._b = r, g, b
        self._refresh_from_rgb()

    def _on_hex_edited(self, text: str) -> None:
        if self._updating:
            return
        clean = text.strip()
        if not clean.startswith("#"):
            clean = "#" + clean
        if len(clean) in (4, 7, 9):
            try:
                r, g, b, a = parse_hex_color(clean)
                self._r, self._g, self._b, self._a = r, g, b, a
                self._refresh_from_rgb()
            except Exception:
                pass

    def _on_pick_system_color(self) -> None:
        initial = QColor(self._r, self._g, self._b)
        col = QColorDialog.getColor(initial, self, "Escolher Cor")
        if col.isValid():
            self._r = col.red()
            self._g = col.green()
            self._b = col.blue()
            self._refresh_from_rgb()

    def _copy_snippet(self, key: str) -> None:
        if key in self._snippet_labels:
            val = self._snippet_labels[key].text()
            if val:
                QApplication.clipboard().setText(val)
                show_toast(self, f"Snippet {key} copiado!", duration_ms=1800)
