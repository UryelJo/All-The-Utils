"""
Ferramenta: Conversor Universal de Vídeo e Áudio em Lote.
Implementação completa herdando de FileTool com suporte a 50 formatos de entrada,
26 formatos de saída, codecs modernos (H.264, H.265/HEVC Apple, AV1, VP9, ProRes, Stream Copy),
extração de áudio, compressão por meta de MB e conversão para GIF / WebP Animado.
"""
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import FileTool, ItemResult, TaskContext, register
from wintoolbox.tools.media.convert.logic import (
    ALL_OUTPUT_FORMATS,
    ANIMATED_FORMATS,
    AUDIO_FORMATS,
    FLEXIBLE_CODEC_CONTAINERS,
    SUPPORTED_MEDIA_INPUTS,
    convert_media_file,
)

_log = get_logger("media.convert.ui")


@register
class MediaConvertTool(FileTool):
    id = "media.convert"
    name = "Conversor de Vídeo e Áudio"
    category = "Áudio e Vídeo"
    description = (
        "Converta vídeos e áudios em lote entre 50 formatos (MP4, MOV/HEVC iPhone, MKV, WEBM, "
        "TS, AVI, WMV, OPUS, FLAC, M4A, AIFF, AC3, GIF e WebP Animado) com aceleração por GPU"
    )
    keywords = [
        "video", "audio", "conversor", "mp4", "mov", "hevc", "h265", "h264", "av1", "prores",
        "iphone", "mp3", "opus", "flac", "m4a", "aiff", "ac3", "mkv", "webm", "ts", "mts",
        "vob", "3gp", "gif", "webp", "comprimir", "extrair audio", "ffmpeg", "lote",
    ]
    accepts = list(SUPPORTED_MEDIA_INPUTS)
    batch_kind = "per_file"
    parallel_mode = "process"

    def build_options(self, parent: Optional[QWidget] = None) -> QWidget:
        panel = QFrame(parent)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        lbl_header = QLabel("Opções de Conversão, Codecs e Otimização")
        lbl_header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # Linha 0: Formato de saída + Codec de Vídeo
        grid.addWidget(QLabel("Formato de saída:"), 0, 0)
        self.cmb_format = QComboBox()
        self.cmb_format.addItems([fmt.upper() for fmt in ALL_OUTPUT_FORMATS])
        self.cmb_format.setCurrentText("MP4")
        self.cmb_format.currentTextChanged.connect(self._sync_controls_state)
        grid.addWidget(self.cmb_format, 0, 1)

        grid.addWidget(QLabel("Codec de vídeo:"), 0, 2)
        self.cmb_video_codec = QComboBox()
        self.cmb_video_codec.addItem("Automático (Recomendado para o formato)", "auto")
        self.cmb_video_codec.addItem("H.264 / AVC (Compatibilidade Universal)", "h264")
        self.cmb_video_codec.addItem("H.265 / HEVC (Alta Eficiência / iPhone hvc1)", "h265")
        self.cmb_video_codec.addItem("AV1 (Alta Compressão Web Moderna)", "av1")
        self.cmb_video_codec.addItem("VP9 (WebM / Streaming)", "vp9")
        self.cmb_video_codec.addItem("Apple ProRes 422 (Edição Profissional - MOV/MKV)", "prores")
        self.cmb_video_codec.addItem("Cópia Direta sem Recodificar (Remux Rápido)", "copy")
        self.cmb_video_codec.currentIndexChanged.connect(self._sync_controls_state)
        grid.addWidget(self.cmb_video_codec, 0, 3)

        # Linha 1: Resolução Máxima + Qualidade / Bitrate de Áudio
        grid.addWidget(QLabel("Resolução de vídeo:"), 1, 0)
        self.cmb_resolution = QComboBox()
        self.cmb_resolution.addItem("Manter resolução original", 0)
        self.cmb_resolution.addItem("Máximo 2160p (4K Ultra HD)", 2160)
        self.cmb_resolution.addItem("Máximo 1440p (2K QHD)", 1440)
        self.cmb_resolution.addItem("Máximo 1080p (Full HD)", 1080)
        self.cmb_resolution.addItem("Máximo 720p (HD)", 720)
        self.cmb_resolution.addItem("Máximo 480p (Compacto)", 480)
        grid.addWidget(self.cmb_resolution, 1, 1)

        grid.addWidget(QLabel("Bitrate de áudio:"), 1, 2)
        self.cmb_audio_bitrate = QComboBox()
        self.cmb_audio_bitrate.addItem("128 kbps (Compacto / Voz)", "128k")
        self.cmb_audio_bitrate.addItem("192 kbps (Padrão Equilibrado)", "192k")
        self.cmb_audio_bitrate.addItem("256 kbps (Alta Qualidade)", "256k")
        self.cmb_audio_bitrate.addItem("320 kbps (Qualidade Máxima)", "320k")
        self.cmb_audio_bitrate.setCurrentIndex(1)
        grid.addWidget(self.cmb_audio_bitrate, 1, 3)

        # Linha 2: Meta de tamanho em MB + Aceleração de Hardware
        grid.addWidget(QLabel("Meta de tamanho (MB) [opcional]:"), 2, 0)
        self.spin_target_mb = QDoubleSpinBox()
        self.spin_target_mb.setRange(0.0, 10000.0)
        self.spin_target_mb.setValue(0.0)
        self.spin_target_mb.setSpecialValueText("Desativado (qualidade padrão)")
        self.spin_target_mb.setSuffix(" MB")
        grid.addWidget(self.spin_target_mb, 2, 1)

        grid.addWidget(QLabel("Processamento:"), 2, 2)
        self.cmb_hw_accel = QComboBox()
        self.cmb_hw_accel.addItem("Automático (GPU NVENC/AMF/QSV + Fallback CPU)", "auto")
        self.cmb_hw_accel.addItem("Forçar Processador (CPU - Máxima Eficiência)", "cpu")
        grid.addWidget(self.cmb_hw_accel, 2, 3)

        # Linha 3: Extrair áudio apenas
        self.chk_extract_audio = QCheckBox("Extrair apenas a faixa de áudio (ignorar vídeo)")
        self.chk_extract_audio.toggled.connect(self._on_audio_toggled)
        grid.addWidget(self.chk_extract_audio, 3, 0, 1, 4)

        # Linha 4: Opções dedicadas de Animação (GIF e WebP Animado)
        self.lbl_gif_fps = QLabel("FPS da animação:")
        grid.addWidget(self.lbl_gif_fps, 4, 0)

        self.spin_gif_fps = QSpinBox()
        self.spin_gif_fps.setRange(1, 60)
        self.spin_gif_fps.setValue(15)
        grid.addWidget(self.spin_gif_fps, 4, 1)

        self.lbl_gif_width = QLabel("Largura da animação (px):")
        grid.addWidget(self.lbl_gif_width, 4, 2)

        self.spin_gif_width = QSpinBox()
        self.spin_gif_width.setRange(120, 1920)
        self.spin_gif_width.setSingleStep(40)
        self.spin_gif_width.setValue(480)
        grid.addWidget(self.spin_gif_width, 4, 3)

        layout.addLayout(grid)
        self._sync_controls_state()
        return panel

    def _sync_controls_state(self) -> None:
        fmt = self.cmb_format.currentText().lower()
        is_anim = fmt in ANIMATED_FORMATS
        is_audio = self.chk_extract_audio.isChecked() or (fmt in AUDIO_FORMATS)
        is_video = not is_anim and not is_audio

        self.lbl_gif_fps.setVisible(is_anim)
        self.spin_gif_fps.setVisible(is_anim)
        self.lbl_gif_width.setVisible(is_anim)
        self.spin_gif_width.setVisible(is_anim)

        can_choose_codec = is_video and (fmt in FLEXIBLE_CODEC_CONTAINERS or fmt == "webm")
        self.cmb_video_codec.setEnabled(can_choose_codec)

        is_stream_copy = can_choose_codec and (self.cmb_video_codec.currentData() == "copy")
        self.cmb_resolution.setEnabled(is_video and not is_stream_copy)
        self.spin_target_mb.setEnabled(is_video and not is_stream_copy)
        self.cmb_hw_accel.setEnabled(is_video and not is_stream_copy)

        lossless_audio = fmt in ("flac", "wav", "aiff", "caf")
        self.cmb_audio_bitrate.setEnabled((not is_anim) and (not lossless_audio) and (not is_stream_copy))

    def _on_audio_toggled(self, checked: bool) -> None:
        if checked:
            fmt = self.cmb_format.currentText().lower()
            if fmt not in AUDIO_FORMATS:
                self.cmb_format.setCurrentText("MP3")
        self._sync_controls_state()

    def get_options(self) -> Dict[str, Any]:
        return {
            "format": self.cmb_format.currentText().lower(),
            "extract_audio": self.chk_extract_audio.isChecked(),
            "target_size_mb": self.spin_target_mb.value(),
            "gif_fps": self.spin_gif_fps.value(),
            "gif_width": self.spin_gif_width.value(),
            "video_codec": self.cmb_video_codec.currentData() or "auto",
            "max_height": int(self.cmb_resolution.currentData() or 0),
            "audio_bitrate": self.cmb_audio_bitrate.currentData() or "192k",
            "hw_accel": self.cmb_hw_accel.currentData() or "auto",
        }

    def output_ext(self, params: Dict[str, Any]) -> str:
        fmt = str(params.get("format", "mp4")).lower().lstrip(".")
        return f".{fmt}"

    def process(
        self,
        src: Path,
        dst: Path,
        params: Dict[str, Any],
        ctx: TaskContext,
    ) -> ItemResult:
        try:
            target_fmt = str(params.get("format", "mp4")).lower()
            audio_only = bool(params.get("extract_audio", False))
            target_mb = float(params.get("target_size_mb", 0.0) or 0.0)
            fps = int(params.get("gif_fps", 15))
            width = int(params.get("gif_width", 480))
            v_codec = str(params.get("video_codec", "auto"))
            max_h = int(params.get("max_height", 0) or 0)
            a_bitrate = str(params.get("audio_bitrate", "192k"))
            hw_mode = str(params.get("hw_accel", "auto"))

            convert_media_file(
                src,
                dst,
                target_format=target_fmt,
                extract_audio_only=audio_only,
                target_size_mb=target_mb if target_mb > 0 else None,
                gif_fps=fps,
                gif_width=width,
                hw_accel=hw_mode,
                video_codec=v_codec,
                max_height=max_h,
                audio_bitrate=a_bitrate,
            )

            bytes_out = dst.stat().st_size if dst.exists() else 0
            sz_mb = bytes_out / (1024 * 1024)
            return ItemResult(
                success=True,
                source_path=src,
                output_path=dst,
                message=f"Convertido com sucesso ({sz_mb:.2f} MB)",
                bytes_in=src.stat().st_size,
                bytes_out=bytes_out,
            )
        except Exception as exc:
            _log.warning("Falha ao converter mídia '%s': %s", src, exc)
            return ItemResult(
                success=False,
                source_path=src,
                error=f"Falha ao converter {src.name}: {exc}",
            )
