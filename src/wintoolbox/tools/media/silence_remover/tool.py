"""
Interface gráfica do Removedor Automático de Silêncio (media.silence_remover).
Herda de FileTool com suporte a lote, ajuste de decibéis e corte de pausas mortas.
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, register
from wintoolbox.tools.media.silence_remover.logic import remove_silence_from_media


@register
class SilenceRemoverTool(FileTool):
    id = "media.silence_remover"
    name = "Removedor de Silêncios e Pausas"
    description = "Remove automaticamente trechos de silêncio e pausas mortas em podcasts, gravações de voz e aulas."
    category = "media"
    extensions = [
        ".mp3",
        ".wav",
        ".m4a",
        ".flac",
        ".ogg",
        ".aac",
        ".mp4",
        ".mkv",
        ".webm",
    ]

    def build_options(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self._combo_threshold = QComboBox()
        self._combo_threshold.addItem("-35 dB (Equilibrado / Recomendado)", -35.0)
        self._combo_threshold.addItem("-30 dB (Agressivo / Corta mais rápido)", -30.0)
        self._combo_threshold.addItem("-40 dB (Conservador / Preserva pausas suaves)", -40.0)
        self._combo_threshold.addItem("-50 dB (Apenas silêncio absoluto digital)", -50.0)
        form.addRow("Sensibilidade do Silêncio:", self._combo_threshold)

        self._spin_duration = QDoubleSpinBox()
        self._spin_duration.setRange(0.2, 10.0)
        self._spin_duration.setValue(0.8)
        self._spin_duration.setSingleStep(0.1)
        self._spin_duration.setSuffix(" s")
        form.addRow("Duração Mínima da Pausa:", self._spin_duration)

        layout.addLayout(form)
        return widget

    def get_options(self) -> Dict[str, Any]:
        return {
            "threshold_db": self._combo_threshold.currentData(),
            "min_silence_sec": self._spin_duration.value(),
        }

    def process(self, input_path: Path, output_dir: Path, options: Dict[str, Any]) -> Path:
        out_path = output_dir / f"{input_path.stem}_sem_silencio{input_path.suffix}"
        return remove_silence_from_media(
            input_path=input_path,
            output_path=out_path,
            threshold_db=options.get("threshold_db", -35.0),
            min_silence_sec=options.get("min_silence_sec", 0.8),
        )
