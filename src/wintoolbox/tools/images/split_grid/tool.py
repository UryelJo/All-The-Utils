"""
Ferramenta: Divisão de Imagens em Grade e Fatias.
Permite particionar imagens para carrossel, mosaicos e sprites em lote.
"""
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.split_grid.logic import split_image_file


@register
class SplitGridTool(FileTool):
    id = "images.split_grid"
    name = "Divisão em Grade (Carrossel)"
    category = "Imagens"
    description = "Divida imagens em grades NxM ou fatias para carrossel do Instagram, posters e sprites"
    keywords = ["dividir", "grade", "fatiar", "carrossel", "instagram", "mosaico", "sprites", "grid", "tiles"]
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

        lbl_header = QLabel("Configuração da Grade de Corte")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # 1. Predefinições Rápidas
        grid.addWidget(QLabel("Predefinições:"), 0, 0)
        self.cmb_preset = QComboBox()
        self.cmb_preset.addItems([
            "Personalizado",
            "Carrossel Instagram (1x3)",
            "Carrossel Instagram (1x4)",
            "Grade Instagram (3x3)",
            "Díptico / Lado a Lado (1x2)",
            "Atlas / Sprite (2x2)",
            "Atlas / Sprite (4x4)",
        ])
        self.cmb_preset.currentTextChanged.connect(self._on_preset_changed)
        grid.addWidget(self.cmb_preset, 0, 1, 1, 3)

        # 2. Linhas
        grid.addWidget(QLabel("Linhas (verticais):"), 1, 0)
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(1, 20)
        self.spin_rows.setValue(1)
        grid.addWidget(self.spin_rows, 1, 1)

        # 3. Colunas
        grid.addWidget(QLabel("Colunas (horizontais):"), 1, 2)
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 20)
        self.spin_cols.setValue(3)
        grid.addWidget(self.spin_cols, 1, 3)

        # 4. Sobreposição (Overlap)
        grid.addWidget(QLabel("Sobreposição (px):"), 2, 0)
        self.spin_overlap = QSpinBox()
        self.spin_overlap.setRange(0, 100)
        self.spin_overlap.setValue(0)
        grid.addWidget(self.spin_overlap, 2, 1)

        # 5. Formato de Saída
        grid.addWidget(QLabel("Formato de saída:"), 2, 2)
        self.cmb_format = QComboBox()
        self.cmb_format.addItems(["PNG", "JPEG", "WebP"])
        grid.addWidget(self.cmb_format, 2, 3)

        layout.addLayout(grid)
        return panel

    def _on_preset_changed(self, text: str) -> None:
        if "1x3" in text:
            self.spin_rows.setValue(1)
            self.spin_cols.setValue(3)
        elif "1x4" in text:
            self.spin_rows.setValue(1)
            self.spin_cols.setValue(4)
        elif "3x3" in text:
            self.spin_rows.setValue(3)
            self.spin_cols.setValue(3)
        elif "1x2" in text:
            self.spin_rows.setValue(1)
            self.spin_cols.setValue(2)
        elif "2x2" in text:
            self.spin_rows.setValue(2)
            self.spin_cols.setValue(2)
        elif "4x4" in text:
            self.spin_rows.setValue(4)
            self.spin_cols.setValue(4)

    def get_options(self) -> Dict[str, Any]:
        return {
            "rows": self.spin_rows.value() if hasattr(self, "spin_rows") else 1,
            "cols": self.spin_cols.value() if hasattr(self, "spin_cols") else 3,
            "overlap": self.spin_overlap.value() if hasattr(self, "spin_overlap") else 0,
            "format": self.cmb_format.currentText() if hasattr(self, "cmb_format") else "PNG",
        }

    def process(
        self,
        src: Path,
        dst: Path,
        params: Optional[Dict[str, Any]] = None,
        ctx: Optional[TaskContext] = None,
    ) -> ItemResult:
        opts = self.get_options() if hasattr(self, "spin_rows") else {}
        eff_params = params if isinstance(params, dict) else {}

        if ctx is not None and ctx.cancelled():
            return ItemResult(
                success=False,
                source_path=src,
                output_path=dst,
                error="Operação cancelada pelo usuário",
            )

        rows = int(eff_params.get("rows", opts.get("rows", 1)))
        cols = int(eff_params.get("cols", opts.get("cols", 3)))
        overlap = int(eff_params.get("overlap", opts.get("overlap", 0)))
        out_fmt = str(eff_params.get("format", opts.get("format", "PNG"))).lower()

        clean_stem = dst.stem.split(".wtbx-")[0] if ".wtbx-" in dst.stem else src.stem
        dest_folder = dst.parent / f"{clean_stem}_grid_{rows}x{cols}"
        bytes_in = src.stat().st_size if src.exists() else 0

        try:
            generated_files = split_image_file(
                input_path=src,
                output_dir=dest_folder,
                rows=rows,
                cols=cols,
                overlap_px=overlap,
                output_format=out_fmt,
            )
            bytes_out = sum(f.stat().st_size for f in generated_files if f.exists())
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dest_folder,
                message=f"{len(generated_files)} partes geradas em {dest_folder.name}",
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
