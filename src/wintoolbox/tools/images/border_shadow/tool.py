"""
Ferramenta: Bordas, Sombras e Mockup de Capturas em Lote com Preview Dinâmico.
Implementação completa com contrato FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.border_shadow.logic import (
    process_image_border_shadow, render_border_shadow_preview
)
from wintoolbox.ui.widgets.live_preview import ImageLivePreviewPanel
from wintoolbox.ui.widgets.slider_spin import SliderSpinControl

_log = get_logger("images.border_shadow.ui")


@register
class BorderShadowTool(FileTool):
    id = "images.border_shadow"
    name = "Bordas e Sombras"
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
        main_layout = QHBoxLayout(panel)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        # Coluna da Esquerda: Controles
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        grp_box = QGroupBox("Estilo de Mockup e Efeitos Visuais")
        grid = QGridLayout(grp_box)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        # 1. Cantos Arredondados
        grid.addWidget(QLabel("Raio dos cantos:"), 0, 0)
        self.slider_radius = SliderSpinControl("", 0, 64, 16, suffix=" px")
        self.slider_radius.valueChanged.connect(self._on_options_changed)
        grid.addWidget(self.slider_radius, 0, 1)

        # 2. Espessura da Borda
        grid.addWidget(QLabel("Borda externa:"), 0, 2)
        self.spin_border = SliderSpinControl("", 0, 20, 1, suffix=" px")
        self.spin_border.valueChanged.connect(self._on_options_changed)
        grid.addWidget(self.spin_border, 0, 3)

        # 3. Sombra (Desfoque)
        grid.addWidget(QLabel("Sombra difusa:"), 1, 0)
        self.slider_shadow = SliderSpinControl("", 0, 80, 24, suffix=" px")
        self.slider_shadow.valueChanged.connect(self._on_options_changed)
        grid.addWidget(self.slider_shadow, 1, 1)

        # 4. Opacidade da Sombra
        grid.addWidget(QLabel("Opacidade sombra:"), 1, 2)
        self.slider_opacity = SliderSpinControl("", 0, 100, 35, suffix="%")
        self.slider_opacity.valueChanged.connect(self._on_options_changed)
        grid.addWidget(self.slider_opacity, 1, 3)

        # 5. Padding Externo
        grid.addWidget(QLabel("Espaço externo:"), 2, 0)
        self.slider_padding = SliderSpinControl("", 0, 120, 40, suffix=" px")
        self.slider_padding.valueChanged.connect(self._on_options_changed)
        grid.addWidget(self.slider_padding, 2, 1)

        # 6. Modo de Fundo
        grid.addWidget(QLabel("Fundo decorativo:"), 2, 2)
        self.cmb_background = QComboBox()
        self.cmb_background.addItem("Transparente (PNG / WebP)", "transparent")
        self.cmb_background.addItem("Cor Sólida (#f6f8fa)", "color")
        self.cmb_background.addItem("Gradiente: Pôr do Sol", "sunset")
        self.cmb_background.addItem("Gradiente: Oceano Profundo", "ocean")
        self.cmb_background.addItem("Gradiente: Roxo Neon", "neon_purple")
        self.cmb_background.addItem("Gradiente: Menta Fresca", "mint")
        self.cmb_background.addItem("Gradiente: Escuro Moderno", "dark_slate")
        self.cmb_background.currentTextChanged.connect(self._on_options_changed)
        grid.addWidget(self.cmb_background, 2, 3)

        left_layout.addWidget(grp_box)
        left_layout.addStretch()
        main_layout.addWidget(left_col, stretch=1)

        # Coluna da Direita: Preview Dinâmico
        self.preview_panel = ImageLivePreviewPanel("Prévia", panel)
        self.preview_panel.set_preview_generator(render_border_shadow_preview)
        main_layout.addWidget(self.preview_panel, stretch=1)

        panel.on_active_file_changed = self.on_active_file_changed
        return panel

    def on_active_file_changed(self, path: Path) -> None:
        self.preview_panel.set_source_file(path)
        self._update_preview()

    def _on_options_changed(self, *_) -> None:
        self._update_preview()

    def _update_preview(self) -> None:
        params = self.get_options()
        self.preview_panel.update_params(params)

    def get_options(self) -> Dict[str, Any]:
        bg_data = self.cmb_background.currentData() or "transparent"
        bg_mode = "gradient" if bg_data not in ("transparent", "color") else bg_data
        grad_preset = bg_data if bg_mode == "gradient" else None

        return {
            "corner_radius": int(self.slider_radius.value()),
            "border_width": int(self.spin_border.value()),
            "border_hex": "#d0d7de",
            "shadow_blur": int(self.slider_shadow.value()),
            "shadow_offset_y": max(2, int(self.slider_shadow.value() // 2)),
            "shadow_opacity": float(self.slider_opacity.value() / 100.0),
            "padding": int(self.slider_padding.value()),
            "background_mode": bg_mode,
            "bg_color_hex": "#f6f8fa",
            "gradient_preset": grad_preset,
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        return ".png"

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        if ctx and ctx.cancelled():
            return ItemResult(
                success=False,
                source_path=src,
                error="Operação cancelada pelo usuário"
            )
        final_out = dst
        if final_out.suffix.lower() not in (".png", ".webp"):
            final_out = final_out.with_suffix(".png")

        try:
            bytes_in = src.stat().st_size
            process_image_border_shadow(
                input_path=src,
                output_path=final_out,
                corner_radius=int(params.get("radius", params.get("corner_radius", 16))),
                border_width=int(params.get("border_width", 1)),
                border_hex=str(params.get("border_hex", "#d0d7de")),
                shadow_blur=int(params.get("shadow_blur", 24)),
                shadow_offset_y=int(params.get("shadow_offset_y", 12)),
                shadow_opacity=float(params.get("shadow_opacity", 0.35)),
                padding=int(params.get("padding", 40)),
                background_mode=str(params.get("background_mode", "transparent")),
                bg_color_hex=str(params.get("bg_color_hex", "#f6f8fa")),
                gradient_preset=params.get("gradient_preset"),
            )
            bytes_out = final_out.stat().st_size if final_out.exists() else 0
            return ItemResult(
                success=True,
                source_path=src,
                output_path=final_out,
                message="Mockup gerado com sucesso",
                bytes_in=bytes_in,
                bytes_out=bytes_out,
            )
        except Exception as exc:
            _log.warning("Falha ao aplicar bordas e sombras em '%s': %s", src, exc)
            return ItemResult(
                success=False,
                source_path=src,
                error=str(exc),
            )
