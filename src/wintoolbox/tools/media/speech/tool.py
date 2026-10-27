"""
Ferramenta: Texto para Voz (TTS) Local.
Sintetizador de voz 100% offline utilizando o motor de fala nativo do Windows.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QSlider, QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.media.speech.logic import (
    get_available_voices, save_speech_to_file, speak_text
)


@register
class MediaSpeechTool(Tool):
    id = "media.speech"
    name = "Texto para Voz (TTS Local)"
    category = "Áudio e Vídeo"
    description = "Síntese de texto para fala (Text-to-Speech): converte textos em áudio narrado com as vozes nativas instaladas no Windows e salva em arquivo .wav."
    keywords = ["tts", "voz", "texto para fala", "audio", "sapi", "pyttsx3", "narrador", "falar", "offline"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QFrame(parent)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        header = QLabel("Texto para Voz (Sintetizador Local)")
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        main_layout.addWidget(header)

        # Entrada de Texto
        lbl_input = QLabel("Digite ou cole o texto que deseja sintetizar:")
        main_layout.addWidget(lbl_input)

        self.txt_content = QPlainTextEdit()
        self.txt_content.setPlaceholderText("Escreva aqui o texto para a voz ler...")
        self.txt_content.setPlainText("Bem-vindo ao All the Utils! Esta é uma demonstração de síntese de voz nativa no Windows.")
        self.txt_content.setStyleSheet("font-family: 'Segoe UI', sans-serif; font-size: 13px;")
        main_layout.addWidget(self.txt_content, stretch=1)

        # Configurações de Voz
        grp_opts = QGroupBox("Configurações do Narrador")
        grid = QGridLayout(grp_opts)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Voz do sistema:"), 0, 0)
        self.cmb_voices = QComboBox()
        try:
            voices = get_available_voices()
            for v in voices:
                self.cmb_voices.addItem(v["name"], v["id"])
        except Exception:
            self.cmb_voices.addItem("Voz Padrão do Sistema", None)
        grid.addWidget(self.cmb_voices, 0, 1)

        grid.addWidget(QLabel("Velocidade da fala:"), 1, 0)
        row_rate = QHBoxLayout()
        self.spin_rate = QSpinBox()
        self.spin_rate.setRange(50, 400)
        self.spin_rate.setValue(160)
        self.spin_rate.setSuffix(" ppm")
        row_rate.addWidget(self.spin_rate)
        grid.addLayout(row_rate, 1, 1)

        grid.addWidget(QLabel("Volume da voz:"), 2, 0)
        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(10, 100)
        self.slider_volume.setValue(100)
        grid.addWidget(self.slider_volume, 2, 1)

        main_layout.addWidget(grp_opts)

        # Ações
        act_box = QHBoxLayout()
        self.lbl_status = QLabel("")
        act_box.addWidget(self.lbl_status)
        act_box.addStretch()

        self.btn_speak = QPushButton("Ouvir Agora")
        self.btn_speak.setProperty("class", "primary")
        self.btn_speak.clicked.connect(self._on_speak)
        act_box.addWidget(self.btn_speak)

        self.btn_save = QPushButton("Salvar como Arquivo de Áudio...")
        self.btn_save.clicked.connect(self._on_save_audio)
        act_box.addWidget(self.btn_save)

        main_layout.addLayout(act_box)
        return container

    def _on_speak(self):
        text = self.txt_content.toPlainText().strip()
        if not text:
            QMessageBox.warning(None, "Aviso", "O texto para fala não pode estar vazio.")
            return

        voice_id = self.cmb_voices.currentData()
        rate = self.spin_rate.value()
        vol = self.slider_volume.value() / 100.0

        self.btn_speak.setEnabled(False)
        self.lbl_status.setText("Reproduzindo fala...")

        def _work(ctx: TaskContext):
            speak_text(text, voice_id=voice_id, rate=rate, volume=vol)
            return True

        def _done(result, exc):
            self.btn_speak.setEnabled(True)
            if exc:
                self.lbl_status.setText(f"Erro: {exc}")
                QMessageBox.critical(None, "Erro", f"Falha ao sintetizar voz: {exc}")
            else:
                self.lbl_status.setText("Reprodução concluída.")

        run_task(_work, on_done=_done)

    def _on_save_audio(self):
        text = self.txt_content.toPlainText().strip()
        if not text:
            QMessageBox.warning(None, "Aviso", "O texto para fala não pode estar vazio.")
            return

        file, _ = QFileDialog.getSaveFileName(None, "Salvar Áudio de Fala", "voz_sintetizada.wav", "Áudio WAV (*.wav)")
        if not file:
            return

        voice_id = self.cmb_voices.currentData()
        rate = self.spin_rate.value()
        vol = self.slider_volume.value() / 100.0

        self.btn_save.setEnabled(False)
        self.lbl_status.setText("Gravando áudio em arquivo...")

        def _work(ctx: TaskContext):
            return save_speech_to_file(text, Path(file), voice_id=voice_id, rate=rate, volume=vol)

        def _done(result, exc):
            self.btn_save.setEnabled(True)
            if exc:
                self.lbl_status.setText(f"Erro: {exc}")
                QMessageBox.critical(None, "Erro", f"Falha ao salvar áudio: {exc}")
            else:
                self.lbl_status.setText("Áudio gravado com sucesso!")
                QMessageBox.information(None, "Sucesso", f"Áudio de fala gravado com sucesso em:\n{result}")

        run_task(_work, on_done=_done)
