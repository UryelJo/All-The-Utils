"""
Ferramenta: Rotacionador de Páginas de PDF em Lote.
Implementação completa herdando de FileTool.
"""
from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QLabel, QLineEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.pdf.rotate.logic import rotate_pdf


@register
class PdfRotateTool(FileTool):
    id = "pdf.rotate"
    name = "Rotacionador de PDF"
    category = "PDF"
    description = "Gire páginas de PDFs em 90°, 180° ou 270° em lote, com seleção de todas, ímpares, pares ou intervalos"
    keywords = ["pdf", "rotacionar", "girar", "orientação", "paisagem", "retrato", "páginas", "lote"]
    accepts = [".pdf"]
    batch_kind = "per_file"
    parallel_mode = "thread"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Opções de Rotação de Páginas")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        grid.addWidget(QLabel("Ângulo de rotação:"), 0, 0)
        self.cmb_angle = QComboBox()
        self.cmb_angle.addItem("90° Horário", 90)
        self.cmb_angle.addItem("180° (Inverter)", 180)
        self.cmb_angle.addItem("270° Horário (90° Anti-horário)", 270)
        grid.addWidget(self.cmb_angle, 0, 1)

        grid.addWidget(QLabel("Aplicar nas páginas:"), 1, 0)
        self.cmb_pages_mode = QComboBox()
        self.cmb_pages_mode.addItem("Todas as páginas", "all")
        self.cmb_pages_mode.addItem("Apenas páginas ímpares (1, 3, 5...)", "odd")
        self.cmb_pages_mode.addItem("Apenas páginas pares (2, 4, 6...)", "even")
        self.cmb_pages_mode.addItem("Intervalo customizado", "range")
        self.cmb_pages_mode.currentIndexChanged.connect(self._on_pages_mode_changed)
        grid.addWidget(self.cmb_pages_mode, 1, 1)

        self.lbl_range = QLabel("Intervalo (ex: 1-3, 5):")
        self.lbl_range.setVisible(False)
        grid.addWidget(self.lbl_range, 2, 0)

        self.txt_range = QLineEdit()
        self.txt_range.setPlaceholderText("Ex: 1, 3, 5-8")
        self.txt_range.setVisible(False)
        grid.addWidget(self.txt_range, 2, 1)

        layout.addLayout(grid)
        return panel

    def _on_pages_mode_changed(self):
        mode = self.cmb_pages_mode.currentData()
        is_range = (mode == "range")
        self.lbl_range.setVisible(is_range)
        self.txt_range.setVisible(is_range)

    def get_options(self) -> Dict[str, Any]:
        return {
            "angle": self.cmb_angle.currentData(),
            "pages_mode": self.cmb_pages_mode.currentData(),
            "range_str": self.txt_range.text().strip(),
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        return ".pdf"

    def process(
        self,
        src: Path,
        dst: Path,
        params: Dict[str, Any],
        ctx: TaskContext
    ) -> ItemResult:
        try:
            rotate_pdf(
                src,
                dst,
                angle=params.get("angle", 90),
                pages_mode=params.get("pages_mode", "all"),
                range_str=params.get("range_str", "")
            )
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message=f"Páginas rotacionadas em {params.get('angle', 90)}°"
            )
        except Exception as e:
            return ItemResult(
                success=False,
                source_path=src,
                error=f"Falha ao rotacionar {src.name}: {e}"
            )
