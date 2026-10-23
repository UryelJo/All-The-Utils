"""
Ferramenta: Downloader de Mídia Multiplataforma.
Interface para download de vídeos e músicas de centenas de sites com yt-dlp.
"""
import os
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.media.downloader.logic import download_media_url


@register
class MediaDownloaderTool(Tool):
    id = "media.downloader"
    name = "Downloader de Mídia"
    category = "Áudio e Vídeo"
    description = "Baixe vídeos e áudios do YouTube, TikTok, Instagram, Twitter/X e dezenas de plataformas via yt-dlp"
    keywords = ["video", "download", "youtube", "tiktok", "instagram", "twitter", "yt-dlp", "musica", "mp3", "mp4"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        container = QFrame(parent)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        header = QLabel("Downloader de Mídia Multiplataforma")
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        main_layout.addWidget(header)

        lbl_desc = QLabel("Insira a URL do vídeo ou publicação para realizar o download direto:")
        main_layout.addWidget(lbl_desc)

        # Entrada de URL
        grp_url = QGroupBox("Endereço de Mídia (URL)")
        grid_url = QGridLayout(grp_url)
        grid_url.addWidget(QLabel("URL do vídeo/áudio:"), 0, 0)
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("https://www.youtube.com/watch?v=... ou link do TikTok / Instagram / Twitter")
        grid_url.addWidget(self.txt_url, 0, 1)

        btn_paste = QPushButton("Colar URL")
        btn_paste.clicked.connect(self._on_paste_url)
        grid_url.addWidget(btn_paste, 0, 2)
        main_layout.addWidget(grp_url)

        # Configurações de Download
        grp_opts = QGroupBox("Formato e Resolução")
        grid_opts = QGridLayout(grp_opts)

        grid_opts.addWidget(QLabel("Tipo de download:"), 0, 0)
        self.cmb_type = QComboBox()
        self.cmb_type.addItem("Vídeo com Áudio (MP4)", "video")
        self.cmb_type.addItem("Apenas Áudio (Converter para MP3 192k)", "audio")
        self.cmb_type.currentIndexChanged.connect(self._on_type_changed)
        grid_opts.addWidget(self.cmb_type, 0, 1)

        self.lbl_qual = QLabel("Qualidade máxima de vídeo:")
        grid_opts.addWidget(self.lbl_qual, 0, 2)
        self.cmb_quality = QComboBox()
        self.cmb_quality.addItem("Melhor Disponível (Original)", "best")
        self.cmb_quality.addItem("Full HD (1080p)", "1080p")
        self.cmb_quality.addItem("HD (720p)", "720p")
        self.cmb_quality.addItem("Padrão (480p)", "480p")
        grid_opts.addWidget(self.cmb_quality, 0, 3)

        main_layout.addWidget(grp_opts)

        # Pasta de Destino
        grp_dst = QGroupBox("Pasta de Download")
        grid_dst = QGridLayout(grp_dst)
        grid_dst.addWidget(QLabel("Salvar em:"), 0, 0)
        self.txt_output_dir = QLineEdit()
        default_dl = Path.home() / "Downloads"
        self.txt_output_dir.setText(str(default_dl))
        grid_dst.addWidget(self.txt_output_dir, 0, 1)

        btn_browse = QPushButton("Procurar...")
        btn_browse.clicked.connect(self._on_browse_output_dir)
        grid_dst.addWidget(btn_browse, 0, 2)
        main_layout.addWidget(grp_dst)

        # Barra de Progresso e Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # Ações
        act_box = QHBoxLayout()
        self.lbl_status = QLabel("Pronto para download.")
        act_box.addWidget(self.lbl_status)
        act_box.addStretch()

        self.btn_download = QPushButton("Iniciar Download")
        self.btn_download.setProperty("class", "primary")
        self.btn_download.clicked.connect(self._on_start_download)
        act_box.addWidget(self.btn_download)

        main_layout.addLayout(act_box)
        main_layout.addStretch()
        return container

    def _on_paste_url(self):
        text = os.environ.get("CLIPBOARD_TEXT", "")
        # PySide clipboard
        from PySide6.QtWidgets import QApplication
        cb_text = QApplication.clipboard().text()
        if cb_text and "http" in cb_text:
            self.txt_url.setText(cb_text.strip())

    def _on_type_changed(self):
        is_audio = (self.cmb_type.currentData() == "audio")
        self.lbl_qual.setVisible(not is_audio)
        self.cmb_quality.setVisible(not is_audio)

    def _on_browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(None, "Selecionar Pasta de Download")
        if folder:
            self.txt_output_dir.setText(folder)

    def _on_start_download(self):
        url = self.txt_url.text().strip()
        if not url:
            QMessageBox.warning(None, "Aviso", "Por favor, insira a URL da mídia.")
            return

        out_dir = self.txt_output_dir.text().strip()
        if not out_dir:
            QMessageBox.warning(None, "Aviso", "Informe a pasta de download.")
            return

        is_audio = (self.cmb_type.currentData() == "audio")
        qual = self.cmb_quality.currentData()

        self.btn_download.setEnabled(False)
        self.progress_bar.setValue(10)
        self.lbl_status.setText("Conectando e baixando mídia...")

        def _work(ctx: TaskContext):
            def _hook(d):
                if d.get("status") == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    downloaded = d.get("downloaded_bytes", 0)
                    if total > 0:
                        pct = int(downloaded / total * 100)
                        ctx.progress(pct, 100, f"Baixando: {pct}%")

            return download_media_url(
                url,
                Path(out_dir),
                audio_only=is_audio,
                quality=qual,
                progress_hook=_hook
            )

        def _done(result, exc):
            self.btn_download.setEnabled(True)
            if exc:
                self.progress_bar.setValue(0)
                self.lbl_status.setText(f"Erro: {exc}")
                QMessageBox.critical(None, "Erro", f"Falha ao realizar download: {exc}")
            else:
                self.progress_bar.setValue(100)
                title = result.get("title", "")
                self.lbl_status.setText(f"Concluído: {title}")
                QMessageBox.information(
                    None,
                    "Sucesso",
                    f"Download concluído com sucesso!\n\nTítulo: {title}\nSalvo em: {out_dir}"
                )

        run_task(_work, on_done=_done)
