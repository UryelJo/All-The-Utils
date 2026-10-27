"""
Ferramenta: Conversor em Lote de Vetores SVG para PNG e ICO.
Implementação em lote herdando de FileTool utilizando renderizador nativo QSvgRenderer.
"""
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.images.svg_convert.logic import (
    convert_png_to_multi_size_ico, parse_svg_dimensions
)

_log = get_logger("images.svg_convert.ui")

SCALE_OPTIONS = [
    ("1x (Tamanho Nativo)", 1.0),
    ("2x (Alta Resolução - Retina)", 2.0),
    ("4x (Ultra HD 4K)", 4.0),
    ("Fixo: 256 × 256 px", 256),
    ("Fixo: 512 × 512 px", 512),
    ("Fixo: 1024 × 1024 px", 1024),
    ("Fixo: 2048 × 2048 px", 2048),
]


@register
class SvgConverterTool(FileTool):
    id = "images.svg_convert"
    name = "Conversor de SVG para PNG e ICO"
    category = "Imagens e Mídia"
    description = "Conversão de vetores SVG em lote para imagens PNG em alta resolução e ícones ICO multi-tamanho para Windows"
    keywords = ["svg", "vetor", "rasterizar", "png", "ico", "icone", "resolucao", "lote"]
    accepts = [".svg"]
    batch_kind = "per_file"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(14)

        # Formato de Saída
        row.addWidget(QLabel("Formato de Saída:"))
        self.cmb_format = QComboBox()
        self.cmb_format.addItem("PNG (Imagem Transparente)", "png")
        self.cmb_format.addItem("ICO (Ícone do Windows Multi-Resolução)", "ico")
        row.addWidget(self.cmb_format)

        # Escala de Renderização
        row.addWidget(QLabel("Resolução / Escala:"))
        self.cmb_scale = QComboBox()
        for label, val in SCALE_OPTIONS:
            self.cmb_scale.addItem(label, val)
        self.cmb_scale.setCurrentIndex(1)  # 2x por padrão
        row.addWidget(self.cmb_scale)

        # Fundo sólido
        self.chk_white_bg = QCheckBox("Fundo branco sólido (remover transparência)")
        row.addWidget(self.chk_white_bg)

        row.addStretch(1)
        layout.addLayout(row)
        return panel

    def get_options(self) -> Dict[str, Any]:
        return {
            "format": self.cmb_format.currentData() or "png",
            "scale_value": self.cmb_scale.currentData() or 2.0,
            "white_bg": self.chk_white_bg.isChecked(),
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        fmt = params.get("format", "png")
        return f".{fmt}"

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            fmt = params.get("format", "png")
            scale_val = params.get("scale_value", 2.0)
            white_bg = params.get("white_bg", False)

            renderer = QSvgRenderer(str(src))
            if not renderer.isValid():
                return ItemResult(success=False, source_path=src, error="Arquivo SVG inválido ou corrompido.")

            orig_w, orig_h = parse_svg_dimensions(src)

            # Calcula dimensões finais de renderização
            if isinstance(scale_val, int):
                target_w = scale_val
                target_h = scale_val
            else:
                target_w = max(16, int(orig_w * float(scale_val)))
                target_h = max(16, int(orig_h * float(scale_val)))

            # Cria canvas QImage transparente
            qimg = QImage(target_w, target_h, QImage.Format_ARGB32_Premultiplied)
            if white_bg:
                qimg.fill(QColor(255, 255, 255, 255))
            else:
                qimg.fill(Qt.transparent)

            painter = QPainter(qimg)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            renderer.render(painter)
            painter.end()

            dst.parent.mkdir(parents=True, exist_ok=True)

            if fmt == "png":
                qimg.save(str(dst), "PNG")
            elif fmt == "ico":
                # Salva temporário e monta pacote multi-resolução
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_f:
                    tmp_png = Path(tmp_f.name)
                try:
                    qimg.save(str(tmp_png), "PNG")
                    convert_png_to_multi_size_ico(tmp_png, dst)
                finally:
                    if tmp_png.exists():
                        tmp_png.unlink(missing_ok=True)

            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                bytes_in=src.stat().st_size,
                bytes_out=dst.stat().st_size if dst.exists() else 0
            )

        except Exception as e:
            _log.error(f"Erro ao converter SVG {src.name}: {e}")
            return ItemResult(success=False, source_path=src, error=str(e))
