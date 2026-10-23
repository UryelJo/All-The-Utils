"""
Ferramenta: Aplicador de Marca d'Água em Lote.
Implementação completa com contrato FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QSpinBox,
    QVBoxLayout, QWidget
)

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.watermark.logic import (
    WATERMARK_POSITIONS, apply_watermark_to_image
)

@register
class ImageWatermarkTool(FileTool):
    id = "images.watermark"
    name = "Aplicador de Marca d'Água"
    category = "Imagens"
    description = "Aplique assinaturas de texto ou logos em fotos em lote com controle de transparência e posição"
    keywords = ["marca", "dagua", "watermark", "logo", "assinatura", "copyright", "fotos", "texto", "lote"]
    accepts = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Opções de Marca d'Água")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # 1. Tipo de Marca d'água
        grid.addWidget(QLabel("Tipo de marca:"), 0, 0)
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["Texto", "Imagem (Logo)"])
        self.cmb_type.currentTextChanged.connect(self._on_type_changed)
        grid.addWidget(self.cmb_type, 0, 1)

        # 2. Posição
        grid.addWidget(QLabel("Posicionamento:"), 0, 2)
        self.cmb_pos = QComboBox()
        self.cmb_pos.addItems(WATERMARK_POSITIONS)
        grid.addWidget(self.cmb_pos, 0, 3)

        # --- Seção Texto ---
        self.lbl_text = QLabel("Texto da marca:")
        grid.addWidget(self.lbl_text, 1, 0)
        self.txt_watermark = QLineEdit("© All the Utils")
        grid.addWidget(self.txt_watermark, 1, 1)

        self.lbl_font_size = QLabel("Tamanho da fonte:")
        grid.addWidget(self.lbl_font_size, 1, 2)
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(10, 200)
        self.spin_font_size.setValue(36)
        grid.addWidget(self.spin_font_size, 1, 3)

        self.lbl_color = QLabel("Cor do texto:")
        grid.addWidget(self.lbl_color, 2, 0)
        row_color = QHBoxLayout()
        self.txt_color = QLineEdit("#FFFFFF")
        self.txt_color.setFixedWidth(80)
        btn_pick_color = QPushButton("Escolher...")
        btn_pick_color.clicked.connect(self._pick_color)
        row_color.addWidget(self.txt_color)
        row_color.addWidget(btn_pick_color)
        grid.addLayout(row_color, 2, 1)

        self.lbl_rotation = QLabel("Rotação (-90° a 90°):")
        grid.addWidget(self.lbl_rotation, 2, 2)
        self.spin_rotation = QSpinBox()
        self.spin_rotation.setRange(-90, 90)
        self.spin_rotation.setValue(0)
        self.spin_rotation.setSuffix(" °")
        grid.addWidget(self.spin_rotation, 2, 3)

        # --- Seção Logo/Imagem ---
        self.lbl_logo = QLabel("Arquivo do logo:")
        grid.addWidget(self.lbl_logo, 3, 0)
        row_logo = QHBoxLayout()
        self.txt_logo = QLineEdit()
        self.txt_logo.setPlaceholderText("Selecione um logo PNG transparente...")
        btn_browse_logo = QPushButton("Procurar...")
        btn_browse_logo.clicked.connect(self._browse_logo)
        row_logo.addWidget(self.txt_logo)
        row_logo.addWidget(btn_browse_logo)
        grid.addLayout(row_logo, 3, 1)

        self.lbl_logo_scale = QLabel("Escala do logo (%):")
        grid.addWidget(self.lbl_logo_scale, 3, 2)
        self.spin_logo_scale = QSpinBox()
        self.spin_logo_scale.setRange(5, 80)
        self.spin_logo_scale.setValue(20)
        self.spin_logo_scale.setSuffix(" %")
        grid.addWidget(self.spin_logo_scale, 3, 3)

        # --- Seção Comum: Opacidade e Margem ---
        self.lbl_opacity = QLabel("Opacidade (50%):")
        grid.addWidget(self.lbl_opacity, 4, 0)
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(5, 100)
        self.slider_opacity.setValue(50)
        self.slider_opacity.valueChanged.connect(
            lambda v: self.lbl_opacity.setText(f"Opacidade ({v}%):")
        )
        grid.addWidget(self.slider_opacity, 4, 1)

        grid.addWidget(QLabel("Margem da borda:"), 4, 2)
        self.spin_margin = QSpinBox()
        self.spin_margin.setRange(0, 300)
        self.spin_margin.setValue(25)
        self.spin_margin.setSuffix(" px")
        grid.addWidget(self.spin_margin, 4, 3)

        layout.addLayout(grid)
        self._on_type_changed(self.cmb_type.currentText())

        return panel

    def _on_type_changed(self, wm_type: str):
        is_text = wm_type == "Texto"

        self.lbl_text.setVisible(is_text)
        self.txt_watermark.setVisible(is_text)
        self.lbl_font_size.setVisible(is_text)
        self.spin_font_size.setVisible(is_text)
        self.lbl_color.setVisible(is_text)
        self.txt_color.setVisible(is_text)
        self.lbl_rotation.setVisible(is_text)
        self.spin_rotation.setVisible(is_text)

        self.lbl_logo.setVisible(not is_text)
        self.txt_logo.setVisible(not is_text)
        self.lbl_logo_scale.setVisible(not is_text)
        self.spin_logo_scale.setVisible(not is_text)

    def _pick_color(self):
        col = QColorDialog.getColor()
        if col.isValid():
            self.txt_color.setText(col.name().upper())

    def _browse_logo(self):
        f, _ = QFileDialog.getOpenFileName(
            self.txt_logo,
            "Selecionar Logo de Imagem",
            "",
            "Imagens (*.png *.webp *.jpg *.jpeg *.bmp)"
        )
        if f:
            self.txt_logo.setText(f)

    def get_options(self) -> Dict[str, Any]:
        return {
            "type": self.cmb_type.currentText(),
            "position": self.cmb_pos.currentText(),
            "text": self.txt_watermark.text().strip(),
            "font_size": self.spin_font_size.value(),
            "color": self.txt_color.text().strip(),
            "rotation": self.spin_rotation.value(),
            "logo_path": self.txt_logo.text().strip(),
            "logo_scale": self.spin_logo_scale.value(),
            "opacity": self.slider_opacity.value(),
            "margin": self.spin_margin.value()
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        return ""

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            apply_watermark_to_image(src, dst, params)
            return ItemResult(
                success=True,
                src=src,
                dst=dst,
                message="Marca d'água aplicada com sucesso"
            )
        except Exception as e:
            return ItemResult(
                success=False,
                src=src,
                dst=dst,
                message=f"Erro ao aplicar marca d'água: {str(e)}"
            )
