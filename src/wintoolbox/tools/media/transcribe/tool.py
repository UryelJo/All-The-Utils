"""
Interface gráfica da ferramenta Transcrição de Áudio Offline (media.transcribe).
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import TaskRunner
from wintoolbox.tools.media.transcribe.logic import (
    get_available_engine, is_whisper_available,
    segments_to_plain_text, segments_to_srt, transcribe_audio_file
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("media.transcribe.ui")


@register
class TranscribeTool(Tool):
    id = "media.transcribe"
    name = "Transcrição de Áudio Offline (Whisper)"
    category = "Imagens"
    description = "Transcreva gravações, podcasts e vídeos para texto ou legendas SRT 100% offline utilizando Inteligência Artificial Whisper"
    keywords = ["transcricao", "audio", "whisper", "faster-whisper", "voz", "texto", "legenda", "srt", "ia", "offline"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return TranscribeView(self, parent)


class TranscribeView(QWidget):
    def __init__(self, tool: TranscribeTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._segments: List[Dict[str, Any]] = []
        self._is_running = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(self.tool.name, self.tool.description))

        if not is_whisper_available():
            card_warn = QFrame()
            card_warn.setObjectName("Card")
            w_lay = QVBoxLayout(card_warn)
            w_lay.setContentsMargins(16, 16, 16, 16)
            w_lay.setSpacing(10)

            title_w = QLabel("Mecanismo de IA (faster-whisper) não instalado")
            title_w.setStyleSheet("font-weight: 600; font-size: 14px; color: #f59e0b;")
            w_lay.addWidget(title_w)

            desc_w = QLabel(
                "A transcrição de áudio por Inteligência Artificial é um recurso opcional devido ao download\n"
                "de modelos neurais locais. Para habilitar a transcrição offline no seu computador, instale a biblioteca com o comando abaixo:"
            )
            desc_w.setWordWrap(True)
            w_lay.addWidget(desc_w)

            cmd_row = QHBoxLayout()
            txt_cmd = QLineEdit("pip install faster-whisper")
            txt_cmd.setReadOnly(True)
            cmd_row.addWidget(txt_cmd, stretch=1)

            btn_copy_cmd = QPushButton("Copiar Comando")
            btn_copy_cmd.clicked.connect(lambda: QApplication.clipboard().setText("pip install faster-whisper"))
            cmd_row.addWidget(btn_copy_cmd)

            w_lay.addLayout(cmd_row)
            layout.addWidget(card_warn)

        # Barra de seleção de arquivo
        top_card = QFrame()
        top_card.setObjectName("Card")
        t_lay = QHBoxLayout(top_card)
        t_lay.setContentsMargins(14, 12, 14, 12)
        t_lay.setSpacing(10)

        t_lay.addWidget(QLabel("Arquivo de Áudio / Vídeo:"))
        self.txt_file = QLineEdit()
        self.txt_file.setPlaceholderText("Selecione um arquivo .mp3, .wav, .m4a, .mp4, .mkv...")
        t_lay.addWidget(self.txt_file, stretch=1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._browse_file)
        t_lay.addWidget(btn_browse)

        layout.addWidget(top_card)

        # Configurações do Modelo e Idioma
        cfg_card = QFrame()
        cfg_card.setObjectName("Card")
        c_lay = QHBoxLayout(cfg_card)
        c_lay.setContentsMargins(14, 10, 14, 10)
        c_lay.setSpacing(12)

        c_lay.addWidget(QLabel("Modelo Whisper:"))
        self.cmb_model = QComboBox()
        self.cmb_model.addItem("Tiny (Ultrarrápido, ~75MB)", "tiny")
        self.cmb_model.addItem("Base (Equilibrado e leve, ~140MB)", "base")
        self.cmb_model.addItem("Small (Mais preciso, ~460MB)", "small")
        self.cmb_model.setCurrentIndex(1)
        c_lay.addWidget(self.cmb_model)

        c_lay.addWidget(QLabel("Idioma do Áudio:"))
        self.cmb_lang = QComboBox()
        self.cmb_lang.addItem("Português (pt)", "pt")
        self.cmb_lang.addItem("Inglês (en)", "en")
        self.cmb_lang.addItem("Espanhol (es)", "es")
        self.cmb_lang.addItem("Detectar Automaticamente", "auto")
        c_lay.addWidget(self.cmb_lang)

        c_lay.addStretch()

        self.btn_transcribe = QPushButton("Transcrever Áudio")
        self.btn_transcribe.setProperty("class", "accent")
        self.btn_transcribe.setStyleSheet("padding: 7px 18px; font-weight: 600;")
        self.btn_transcribe.clicked.connect(self._start_transcribe)
        c_lay.addWidget(self.btn_transcribe)

        layout.addWidget(cfg_card)

        # Barra de Progresso e Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel(f"Motor detectado: {get_available_engine()}")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self.lbl_status)

        # Caixa de Texto de Saída
        self.txt_output = QPlainTextEdit()
        self.txt_output.setPlaceholderText("O texto transcrito pelo modelo aparecerá aqui...")
        self.txt_output.setStyleSheet("font-size: 13px; line-height: 1.5;")
        layout.addWidget(self.txt_output, stretch=1)

        # Barra de Ações Inferior
        bottom_bar = QHBoxLayout()
        self.lbl_stats = QLabel("0 palavras | 0 caracteres")
        self.lbl_stats.setStyleSheet("color: #888888; font-size: 12px;")
        bottom_bar.addWidget(self.lbl_stats)

        bottom_bar.addStretch()

        btn_copy = QPushButton("Copiar Texto")
        btn_copy.clicked.connect(self._copy_text)
        bottom_bar.addWidget(btn_copy)

        btn_save_txt = QPushButton("Salvar como .txt...")
        btn_save_txt.clicked.connect(self._save_txt)
        bottom_bar.addWidget(btn_save_txt)

        btn_save_srt = QPushButton("Salvar Legenda (.srt)...")
        btn_save_srt.clicked.connect(self._save_srt)
        bottom_bar.addWidget(btn_save_srt)

        layout.addLayout(bottom_bar)

    def _browse_file(self) -> None:
        p, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Arquivo de Mídia",
            "",
            "Áudio e Vídeo (*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.mp4 *.mkv *.mov *.avi *.webm);;Todos (*.*)"
        )
        if p:
            self.txt_file.setText(p)

    def _start_transcribe(self) -> None:
        if self._is_running:
            return

        f_str = self.txt_file.text().strip()
        if not f_str or not Path(f_str).is_file():
            show_toast(self, "Selecione um arquivo de áudio ou vídeo existente.", kind="error")
            return

        if not is_whisper_available():
            QMessageBox.warning(
                self,
                "Dependência Ausente",
                "Para transcrever áudio localmente, instale o motor faster-whisper:\n\n"
                "pip install faster-whisper\n\n"
                "Após a instalação, reabra a ferramenta."
            )
            return

        media_path = Path(f_str)
        model_size = self.cmb_model.currentData()
        language = self.cmb_lang.currentData()

        self._is_running = True
        self.btn_transcribe.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.lbl_status.setText("Iniciando transcrição de áudio...")

        def _worker():
            def _cb(msg):
                self.lbl_status.setText(msg)
            return transcribe_audio_file(media_path, model_size=model_size, language=language, progress_cb=_cb)

        def _on_done(segments):
            self._is_running = False
            self.btn_transcribe.setEnabled(True)
            self.progress_bar.setVisible(False)
            self._segments = segments
            full_text = segments_to_plain_text(segments)
            self.txt_output.setPlainText(full_text)
            self.lbl_status.setText(f"Transcrição concluída com sucesso! ({len(segments)} segmentos encontrados)")
            words = len(full_text.split())
            chars = len(full_text)
            self.lbl_stats.setText(f"{words:,} palavras | {chars:,} caracteres")
            show_toast(self, "Áudio transcrito com sucesso!", kind="success")

        def _on_error(err):
            self._is_running = False
            self.btn_transcribe.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.lbl_status.setText(f"Erro na transcrição: {err}")
            show_toast(self, f"Erro: {err}", kind="error")

        TaskRunner.run(_worker, on_success=_on_done, on_error=_on_error)

    def _copy_text(self) -> None:
        txt = self.txt_output.toPlainText()
        if txt:
            QApplication.clipboard().setText(txt)
            show_toast(self, "Texto copiado para a área de transferência!", kind="success")

    def _save_txt(self) -> None:
        txt = self.txt_output.toPlainText()
        if not txt:
            show_toast(self, "Nenhum texto para salvar.", kind="error")
            return
        p, _ = QFileDialog.getSaveFileName(self, "Salvar Texto", "transcricao.txt", "Documento de Texto (*.txt)")
        if p:
            Path(p).write_text(txt, encoding="utf-8")
            show_toast(self, "Arquivo .txt salvo com sucesso!", kind="success")

    def _save_srt(self) -> None:
        if not self._segments:
            show_toast(self, "Transcreva um arquivo primeiro para gerar legendas com tempos.", kind="error")
            return
        srt_text = segments_to_srt(self._segments)
        p, _ = QFileDialog.getSaveFileName(self, "Salvar Legenda", "legenda.srt", "Legenda SubRip (*.srt)")
        if p:
            Path(p).write_text(srt_text, encoding="utf-8")
            show_toast(self, "Legenda .srt salva com sucesso!", kind="success")
