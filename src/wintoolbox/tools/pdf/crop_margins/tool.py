"""
Interface gráfica da ferramenta Recortador de Margens em PDF (pdf.crop_margins).
Herda de FileTool com suporte a lote, detecção automática de conteúdo e corte manual.
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, register
from wintoolbox.tools.pdf.crop_margins.logic import crop_pdf_document


@register
class CropMarginsTool(FileTool):
    id = "pdf.crop_margins"
    name = "Recortador de Margens de PDF"
    description = "Recorta margens vazias de documentos PDF com detecção automática do conteúdo ou valores manuais."
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
        self._combo_mode.addItem("Corte Automático (Detecta conteúdo e bordas)", True)
        self._combo_mode.addItem("Corte Manual por Margens Fixas (pt)", False)
        self._combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        form.addRow("Método de Recorte:", self._combo_mode)

        self._spin_padding = QDoubleSpinBox()
        self._spin_padding.setRange(0, 200)
        self._spin_padding.setValue(10.0)
        self._spin_padding.setSuffix(" pt")
        form.addRow("Margem de Respiro:", self._spin_padding)

        # Margens manuais
        self._spin_left = QDoubleSpinBox()
        self._spin_left.setRange(0, 500)
        self._spin_left.setValue(20.0)
        self._spin_left.setSuffix(" pt")

        self._spin_right = QDoubleSpinBox()
        self._spin_right.setRange(0, 500)
        self._spin_right.setValue(20.0)
        self._spin_right.setSuffix(" pt")

        self._spin_top = QDoubleSpinBox()
        self._spin_top.setRange(0, 500)
        self._spin_top.setValue(20.0)
        self._spin_top.setSuffix(" pt")

        self._spin_bottom = QDoubleSpinBox()
        self._spin_bottom.setRange(0, 500)
        self._spin_bottom.setValue(20.0)
        self._spin_bottom.setSuffix(" pt")

        box_h = QHBoxLayout()
        box_h.addWidget(QLabel("Esq:"))
        box_h.addWidget(self._spin_left)
        box_h.addWidget(QLabel("Dir:"))
        box_h.addWidget(self._spin_right)
        box_h.addWidget(QLabel("Sup:"))
        box_h.addWidget(self._spin_top)
        box_h.addWidget(QLabel("Inf:"))
        box_h.addWidget(self._spin_bottom)
        form.addRow("Margens Manuais:", box_h)

        layout.addLayout(form)
        self._on_mode_changed(0)
        return widget

    def _on_mode_changed(self, idx: int) -> None:
        auto = self._combo_mode.currentData()
        self._spin_padding.setEnabled(auto)
        self._spin_left.setEnabled(not auto)
        self._spin_right.setEnabled(not auto)
        self._spin_top.setEnabled(not auto)
        self._spin_bottom.setEnabled(not auto)

    def get_options(self) -> Dict[str, Any]:
        return {
            "auto_crop": self._combo_mode.currentData(),
            "padding_pt": self._spin_padding.value(),
            "margin_left": self._spin_left.value(),
            "margin_right": self._spin_right.value(),
            "margin_top": self._spin_top.value(),
            "margin_bottom": self._spin_bottom.value(),
        }

    def process(self, input_path: Path, output_dir: Path, options: Dict[str, Any]) -> Path:
        out_path = output_dir / f"{input_path.stem}_recortado.pdf"
        return crop_pdf_document(
            input_pdf_path=input_path,
            output_pdf_path=out_path,
            auto_crop=options.get("auto_crop", True),
            padding_pt=options.get("padding_pt", 10.0),
            margin_left_pt=options.get("margin_left", 0.0),
            margin_bottom_pt=options.get("margin_bottom", 0.0),
            margin_right_pt=options.get("margin_right", 0.0),
            margin_top_pt=options.get("margin_top", 0.0),
        )
