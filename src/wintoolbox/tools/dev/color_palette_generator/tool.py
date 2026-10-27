"""
Interface gráfica da ferramenta Gerador de Paletas Harmônicas e Contraste WCAG (dev.color_palette_generator).
Permite criar paletas (Complementar, Análoga, Triádica, Monocromática),
avaliar contraste de acessibilidade e exportar variáveis CSS/SCSS em 1 clique.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.dev.color_palette_generator.logic import (
    export_palette_code,
    generate_palette,
)


@register
class ColorPaletteGeneratorTool(Tool):
    id = "dev.color_palette_generator"
    name = "Gerador de Paletas Harmônicas e WCAG"
    category = "Desenvolvedores"
    description = (
        "Gera paletas de cores harmônicas (Complementar, Análoga, Triádica, Monocromática) "
        "com teste de contraste e acessibilidade WCAG 2.1 e exportação de variáveis CSS."
    )
    keywords = ["cores", "paleta", "harmonia", "wcag", "contraste", "acessibilidade", "css", "hex", "rgb", "hsl"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ColorPaletteGeneratorView(self, parent)


class ColorPaletteGeneratorView(QWidget):
    def __init__(self, tool: ColorPaletteGeneratorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_palette = []
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937;")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        root_layout.addWidget(lbl_desc)

        # Barra Superior: Cor Base e Modo de Harmonia
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Cor Base:"))

        self._color_preview_btn = QPushButton()
        self._color_preview_btn.setFixedSize(32, 26)
        self._color_preview_btn.setStyleSheet("background-color: #3B82F6; border: 1px solid #ccc; border-radius: 4px;")
        self._color_preview_btn.clicked.connect(self._pick_color)
        top_bar.addWidget(self._color_preview_btn)

        self._txt_hex = QLineEdit("#3B82F6")
        self._txt_hex.setFixedWidth(90)
        self._txt_hex.setFont(QFont("Consolas", 10))
        self._txt_hex.textChanged.connect(self._on_hex_text_changed)
        top_bar.addWidget(self._txt_hex)

        top_bar.addWidget(QLabel("Harmonia:"))
        self._combo_harmony = QComboBox()
        self._combo_harmony.addItem("Complementar (180°)", "complementary")
        self._combo_harmony.addItem("Análoga (±30°)", "analogous")
        self._combo_harmony.addItem("Triádica (120°)", "triadic")
        self._combo_harmony.addItem("Tétrade (90°)", "tetradic")
        self._combo_harmony.addItem("Monocromática (Variações)", "monochromatic")
        self._combo_harmony.addItem("Split-Complementar (150°/210°)", "split_complementary")
        self._combo_harmony.currentIndexChanged.connect(self._generate)
        top_bar.addWidget(self._combo_harmony)

        top_bar.addStretch()

        btn_copy_css = QPushButton("Copiar Variáveis CSS")
        btn_copy_css.clicked.connect(self._copy_css)
        top_bar.addWidget(btn_copy_css)

        root_layout.addLayout(top_bar)

        # Área de Exibição dos Swatches de Cores da Paleta
        self._swatches_container = QWidget()
        self._swatches_layout = QHBoxLayout(self._swatches_container)
        self._swatches_layout.setContentsMargins(0, 8, 0, 8)
        self._swatches_layout.setSpacing(12)

        root_layout.addWidget(self._swatches_container)

        # Painel Inferior: Código Exportado
        group_code = QGroupBox("Código da Paleta (CSS / SCSS / JSON)")
        code_layout = QVBoxLayout(group_code)
        self._txt_code = QPlainTextEdit()
        self._txt_code.setFont(QFont("Consolas", 9))
        self._txt_code.setReadOnly(True)
        code_layout.addWidget(self._txt_code)
        root_layout.addWidget(group_code)

        # Gera paleta inicial
        self._generate()

    def _pick_color(self):
        cur_color = QColor(self._txt_hex.text().strip())
        color = QColorDialog.getColor(cur_color, self, "Selecionar Cor Base")
        if color.isValid():
            hex_str = color.name().upper()
            self._txt_hex.setText(hex_str)

    def _on_hex_text_changed(self, text: str):
        clean = text.strip()
        if len(clean) in (4, 7) and clean.startswith("#"):
            self._color_preview_btn.setStyleSheet(f"background-color: {clean}; border: 1px solid #ccc; border-radius: 4px;")
            self._generate()

    def _generate(self):
        hex_val = self._txt_hex.text().strip()
        mode = self._combo_harmony.currentData()
        try:
            palette = generate_palette(hex_val, harmony_mode=mode)
            self._current_palette = palette
            self._render_swatches(palette)
            css_code = export_palette_code(palette, format_type="css")
            self._txt_code.setPlainText(css_code)
        except Exception:
            pass

    def _render_swatches(self, palette: list):
        # Limpa widgets anteriores
        while self._swatches_layout.count():
            item = self._swatches_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for col in palette:
            card = QFrame()
            card.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; }")
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(8, 8, 8, 8)
            c_layout.setSpacing(6)

            # Bloco de cor visual
            swatch = QLabel()
            swatch.setFixedHeight(80)
            swatch.setStyleSheet(f"background-color: {col['hex']}; border-radius: 6px;")
            c_layout.addWidget(swatch)

            lbl_name = QLabel(col["label"])
            lbl_name.setStyleSheet("font-weight: bold; font-size: 11px; color: #1f2937;")
            c_layout.addWidget(lbl_name)

            lbl_hex = QLabel(col["hex"])
            lbl_hex.setFont(QFont("Consolas", 10))
            c_layout.addWidget(lbl_hex)

            lbl_rgb = QLabel(col["rgb"])
            lbl_rgb.setStyleSheet("color: #6b7280; font-size: 10px;")
            c_layout.addWidget(lbl_rgb)

            # Badges WCAG
            wcag_text = f"Branco: {col['contrast_on_white']} | Preto: {col['contrast_on_black']}"
            lbl_wcag = QLabel(wcag_text)
            lbl_wcag.setStyleSheet("font-size: 9px; color: #4b5563;")
            c_layout.addWidget(lbl_wcag)

            btn_copy = QPushButton("Copiar HEX")
            btn_copy.clicked.connect(lambda checked=False, h=col["hex"]: self._copy_text(h))
            c_layout.addWidget(btn_copy)

            self._swatches_layout.addWidget(card)

    def _copy_text(self, text: str):
        QGuiApplication.clipboard().setText(text)

    def _copy_css(self):
        txt = self._txt_code.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)
