"""
Ferramenta: Filtros e Ajustes de Imagem em Lote.
Implementação completa com contrato FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.effects.logic import (
    IMAGE_EFFECTS, apply_image_effects_and_adjustments
)

@register
class ImageEffectsTool(FileTool):
    id = "images.effects"
    name = "Filtros e Ajustes de Imagem"
    category = "Imagens"
    description = "Ajuste brilho, contraste, saturação e aplique filtros artísticos (P&B, sépia, desfoque) em fotos"
    keywords = ["filtros", "ajustes", "brilho", "contraste", "saturacao", "sepia", "preto e branco", "desfoque", "fotos"]
    accepts = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".heic", ".heif", ".avif"]
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Opções de Ajustes e Filtros")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # 1. Filtro Artístico
        grid.addWidget(QLabel("Filtro artístico:"), 0, 0)
        self.cmb_effect = QComboBox()
        self.cmb_effect.addItems(IMAGE_EFFECTS)
        self.cmb_effect.currentTextChanged.connect(self._on_effect_changed)
        grid.addWidget(self.cmb_effect, 0, 1)

        # 2. Raio de Desfoque
        self.lbl_blur = QLabel("Raio de desfoque (px):")
        grid.addWidget(self.lbl_blur, 0, 2)
        self.spin_blur = QDoubleSpinBox()
        self.spin_blur.setRange(0.5, 30.0)
        self.spin_blur.setValue(2.5)
        self.spin_blur.setSingleStep(0.5)
        grid.addWidget(self.spin_blur, 0, 3)

        # 3. Brilho
        self.lbl_brightness = QLabel("Brilho (1.0x):")
        grid.addWidget(self.lbl_brightness, 1, 0)
        self.slider_brightness = QSlider(Qt.Horizontal)
        self.slider_brightness.setRange(20, 250)
        self.slider_brightness.setValue(100)
        self.slider_brightness.valueChanged.connect(
            lambda v: self.lbl_brightness.setText(f"Brilho ({v/100:.2f}x):")
        )
        grid.addWidget(self.slider_brightness, 1, 1)

        # 4. Contraste
        self.lbl_contrast = QLabel("Contraste (1.0x):")
        grid.addWidget(self.lbl_contrast, 1, 2)
        self.slider_contrast = QSlider(Qt.Horizontal)
        self.slider_contrast.setRange(20, 250)
        self.slider_contrast.setValue(100)
        self.slider_contrast.valueChanged.connect(
            lambda v: self.lbl_contrast.setText(f"Contraste ({v/100:.2f}x):")
        )
        grid.addWidget(self.slider_contrast, 1, 3)

        # 5. Saturação
        self.lbl_saturation = QLabel("Saturação (1.0x):")
        grid.addWidget(self.lbl_saturation, 2, 0)
        self.slider_saturation = QSlider(Qt.Horizontal)
        self.slider_saturation.setRange(0, 250)
        self.slider_saturation.setValue(100)
        self.slider_saturation.valueChanged.connect(
            lambda v: self.lbl_saturation.setText(f"Saturação ({v/100:.2f}x):")
        )
        grid.addWidget(self.slider_saturation, 2, 1)

        # 6. Nitidez
        self.lbl_sharpness = QLabel("Nitidez (1.0x):")
        grid.addWidget(self.lbl_sharpness, 2, 2)
        self.slider_sharpness = QSlider(Qt.Horizontal)
        self.slider_sharpness.setRange(0, 300)
        self.slider_sharpness.setValue(100)
        self.slider_sharpness.valueChanged.connect(
            lambda v: self.lbl_sharpness.setText(f"Nitidez ({v/100:.2f}x):")
        )
        grid.addWidget(self.slider_sharpness, 2, 3)

        # Botão Resetar Sliders
        btn_reset = QPushButton("Redefinir Ajustes para o Padrão")
        btn_reset.setFixedWidth(220)
        btn_reset.clicked.connect(self._reset_sliders)
        grid.addWidget(btn_reset, 3, 0, 1, 2)

        layout.addLayout(grid)
        self._on_effect_changed(self.cmb_effect.currentText())

        return panel

    def _on_effect_changed(self, eff: str):
        is_blur = eff == "Desfoque Gaussiano"
        self.lbl_blur.setVisible(is_blur)
        self.spin_blur.setVisible(is_blur)

    def _reset_sliders(self):
        self.slider_brightness.setValue(100)
        self.slider_contrast.setValue(100)
        self.slider_saturation.setValue(100)
        self.slider_sharpness.setValue(100)

    def get_options(self) -> Dict[str, Any]:
        return {
            "effect": self.cmb_effect.currentText(),
            "blur_radius": self.spin_blur.value(),
            "brightness": self.slider_brightness.value() / 100.0,
            "contrast": self.slider_contrast.value() / 100.0,
            "saturation": self.slider_saturation.value() / 100.0,
            "sharpness": self.slider_sharpness.value() / 100.0
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        return ""

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            apply_image_effects_and_adjustments(src, dst, params)
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message="Filtros e ajustes aplicados com sucesso"
            )
        except Exception as e:
            return ItemResult(
                success=False,
                source_path=src,
                output_path=dst,
                error=f"Erro ao processar imagem: {str(e)}"
            )
