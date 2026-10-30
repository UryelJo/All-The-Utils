"""
Ferramenta: Bordas, Sombras e Mockup de Capturas em Lote.
Implementação completa com contrato FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.border_shadow.logic import process_image_border_shadow


@register
class BorderShadowTool(FileTool):
    id = "images.border_shadow"
    name = "Bordas e Sombras (Mockup)"
    category = "Imagens"
    description = "Adicione cantos arredondados, sombra difusa, moldura e fundo decorativo em screenshots"
    keywords = ["borda", "sombra", "mockup", "screenshot", "cantos arredondados", "moldura", "gradiente"]
    accepts = [
        ".png", ".jpg", ".jpeg", ".jfif", ".webp",
        ".heic", ".heif", ".hif", ".avif", ".bmp",
        ".tiff", ".qoi", ".tga", ".psd",
    ]
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Estilo de Mockup e Efeitos Visuais")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # 1. Cantos Arredondados
        self.lbl_radius = QLabel("Raio dos cantos (16 px):")
        grid.addWidget(self.lbl_radius, 0, 0)
        self.slider_radius = QSlider(Qt.Horizontal)
        self.slider_radius.setRange(0, 64)
        self.slider_radius.setValue(16)
        self.slider_radius.valueChanged.connect(
            lambda v: self.lbl_radius.setText(f"Raio dos cantos ({v} px):")
        )
        grid.addWidget(self.slider_radius, 0, 1)

        # 2. Espessura da Borda
        self.lbl_border = QLabel("Borda (1 px):")
        grid.addWidget(self.lbl_border, 0, 2)
        self.spin_border = QSpinBox()
        self.spin_border.setRange(0, 20)
        self.spin_border.setValue(1)
        self.spin_border.valueChanged.connect(
            lambda v: self.lbl_border.setText(f"Borda ({v} px):")
        )
        grid.addWidget(self.spin_border, 0, 3)

        # 3. Sombra (Desfoque)
        self.lbl_shadow = QLabel("Sombra difusa (24 px):")
        grid.addWidget(self.lbl_shadow, 1, 0)
        self.slider_shadow = QSlider(Qt.Horizontal)
        self.slider_shadow.setRange(0, 60)
        self.slider_shadow.setValue(24)
        self.slider_shadow.valueChanged.connect(
            lambda v: self.lbl_shadow.setText(f"Sombra difusa ({v} px):")
        )
        grid.addWidget(self.slider_shadow, 1, 1)

        # 4. Opacidade da Sombra
        self.lbl_opacity = QLabel("Opacidade sombra (35%):")
        grid.addWidget(self.lbl_opacity, 1, 2)
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(0, 100)
        self.slider_opacity.setValue(35)
        self.slider_opacity.valueChanged.connect(
            lambda v: self.lbl_opacity.setText(f"Opacidade sombra ({v}%):")
        )
        grid.addWidget(self.slider_opacity, 1, 3)

        # 5. Padding Externo
        self.lbl_padding = QLabel("Espaçamento externo (40 px):")
        grid.addWidget(self.lbl_padding, 2, 0)
        self.slider_padding = QSlider(Qt.Horizontal)
        self.slider_padding.setRange(0, 120)
        self.slider_padding.setValue(40)
        self.slider_padding.valueChanged.connect(
            lambda v: self.lbl_padding.setText(f"Espaçamento externo ({v} px):")
        )
        grid.addWidget(self.slider_padding, 2, 1)

        # 6. Modo de Fundo
        grid.addWidget(QLabel("Tipo de fundo:"), 2, 2)
        self.cmb_bg = QComboBox()
        self.cmb_bg.addItems([
            "Transparente",
            "Gradiente Slate",
            "Gradiente Sunset",
            "Gradiente Ocean",
            "Gradiente Purple",
            "Cor Sólida",
        ])
        grid.addWidget(self.cmb_bg, 2, 3)

        layout.addLayout(grid)
        return panel

    def get_options(self) -> Dict[str, Any]:
        return {
            "radius": self.slider_radius.value() if hasattr(self, "slider_radius") else 16,
            "border_width": self.spin_border.value() if hasattr(self, "spin_border") else 1,
            "shadow_blur": self.slider_shadow.value() if hasattr(self, "slider_shadow") else 24,
            "shadow_opacity": (self.slider_opacity.value() / 100.0) if hasattr(self, "slider_opacity") else 0.35,
            "padding": self.slider_padding.value() if hasattr(self, "slider_padding") else 40,
            "bg_text": self.cmb_bg.currentText() if hasattr(self, "cmb_bg") else "Transparente",
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        return ".png"

    def process(
        self,
        src: Path,
        dst: Path,
        params: Optional[Dict[str, Any]] = None,
        ctx: Optional[TaskContext] = None,
    ) -> ItemResult:
        opts = self.get_options() if hasattr(self, "slider_radius") else {}
        eff_params = params if isinstance(params, dict) else {}

        if ctx is not None and ctx.cancelled():
            return ItemResult(
                success=False,
                source_path=src,
                output_path=dst,
                error="Operação cancelada pelo usuário",
            )

        radius = int(eff_params.get("radius", opts.get("radius", 16)))
        border_w = int(eff_params.get("border_width", opts.get("border_width", 1)))
        shadow_blur = int(eff_params.get("shadow_blur", opts.get("shadow_blur", 24)))
        shadow_op = float(eff_params.get("shadow_opacity", opts.get("shadow_opacity", 0.35)))
        pad = int(eff_params.get("padding", opts.get("padding", 40)))
        bg_text = str(eff_params.get("bg_text", opts.get("bg_text", "Transparente")))

        if "Slate" in bg_text:
            bg_mode = "gradient"
            preset = "slate"
        elif "Sunset" in bg_text:
            bg_mode = "gradient"
            preset = "sunset"
        elif "Ocean" in bg_text:
            bg_mode = "gradient"
            preset = "ocean"
        elif "Purple" in bg_text:
            bg_mode = "gradient"
            preset = "purple"
        elif "Cor Sólida" in bg_text:
            bg_mode = "color"
            preset = None
        else:
            bg_mode = "transparent"
            preset = None

        final_out = dst
        if bg_mode == "transparent" and final_out.suffix.lower() not in (".png", ".webp"):
            final_out = final_out.with_suffix(".png")

        bytes_in = src.stat().st_size if src.exists() else 0

        try:
            res_path = process_image_border_shadow(
                input_path=src,
                output_path=final_out,
                corner_radius=radius,
                border_width=border_w,
                border_hex="#d0d7de",
                shadow_blur=shadow_blur,
                shadow_offset_y=12,
                shadow_opacity=shadow_op,
                padding=pad,
                background_mode=bg_mode,
                bg_color_hex="#ffffff",
                gradient_preset=preset,
            )
            bytes_out = res_path.stat().st_size if res_path.exists() else 0
            return ItemResult(
                success=True,
                source_path=src,
                output_path=res_path,
                message=f"Mockup gerado: raio {radius}px, sombra {shadow_blur}px",
                bytes_in=bytes_in,
                bytes_out=bytes_out,
            )
        except Exception as e:
            return ItemResult(
                success=False,
                source_path=src,
                output_path=dst,
                error=str(e),
                bytes_in=bytes_in,
            )
