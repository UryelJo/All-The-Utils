"""
Ferramenta: Reconhecimento Óptico de Caracteres (OCR Local Offline).
Interface gráfica com visualizador com zoom, seleção de região pontilhada (ROI)
e barra de pós-processamento e formatação de texto.
"""
from pathlib import Path
import re
import tempfile
from typing import Optional
from PIL import Image

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QTextEdit,
    QVBoxLayout, QWidget
)

from wintoolbox.core.elevation import bind_admin_prompt_on_show, is_admin, prompt_elevation_dialog
from wintoolbox.core.registry import Tool, register
from wintoolbox.core.tasks import run_task
from wintoolbox.tools.images.ocr.logic import NO_TEXT_MESSAGE, perform_ocr_on_image
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.zoomable_image import ZoomableImageCanvas


@register
class OcrTool(Tool):
    id = "images.ocr"
    name = "OCR de Imagem"
    category = "Imagens"
    description = "Extração rápida de texto de imagens 100% offline via API nativa do Windows (Windows.Media.Ocr)"
    keywords = ["ocr", "texto", "reconhecimento", "imagem", "scan", "foto", "extrair", "leitura", "copiar"]
    requires_admin = True

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return OcrView(self, parent)


class OcrView(QWidget):
    def __init__(self, tool: OcrTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_image_path: Optional[Path] = None
        self._temp_files: list = []
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
        top_bar.addWidget(self.txt_path, stretch=1)

        btn_browse = QPushButton("Procurar Imagem...")
        btn_browse.clicked.connect(self._on_browse_file)
        top_bar.addWidget(btn_browse)

        btn_paste = QPushButton("Colar da Área de Transferência")
        btn_paste.clicked.connect(self._on_paste_clipboard)
        top_bar.addWidget(btn_paste)

        self.btn_run = QPushButton("Extrair Texto (OCR)")
        self.btn_run.setProperty("class", "primary")
        self.btn_run.setStyleSheet("font-weight: bold; padding: 6px 18px;")
        self.btn_run.clicked.connect(self._on_run_ocr)
        top_bar.addWidget(self.btn_run)

        layout.addLayout(top_bar)

        # Painel Central Dividido: Preview com Zoom e ROI vs Editor com Formatação
        split_layout = QHBoxLayout()
        split_layout.setSpacing(12)

        # Esquerda: Imagem com ROI
        grp_prev = QGroupBox("Imagem de Origem (Arraste para selecionar região pontilhada)")
        prev_layout = QVBoxLayout(grp_prev)
        prev_layout.setSpacing(6)

        row_roi_btns = QHBoxLayout()
        self.btn_toggle_roi = QPushButton("Selecionar Região Específica")
        self.btn_toggle_roi.setCheckable(True)
        self.btn_toggle_roi.setChecked(True)
        self.btn_toggle_roi.toggled.connect(self._on_toggle_roi)
        row_roi_btns.addWidget(self.btn_toggle_roi)

        self.btn_clear_roi = QPushButton("Usar Imagem Inteira")
        self.btn_clear_roi.clicked.connect(self._on_clear_roi)
        row_roi_btns.addWidget(self.btn_clear_roi)
        row_roi_btns.addStretch()
        prev_layout.addLayout(row_roi_btns)

        self.canvas = ZoomableImageCanvas(self)
        self.canvas.set_roi_selection_enabled(True)
        prev_layout.addWidget(self.canvas, stretch=1)
        split_layout.addWidget(grp_prev, stretch=1)

        # Direita: Texto Reconhecido e Barra de Formatação
        grp_text = QGroupBox("Texto Reconhecido (OCR)")
        text_layout = QVBoxLayout(grp_text)
        text_layout.setSpacing(6)

        # Barra de ferramentas de formatação de texto
        tb_text = QHBoxLayout()
        tb_text.setContentsMargins(0, 4, 0, 8)
        tb_text.setSpacing(8)

        btn_join = QPushButton("Juntar Parágrafos")
        btn_join.setFixedHeight(26)
        btn_join.setToolTip("Substitui quebras de linha simples por espaços")
        btn_join.clicked.connect(self._format_join_paragraphs)
        tb_text.addWidget(btn_join)

        btn_spaces = QPushButton("Limpar Espaços")
        btn_spaces.setFixedHeight(26)
        btn_spaces.setToolTip("Remove múltiplos espaços seguidos")
        btn_spaces.clicked.connect(self._format_clean_spaces)
        tb_text.addWidget(btn_spaces)

        btn_upper = QPushButton("MAIÚSCULAS")
        btn_upper.setFixedHeight(26)
        btn_upper.clicked.connect(self._format_upper)
        tb_text.addWidget(btn_upper)

        btn_lower = QPushButton("minúsculas")
        btn_lower.setFixedHeight(26)
        btn_lower.clicked.connect(self._format_lower)
        tb_text.addWidget(btn_lower)

        tb_text.addStretch()

        tb_text.addWidget(QLabel("Tamanho:"))
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setFixedWidth(64)
        self.spin_font_size.setRange(10, 24)
        self.spin_font_size.setValue(12)
        self.spin_font_size.valueChanged.connect(self._on_font_size_changed)
        tb_text.addWidget(self.spin_font_size)

        text_layout.addLayout(tb_text)
        text_layout.addSpacing(4)

        self.txt_result = QTextEdit()
        self.txt_result.setPlaceholderText("O texto detectado na imagem aparecerá aqui...")
        self.txt_result.textChanged.connect(self._update_stats)
        text_layout.addWidget(self.txt_result, stretch=1)

        bottom_act = QHBoxLayout()
        self.lbl_stats = QLabel("0 caracteres | 0 palavras")
        self.lbl_stats.setStyleSheet("color: #888890; font-size: 11px;")
        bottom_act.addWidget(self.lbl_stats)

        bottom_act.addStretch()

        btn_copy = QPushButton("Copiar Texto")
        btn_copy.clicked.connect(self._on_copy_text)
        bottom_act.addWidget(btn_copy)

        btn_save_txt = QPushButton("Salvar .TXT...")
        btn_save_txt.clicked.connect(lambda: self._on_save_file("txt"))
        bottom_act.addWidget(btn_save_txt)

        btn_save_md = QPushButton("Salvar .MD...")
        btn_save_md.clicked.connect(lambda: self._on_save_file("md"))
        bottom_act.addWidget(btn_save_md)

        text_layout.addLayout(bottom_act)
        split_layout.addWidget(grp_text, stretch=1)

        layout.addLayout(split_layout)

        bind_admin_prompt_on_show(
            self,
            tool_name="Reconhecimento OCR",
            reason="O motor OCR nativo do Windows (WinRT) requer privilégios de Administrador para acessar determinados pacotes de idiomas e serviços do sistema.",
        )

    def _on_toggle_roi(self, checked: bool):
        self.canvas.set_roi_selection_enabled(checked)

    def _on_clear_roi(self):
        self.canvas.clear_roi()
        show_toast(self, "Seleção limpa: OCR usará a imagem inteira")

    def _on_browse_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem para OCR",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.jfif);;Todos (*.*)"
        )
        if f:
            self._load_image(Path(f))

    def _on_paste_clipboard(self):
        clipboard = QApplication.clipboard()
        img = clipboard.image()
        if img.isNull():
            QMessageBox.warning(self, "Aviso", "A área de transferência não contém uma imagem válida.")
            return

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        img.save(str(tmp_path), "PNG")
        self._temp_files.append(tmp_path)
        self._load_image(tmp_path)

    def _load_image(self, path: Path):
        self._current_image_path = path
        self.txt_path.setText(str(path))
        pix = QPixmap(str(path))
        if not pix.isNull():
            self.canvas.set_pixmap(pix, auto_fit=True)
            self.canvas.clear_roi()
        else:
            QMessageBox.critical(self, "Erro", "Não foi possível carregar a imagem especificada.")

    def _on_run_ocr(self):
        if not self._current_image_path or not self._current_image_path.exists():
            QMessageBox.warning(self, "Aviso", "Por favor, carregue uma imagem antes de extrair o texto.")
            return

        if not is_admin():
            if prompt_elevation_dialog(
                self,
                tool_name="Reconhecimento OCR",
                reason="O motor OCR do Windows exige privilégios de Administrador para inicializar e consultar os pacotes de idiomas instalados.",
            ):
                return

        roi = self.canvas.get_roi()
        if roi and roi.width() > 5 and roi.height() > 5:
            # Recorta região selecionada para arquivo temporário
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                crop_tmp = Path(tmp.name)
            self._temp_files.append(crop_tmp)
            with Image.open(self._current_image_path) as im:
                cropped = im.crop((roi.x(), roi.y(), roi.x() + roi.width(), roi.y() + roi.height()))
                cropped.save(crop_tmp, format="PNG")
            target_file = crop_tmp
            toast_msg = "Reconhecendo texto da região selecionada..."
        else:
            target_file = self._current_image_path
            toast_msg = "Reconhecendo texto da imagem inteira..."

        self.btn_run.setEnabled(False)
        self.btn_run.setText("Extraindo...")
        show_toast(self, toast_msg)

        def _worker(ctx):
            return perform_ocr_on_image(target_file)

        def _done(res):
            self.btn_run.setEnabled(True)
            self.btn_run.setText("Extrair Texto (OCR)")
            self.txt_result.setPlainText(res or NO_TEXT_MESSAGE)
            show_toast(self, "OCR concluído!")

        def _error(err):
            self.btn_run.setEnabled(True)
            self.btn_run.setText("Extrair Texto (OCR)")
            QMessageBox.critical(self, "Erro no OCR", f"Falha ao executar reconhecimento: {err}")

        run_task(_worker, on_success=_done, on_error=_error)

    # Formatação de Texto
    def _format_join_paragraphs(self):
        text = self.txt_result.toPlainText()
        # Junta linhas que não sejam parágrafos duplos
        paragraphs = text.split("\n\n")
        joined = [" ".join(p.splitlines()) for p in paragraphs]
        self.txt_result.setPlainText("\n\n".join(joined))

    def _format_clean_spaces(self):
        text = self.txt_result.toPlainText()
        cleaned = re.sub(r"[ \t]+", " ", text)
        self.txt_result.setPlainText(cleaned)

    def _format_upper(self):
        self.txt_result.setPlainText(self.txt_result.toPlainText().upper())

    def _format_lower(self):
        self.txt_result.setPlainText(self.txt_result.toPlainText().lower())

    def _on_font_size_changed(self, sz: int):
        f = self.txt_result.font()
        f.setPointSize(sz)
        self.txt_result.setFont(f)

    def _update_stats(self):
        text = self.txt_result.toPlainText()
        chars = len(text)
        words = len(text.split())
        self.lbl_stats.setText(f"{chars} caracteres | {words} palavras")

    def _on_copy_text(self):
        text = self.txt_result.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        show_toast(self, "Texto copiado para a área de transferência!")

    def _on_save_file(self, ext: str):
        text = self.txt_result.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Aviso", "Não há texto para salvar.")
            return

        filter_str = "Documento de Texto (*.txt)" if ext == "txt" else "Markdown (*.md)"
        dest, _ = QFileDialog.getSaveFileName(self, "Salvar Texto", f"texto_extraido.{ext}", filter_str)
        if dest:
            Path(dest).write_text(text, encoding="utf-8")
            show_toast(self, f"Arquivo salvo com sucesso:\n{dest}")
