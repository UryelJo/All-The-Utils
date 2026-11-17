"""
Ferramenta: Divisor de Imagens em Grade e Carrossel em Lote com Preview Dinâmico.
Implementação completa com contrato FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.split_grid.logic import (
    GRID_PRESETS, process_image_split, render_grid_slice_preview
)
from wintoolbox.ui.widgets.live_preview import ImageLivePreviewPanel
from wintoolbox.ui.widgets.slider_spin import SliderSpinControl

_log = get_logger("images.split_grid.ui")


@register
class SplitGridTool(FileTool):
    id = "images.split_grid"
    name = "Grade para Carrossel"
    category = "Imagens"
    description = "Fatie imagens panorâmicas em carrossel do Instagram, posts em mosaico, posters e grades 2D"
    keywords = ["grade", "carrossel", "instagram", "fatiar", "mosaico", "split", "tiles", "recorte", "sprites"]
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

        # Coluna da Esquerda: Controles e Presets
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        grp_opts = QGroupBox("Formato e Divisão")
        grid = QGridLayout(grp_opts)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        # Preset (Estilo Canva / Redes Sociais)
        grid.addWidget(QLabel("Predefinição:"), 0, 0)
        self.cmb_preset = QComboBox()
        self.cmb_preset.addItems(list(GRID_PRESETS.keys()))
        self.cmb_preset.currentTextChanged.connect(self._on_preset_changed)
        grid.addWidget(self.cmb_preset, 0, 1)

        # Formato de Saída
        grid.addWidget(QLabel("Formato dos slides:"), 0, 2)
        self.cmb_format = QComboBox()
        self.cmb_format.addItems(["PNG (Sem perdas)", "JPG (Fotografia)", "WEBP (Moderno)"])
        grid.addWidget(self.cmb_format, 0, 3)

        # Colunas (Divisões Horizontais)
        grid.addWidget(QLabel("Colunas (Slides horizontais):"), 1, 0)
        self.spin_cols = SliderSpinControl("", 1, 20, 3, suffix=" col")
        self.spin_cols.valueChanged.connect(self._on_dimensions_changed)
        grid.addWidget(self.spin_cols, 1, 1)

        # Linhas (Divisões Verticais)
        grid.addWidget(QLabel("Linhas (Slides verticais):"), 1, 2)
        self.spin_rows = SliderSpinControl("", 1, 20, 1, suffix=" lin")
        self.spin_rows.valueChanged.connect(self._on_dimensions_changed)
        grid.addWidget(self.spin_rows, 1, 3)

        # Sobreposição (Overlap)
        grid.addWidget(QLabel("Sobreposição entre fatias:"), 2, 0)
        self.spin_overlap = SliderSpinControl("", 0, 150, 0, suffix=" px")
        self.spin_overlap.valueChanged.connect(self._on_dimensions_changed)
        grid.addWidget(self.spin_overlap, 2, 1)

        # Padrão de Nomenclatura
        grid.addWidget(QLabel("Nome dos arquivos:"), 2, 2)
        self.txt_naming = QLineEdit("{stem}_slide_{col}")
        grid.addWidget(self.txt_naming, 2, 3)

        left_layout.addWidget(grp_opts)
        left_layout.addStretch()
        main_layout.addWidget(left_col, stretch=1)

        # Coluna da Direita: Preview Dinâmico com Numeração de Fatias
        self.preview_panel = ImageLivePreviewPanel("Pré-visualização das Fatias (Linhas de Corte)", panel)
        self.preview_panel.set_preview_generator(render_grid_slice_preview)
        main_layout.addWidget(self.preview_panel, stretch=1)

        return panel

    def on_active_file_changed(self, path: Path) -> None:
        self.preview_panel.set_source_file(path)
        self._update_preview()

    def _on_preset_changed(self, text: str) -> None:
        preset = GRID_PRESETS.get(text)
        if preset:
            self.spin_rows.setValue(preset["rows"])
            self.spin_cols.setValue(preset["cols"])
            if preset["rows"] == 1:
                self.txt_naming.setText("{stem}_slide_{col}")
            else:
                self.txt_naming.setText("{stem}_lin{row}_col{col}")
        self._update_preview()

    def _on_dimensions_changed(self, *_) -> None:
        self._update_preview()

    def _update_preview(self) -> None:
        params = self.get_options()
        self.preview_panel.update_params(params)

    def get_options(self) -> Dict[str, Any]:
        fmt_text = self.cmb_format.currentText()
        if "PNG" in fmt_text:
            out_fmt = "PNG"
        elif "JPG" in fmt_text:
            out_fmt = "JPG"
        else:
            out_fmt = "WEBP"

        return {
            "rows": int(self.spin_rows.value()),
            "cols": int(self.spin_cols.value()),
            "overlap_px": int(self.spin_overlap.value()),
            "output_format": out_fmt,
            "naming_pattern": self.txt_naming.text().strip() or "{stem}_slide_{col}",
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        fmt = str(params.get("output_format", params.get("format", "PNG"))).upper()
        if "JPG" in fmt or "JPEG" in fmt:
            return ".jpg"
        if "WEBP" in fmt:
            return ".webp"
        return ".png"

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        if ctx and ctx.cancelled():
            return ItemResult(
                success=False,
                source_path=src,
                error="Operação cancelada pelo usuário"
            )
        try:
            bytes_in = src.stat().st_size
            rows = int(params.get("rows", 1))
            cols = int(params.get("cols", 1))
            overlap_px = int(params.get("overlap_px", params.get("overlap", 0)))
            out_fmt = str(params.get("output_format", params.get("format", "PNG")))
            naming_pat = str(params.get("naming_pattern", "{stem}_slide_{col}"))

            clean_stem = dst.stem.split(".wtbx-")[0] if ".wtbx-" in dst.stem else src.stem
            output_dir = dst.parent / f"{clean_stem}_grid_{rows}x{cols}"

            generated = process_image_split(
                input_path=src,
                output_dir=output_dir,
                rows=rows,
                cols=cols,
                overlap_px=overlap_px,
                output_format=out_fmt,
                naming_pattern=naming_pat,
            )

            bytes_out = sum(p.stat().st_size for p in generated if p.exists())
            return ItemResult(
                success=True,
                source_path=src,
                output_path=output_dir,
                message=f"{len(generated)} fatias geradas em {output_dir.name}/",
                bytes_in=bytes_in,
                bytes_out=bytes_out,
            )
        except Exception as exc:
            _log.warning("Falha ao fatiar imagem '%s': %s", src, exc)
            return ItemResult(
                success=False,
                source_path=src,
                error=str(exc),
            )
