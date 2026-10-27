"""
Interface gráfica da ferramenta Normalização de Volume em Lote (media.normalize).
Integrada ao Batch Engine (FileTool).
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.media.normalize.logic import normalize_audio_file

_log = get_logger("media.normalize.ui")


@register
class NormalizeTool(FileTool):
    id = "media.normalize"
    name = "Normalizador de Volume em Lote (Loudnorm)"
    category = "Imagens"
    description = "Equalize e normalize o volume de músicas, podcasts e vídeos em lote para o padrão internacional EBU R128 (-14 LUFS)"
    keywords = ["normalizar", "volume", "loudnorm", "lufs", "audio", "video", "som", "mp3", "ebu r128", "podcast", "lote"]

    accepts = [
        ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".wma",
        ".mp4", ".mkv", ".mov", ".avi", ".webm"
    ]
    batch_kind = "per_file"
    parallel_mode = "thread"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QWidget(parent)
        layout = QFormLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Preset
        self.cmb_preset = QComboBox()
        self.cmb_preset.addItem("Streaming Web / YouTube / Spotify (-14 LUFS)", -14.0)
        self.cmb_preset.addItem("Apple Music / Podcasts (-16 LUFS)", -16.0)
        self.cmb_preset.addItem("Broadcast / Televisão EBU R128 (-23 LUFS)", -23.0)
        self.cmb_preset.addItem("Personalizado", 0.0)
        self.cmb_preset.currentIndexChanged.connect(self._on_preset_changed)
        layout.addRow("Padrão de Sonoridade:", self.cmb_preset)

        # Alvo Integrado LUFS
        self.spin_lufs = QDoubleSpinBox()
        self.spin_lufs.setRange(-70.0, -5.0)
        self.spin_lufs.setValue(-14.0)
        self.spin_lufs.setSingleStep(1.0)
        self.spin_lufs.setSuffix(" LUFS")
        layout.addRow("Meta Integrada (I):", self.spin_lufs)

        # True Peak
        self.spin_tp = QDoubleSpinBox()
        self.spin_tp.setRange(-10.0, 0.0)
        self.spin_tp.setValue(-1.0)
        self.spin_tp.setSingleStep(0.5)
        self.spin_tp.setSuffix(" dBFS")
        layout.addRow("Pico Verdadeiro Máximo (TP):", self.spin_tp)

        # Formato de Saída (para áudios)
        self.cmb_out_format = QComboBox()
        self.cmb_out_format.addItem("Manter Formato Original", "keep")
        self.cmb_out_format.addItem("Converter para MP3 (320 kbps)", "mp3")
        self.cmb_out_format.addItem("Converter para M4A / AAC (256 kbps)", "m4a")
        self.cmb_out_format.addItem("Converter para WAV sem perdas", "wav")
        self.cmb_out_format.addItem("Converter para FLAC sem perdas", "flac")
        layout.addRow("Formato de Áudio:", self.cmb_out_format)

        return container

    def _on_preset_changed(self, idx: int) -> None:
        val = self.cmb_preset.currentData()
        if val != 0.0:
            self.spin_lufs.setValue(val)

    def get_options(self) -> Dict[str, Any]:
        lufs = getattr(self, "spin_lufs", None)
        tp = getattr(self, "spin_tp", None)
        fmt = getattr(self, "cmb_out_format", None)
        return {
            "target_lufs": lufs.value() if lufs else -14.0,
            "true_peak": tp.value() if tp else -1.0,
            "loudness_range": 11.0,
            "output_format": fmt.currentData() if fmt else "keep",
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        fmt = params.get("output_format", "keep")
        if fmt != "keep":
            return f".{fmt}"
        return ""

    def process(self, src: Path, dst: Path, params: Dict[str, Any], ctx: TaskContext) -> ItemResult:
        try:
            target_lufs = float(params.get("target_lufs", -14.0))
            true_peak = float(params.get("true_peak", -1.0))
            lra = float(params.get("loudness_range", 11.0))
            out_fmt = str(params.get("output_format", "keep"))

            out_path = normalize_audio_file(
                src_path=src,
                dst_path=dst,
                target_lufs=target_lufs,
                true_peak=true_peak,
                loudness_range=lra,
                output_format=out_fmt,
            )

            return ItemResult(
                success=True,
                source_path=src,
                output_path=out_path,
                message=f"Normalizado com sucesso para {target_lufs} LUFS",
            )
        except Exception as exc:
            return ItemResult(
                success=False,
                source_path=src,
                error=str(exc),
            )
