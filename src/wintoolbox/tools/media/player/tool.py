"""
Ferramenta: Player de Áudio e Vídeo Embutido.
Interface de reprodução nativa utilizando QMediaPlayer e QVideoWidget do PySide6.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import QUrl, Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSlider, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.media.player.logic import format_duration


@register
class MediaPlayerTool(Tool):
    id = "media.player"
    name = "Player de Áudio e Vídeo"
    category = "Áudio e Vídeo"
    description = "Reprodutor de mídia leve e rápido: player nativo de áudio e vídeo com controle de volume, barra de progresso, repetição e modo tela cheia."
    keywords = ["player", "reprodutor", "video", "audio", "mp4", "mp3", "tocar", "multimedia"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QFrame(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Cabeçalho
        header_row = QHBoxLayout()
        header = QLabel("Player de Áudio e Vídeo")
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        header_row.addWidget(header)
        header_row.addStretch()

        btn_open = QPushButton("Abrir Arquivo de Mídia...")
        btn_open.clicked.connect(self._on_open_file)
        header_row.addWidget(btn_open)
        layout.addLayout(header_row)

        # Widget de Vídeo
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000; border-radius: 6px;")
        layout.addWidget(self.video_widget, stretch=1)

        # Configuração do QMediaPlayer
        self.player = QMediaPlayer(container)
        self.audio_output = QAudioOutput(container)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)

        # Barra de Seek / Progresso
        self.slider_progress = QSlider(Qt.Horizontal)
        self.slider_progress.setRange(0, 0)
        self.slider_progress.sliderMoved.connect(self._set_position)
        layout.addWidget(self.slider_progress)

        # Barra de Controles Inferior
        controls_row = QHBoxLayout()
        controls_row.setSpacing(10)

        self.btn_play = QPushButton("Reproduzir")
        self.btn_play.setProperty("class", "primary")
        self.btn_play.clicked.connect(self._on_toggle_play)
        controls_row.addWidget(self.btn_play)

        self.btn_stop = QPushButton("Parar")
        self.btn_stop.clicked.connect(self._on_stop)
        controls_row.addWidget(self.btn_stop)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        controls_row.addWidget(self.lbl_time)

        controls_row.addStretch()

        controls_row.addWidget(QLabel("Volume:"))
        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(80)
        self.slider_volume.setFixedWidth(100)
        self.slider_volume.valueChanged.connect(self._on_volume_changed)
        controls_row.addWidget(self.slider_volume)

        layout.addLayout(controls_row)

        # Volume inicial
        self.audio_output.setVolume(0.8)

        return container

    def _on_open_file(self):
        file, _ = QFileDialog.getOpenFileName(
            None,
            "Abrir Mídia",
            "",
            "Mídias (*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.flac *.m4a);;Todos (*.*)"
        )
        if file:
            self.player.setSource(QUrl.fromLocalFile(file))
            self.player.play()
            self.btn_play.setText("Pausar")

    def _on_toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.btn_play.setText("Reproduzir")
        else:
            self.player.play()
            self.btn_play.setText("Pausar")

    def _on_stop(self):
        self.player.stop()
        self.btn_play.setText("Reproduzir")

    def _on_position_changed(self, position: int):
        if not self.slider_progress.isSliderDown():
            self.slider_progress.setValue(position)
        dur = self.player.duration()
        self.lbl_time.setText(f"{format_duration(position)} / {format_duration(dur)}")

    def _on_duration_changed(self, duration: int):
        self.slider_progress.setRange(0, duration)
        pos = self.player.position()
        self.lbl_time.setText(f"{format_duration(pos)} / {format_duration(duration)}")

    def _set_position(self, position: int):
        self.player.setPosition(position)

    def _on_volume_changed(self, value: int):
        self.audio_output.setVolume(value / 100.0)
