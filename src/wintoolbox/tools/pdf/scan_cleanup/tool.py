"""
Interface gráfica do Higienizador de Digitalizações e Scans em PDF (pdf.scan_cleanup).
Herda de FileTool com suporte a lote, conversão para preto e branco puro e realce de nitidez.
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, register
from wintoolbox.tools.pdf.scan_cleanup.logic import cleanup_scanned_pdf


@register
class ScanCleanupTool(FileTool):
    id = "pdf.scan_cleanup"
    name = "Higienizador de Scans e Digitalizações"
    description = "Otimizador de digitalizações (Scans): clareia fundos cinzentos, aumenta o contraste e a nitidez do texto escaneado e gera arquivos preto e branco nítidos."
    category = "PDF"
    extensions = [".pdf"]

    def build_options(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._combo_color = QComboBox()
        self._combo_color.addItem("Preto e Branco Puro (Remove manchas e sombras de fundo)", True)
        self._combo_color.addItem("Escala de Cinza com Alto Contraste", False)
        form.addRow("Modo de Saída:", self._combo_color)

        self._spin_contrast = QDoubleSpinBox()
        self._spin_contrast.setRange(1.0, 4.0)
        self._spin_contrast.setValue(1.8)
        self._spin_contrast.setSingleStep(0.2)
        self._spin_contrast.setSuffix("x")
        form.addRow("Realce de Contraste:", self._spin_contrast)

        self._spin_threshold = QSpinBox()
        self._spin_threshold.setRange(50, 240)
        self._spin_threshold.setValue(180)
        form.addRow("Limiar de Binarização:", self._spin_threshold)

        self._chk_sharpen = QCheckBox("Aplicar filtro de nitidez nas bordas de texto (Sharpen)")
        self._chk_sharpen.setChecked(True)
        form.addRow("Nitidez:", self._chk_sharpen)

        self._combo_dpi = QComboBox()
        self._combo_dpi.addItem("150 DPI (Equilibrado / Rápido)", 150)
        self._combo_dpi.addItem("300 DPI (Alta Resolução para Impressão)", 300)
        self._combo_dpi.addItem("100 DPI (Compacto / Visualização Rápida)", 100)
        form.addRow("Resolução:", self._combo_dpi)

        layout.addLayout(form)
        return widget

    def get_options(self) -> Dict[str, Any]:
        return {
            "to_pure_bw": self._combo_color.currentData(),
            "contrast_factor": self._spin_contrast.value(),
            "binarize_threshold": self._spin_threshold.value(),
            "sharpen": self._chk_sharpen.isChecked(),
            "dpi": self._combo_dpi.currentData(),
        }

    def process(self, input_path: Path, output_dir: Path, options: Dict[str, Any]) -> Path:
        out_path = output_dir / f"{input_path.stem}_limpo.pdf"
        return cleanup_scanned_pdf(
            input_pdf_path=input_path,
            output_pdf_path=out_path,
            contrast_factor=options.get("contrast_factor", 1.8),
            to_pure_bw=options.get("to_pure_bw", True),
            binarize_threshold=options.get("binarize_threshold", 180),
            sharpen=options.get("sharpen", True),
            dpi=options.get("dpi", 150),
        )
