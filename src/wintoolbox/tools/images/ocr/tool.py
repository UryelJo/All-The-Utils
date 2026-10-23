"""
Ferramenta: Reconhecimento Óptico de Caracteres (OCR Local Offline).
Interface gráfica para carregar imagens, extrair texto com o motor nativo do Windows e copiar/salvar resultado.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QTextEdit,
    QVBoxLayout, QWidget
)

from wintoolbox.core.registry import TaskContext, Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.images.ocr.logic import perform_ocr_on_image


@register
class OcrTool(Tool):
    id = "images.ocr"
    name = "OCR de Imagem (Reconhecimento de Texto)"
    category = "Imagens"
    description = "Extração rápida de texto de imagens 100% offline via API nativa do Windows (Windows.Media.Ocr)"
    keywords = ["ocr", "texto", "reconhecimento", "imagem", "scan", "foto", "extrair", "leitura", "copiar"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return OcrView(self, parent)


class OcrView(QWidget):
    def __init__(self, tool: OcrTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_image_path: Optional[Path] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Barra Superior: Carregamento
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.txt_path = QLineEdit()
        self.txt_path.setPlaceholderText("Selecione um arquivo de imagem (PNG, JPG, WEBP, BMP, etc.)...")
        top_bar.addWidget(self.txt_path, 1)

        btn_browse = QPushButton("Procurar Imagem...")
        btn_browse.clicked.connect(self._on_browse_file)
        top_bar.addWidget(btn_browse)

        btn_paste = QPushButton("Colar da Área de Transferência")
        btn_paste.clicked.connect(self._on_paste_clipboard)
        top_bar.addWidget(btn_paste)

        self.btn_run = QPushButton("Extrair Texto (OCR)")
        self.btn_run.setProperty("class", "primary")
        self.btn_run.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.btn_run.clicked.connect(self._on_run_ocr)
        top_bar.addWidget(self.btn_run)

        layout.addLayout(top_bar)

        # Painel Central Dividido: Preview da Imagem vs Texto Extraído
        split_layout = QHBoxLayout()
        split_layout.setSpacing(12)

        # Esquerda: Preview da Imagem
        grp_prev = QGroupBox("Imagem de Origem")
        prev_layout = QVBoxLayout(grp_prev)
        self.scroll_prev = QScrollArea()
        self.scroll_prev.setWidgetResizable(True)
        self.lbl_preview = QLabel("Nenhuma imagem carregada.")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("color: #888890;")
        self.scroll_prev.setWidget(self.lbl_preview)
        prev_layout.addWidget(self.scroll_prev)
        split_layout.addWidget(grp_prev, 1)

        # Direita: Texto Reconhecido
        grp_text = QGroupBox("Texto Reconhecido (OCR)")
        text_layout = QVBoxLayout(grp_text)

        self.txt_result = QTextEdit()
        self.txt_result.setPlaceholderText("O texto detectado na imagem aparecerá aqui...")
        text_layout.addWidget(self.txt_result)

        bottom_act = QHBoxLayout()
        self.lbl_stats = QLabel("0 caracteres | 0 palavras")
        self.lbl_stats.setStyleSheet("color: #888890; font-size: 11px;")
        bottom_act.addWidget(self.lbl_stats)

        bottom_act.addStretch()

        btn_copy = QPushButton("Copiar Texto")
        btn_copy.clicked.connect(self._on_copy_text)
        bottom_act.addWidget(btn_copy)

        btn_save = QPushButton("Salvar como .txt...")
        btn_save.clicked.connect(self._on_save_text)
        bottom_act.addWidget(btn_save)

        text_layout.addLayout(bottom_act)
        split_layout.addWidget(grp_text, 1)

        layout.addLayout(split_layout)

    def _on_browse_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem para OCR",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp *.tiff);;Todos os Arquivos (*.*)"
        )
        if f:
            self._load_image(Path(f))

    def _on_paste_clipboard(self):
        clip = QApplication.clipboard()
        img = clip.image()
        if img.isNull():
            QMessageBox.warning(self, "Aviso", "Nenhuma imagem válida na área de transferência.")
            return

        temp_p = Path.home() / "AppData" / "Local" / "Temp" / "wtbx_ocr_paste.png"
        img.save(str(temp_p), "PNG")
        self._load_image(temp_p)

    def _load_image(self, path: Path):
        self._current_image_path = path
        self.txt_path.setText(str(path))

        pix = QPixmap(str(path))
        if not pix.isNull():
            scaled = pix.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_preview.setPixmap(scaled)
        else:
            self.lbl_preview.setText("Falha ao renderizar prévia da imagem.")

    def _on_run_ocr(self):
        if not self._current_image_path or not self._current_image_path.is_file():
            QMessageBox.warning(self, "Aviso", "Selecione ou cole uma imagem primeiro.")
            return

        self.btn_run.setEnabled(False)
        self.txt_result.setText("Processando imagem com o motor de OCR local...")

        def _work(ctx: TaskContext):
            ctx.progress(20, 100, "Executando reconhecimento de caracteres...")
            txt = perform_ocr_on_image(self._current_image_path)
            ctx.progress(100, 100, "Concluído!")
            return txt

        def _done(result, exc):
            self.btn_run.setEnabled(True)
            if exc:
                self.txt_result.setText(f"Erro ao processar OCR: {exc}")
                QMessageBox.critical(self, "Erro", f"Falha no OCR: {exc}")
            else:
                text_content = result or ""
                self.txt_result.setText(text_content)
                chars = len(text_content)
                words = len(text_content.split())
                self.lbl_stats.setText(f"{chars} caracteres | {words} palavras")

        run_task(_work, on_done=_done)

    def _on_copy_text(self):
        t = self.txt_result.toPlainText()
        if t:
            QApplication.clipboard().setText(t)
            QMessageBox.information(self, "Copiado", "Texto copiado para a área de transferência!")

    def _on_save_text(self):
        t = self.txt_result.toPlainText()
        if not t:
            QMessageBox.warning(self, "Aviso", "Nenhum texto para salvar.")
            return

        f, _ = QFileDialog.getSaveFileName(self, "Salvar Texto OCR", "texto_extraido.txt", "Arquivo de Texto (*.txt)")
        if f:
            Path(f).write_text(t, encoding="utf-8")
            QMessageBox.information(self, "Sucesso", f"Texto salvo com sucesso em:\n{f}")
