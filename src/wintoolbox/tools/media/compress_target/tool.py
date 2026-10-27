"""
Interface gráfica do Compressor de Vídeo com Meta de Tamanho em MB (media.compress_target).
Herda de FileTool com suporte a lote, cálculo de bitrate e compressão precisa.
"""
from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import FileTool, register
from wintoolbox.tools.media.compress_target.logic import compress_to_target_size


@register
class CompressTargetTool(FileTool):
    id = "media.compress_target"
    name = "Compressor de Vídeo por Meta de Tamanho"
    description = "Compressor para tamanho alvo: recalcula o bitrate de vídeo e áudio para atingir exatamente o tamanho desejado (ex: 10 MB para e-mail ou 25 MB para Discord)."
    category = "Áudio e Vídeo"
    extensions = [
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".webm",
        ".flv",
        ".wmv",
    ]

    def build_options(self, parent=None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        # Meta de Tamanho
        size_box = QHBoxLayout()
        self._combo_presets = QComboBox()
        self._combo_presets.addItem("25 MB (Discord / E-mail)", 25.0)
        self._combo_presets.addItem("10 MB (Mensageiros Rápidos)", 10.0)
        self._combo_presets.addItem("50 MB (WhatsApp)", 50.0)
        self._combo_presets.addItem("100 MB", 100.0)
        self._combo_presets.addItem("Personalizado...", -1.0)
        self._combo_presets.currentIndexChanged.connect(self._on_preset_changed)
        size_box.addWidget(self._combo_presets)

        self._spin_custom_mb = QDoubleSpinBox()
        self._spin_custom_mb.setRange(1.0, 5000.0)
        self._spin_custom_mb.setValue(25.0)
        self._spin_custom_mb.setSuffix(" MB")
        self._spin_custom_mb.setEnabled(False)
        size_box.addWidget(self._spin_custom_mb)
        form.addRow("Meta de Tamanho:", size_box)

        # Bitrate de Áudio
        self._combo_audio = QComboBox()
        self._combo_audio.addItem("128 kbps (Recomendado)", 128)
        self._combo_audio.addItem("96 kbps (Economizar mais vídeo)", 96)
        self._combo_audio.addItem("64 kbps (Voz / Podcasts)", 64)
        self._combo_audio.addItem("192 kbps (Alta fidelidade musical)", 192)
        form.addRow("Bitrate de Áudio:", self._combo_audio)

        layout.addLayout(form)

        self._chk_two_pass = QCheckBox("Modo Duas Passadas (Two-Pass - Maior precisão de tamanho e qualidade visual)")
        self._chk_two_pass.setChecked(False)
        layout.addWidget(self._chk_two_pass)

        return widget

    def _on_preset_changed(self, idx: int) -> None:
        val = self._combo_presets.currentData()
        self._spin_custom_mb.setEnabled(val == -1.0)
        if val > 0:
            self._spin_custom_mb.setValue(val)

    def get_options(self) -> Dict[str, Any]:
        preset_val = self._combo_presets.currentData()
        target_mb = self._spin_custom_mb.value() if preset_val == -1.0 else preset_val

        return {
            "target_mb": target_mb,
            "audio_bitrate_kbps": self._combo_audio.currentData(),
            "two_pass": self._chk_two_pass.isChecked(),
        }

    def process(self, input_path: Path, output_dir: Path, options: Dict[str, Any]) -> Path:
        out_path = output_dir / f"{input_path.stem}_comprimido.mp4"
        return compress_to_target_size(
            input_path=input_path,
            output_path=out_path,
            target_mb=options.get("target_mb", 25.0),
            audio_bitrate_kbps=options.get("audio_bitrate_kbps", 128),
            two_pass=options.get("two_pass", False),
        )
