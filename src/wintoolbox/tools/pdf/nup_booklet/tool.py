"""
Interface gráfica da ferramenta Reorganizador de Páginas e Livretos N-Up (pdf.nup_booklet).
Herda de FileTool com suporte a lote, 2-Up, 4-Up e imposição de livreto (booklet).
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, register
from wintoolbox.tools.pdf.nup_booklet.logic import process_nup_or_booklet


@register
class NupBookletTool(FileTool):
    id = "pdf.nup_booklet"
    name = "Reorganizador de Páginas e Livretos (N-Up)"
    description = "Monta 2 ou 4 páginas por folha e gera imposição de livreto (booklet) para impressão e encadernação."
    category = "PDF"
    extensions = [".pdf"]

    def build_options(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._combo_mode = QComboBox()
        self._combo_mode.addItem("2 Páginas por Folha (2-Up Paisagem)", "2UP")
        self._combo_mode.addItem("4 Páginas por Folha (4-Up Grade Retrato)", "4UP")
        self._combo_mode.addItem("Livreto / Booklet (Imposição para Dobra e Grampeamento)", "BOOKLET")
        form.addRow("Modo de Imposição:", self._combo_mode)

        layout.addLayout(form)
        return widget

    def get_options(self) -> Dict[str, Any]:
        return {
            "mode": self._combo_mode.currentData(),
        }

    def process(self, input_path: Path, output_dir: Path, options: Dict[str, Any]) -> Path:
        mode = options.get("mode", "2UP")
        mode_suffix = mode.lower()
        out_path = output_dir / f"{input_path.stem}_{mode_suffix}.pdf"
        return process_nup_or_booklet(
            input_pdf_path=input_path,
            output_pdf_path=out_path,
            mode=mode,
        )
