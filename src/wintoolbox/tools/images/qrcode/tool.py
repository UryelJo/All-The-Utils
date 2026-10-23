"""
Ferramenta: Gerador e Leitor de QR Code.
Interface gráfica em abas para gerar QR Codes com personalização de cores e leitura a partir de arquivos.
"""
from io import BytesIO
from pathlib import Path
from typing import Optional
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QFileDialog, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.images.qrcode.logic import (
    decode_qrcode_from_image, generate_qrcode
)


@register
class QrCodeTool(Tool):
    id = "images.qrcode"
    name = "Gerador e Leitor de QR Code"
    category = "Imagens"
    description = "Geração de QR Codes personalizados com cores, cópia direta da imagem e leitura de códigos a partir de fotos"
    keywords = ["qrcode", "qr", "código", "barras", "link", "wifi", "gerador", "leitor", "escanear"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return QrCodeView(self, parent)


class QrCodeView(QWidget):
    def __init__(self, tool: QrCodeTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_qr_img: Optional[Image.Image] = None
        self._fill_color = "#000000"
        self._back_color = "#FFFFFF"
        self._build_ui()
        self._generate_preview()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_generate_tab(), "Gerador de QR Code")
        self.tabs.addTab(self._build_read_tab(), "Leitor / Decodificador de QR Code")
        root_layout.addWidget(self.tabs)

    # -------------------------------------------------------------------------
    # Aba 1: Gerador
    # -------------------------------------------------------------------------
    def _build_generate_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(14)

        # Coluna da Esquerda: Configurações
        col_left = QVBoxLayout()
        col_left.setSpacing(10)

        col_left.addWidget(QLabel("Conteúdo / Texto ou URL:"))
        self.txt_content = QTextEdit()
        self.txt_content.setPlaceholderText("Cole aqui a URL, texto, número de telefone ou chave PIX...")
        self.txt_content.setText("https://github.com")
        self.txt_content.textChanged.connect(self._generate_preview)
        col_left.addWidget(self.txt_content)

        grp_cfg = QGroupBox("Estilo e Cores")
        cfg_layout = QVBoxLayout(grp_cfg)
        cfg_layout.setSpacing(8)

        row_colors = QHBoxLayout()
        row_colors.addWidget(QLabel("Cor do Código:"))
        self.btn_fill = QPushButton("#000000")
        self.btn_fill.setStyleSheet("background-color: #000000; color: #FFFFFF;")
        self.btn_fill.clicked.connect(self._pick_fill_color)
        row_colors.addWidget(self.btn_fill)

        row_colors.addSpacing(10)
        row_colors.addWidget(QLabel("Cor de Fundo:"))
        self.btn_back = QPushButton("#FFFFFF")
        self.btn_back.setStyleSheet("background-color: #FFFFFF; color: #000000;")
        self.btn_back.clicked.connect(self._pick_back_color)
        row_colors.addWidget(self.btn_back)
        cfg_layout.addLayout(row_colors)

        row_sizes = QHBoxLayout()
        row_sizes.addWidget(QLabel("Tamanho do Módulo:"))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(4, 30)
        self.spin_size.setValue(10)
        self.spin_size.valueChanged.connect(self._generate_preview)
        row_sizes.addWidget(self.spin_size)

        row_sizes.addSpacing(10)
        row_sizes.addWidget(QLabel("Margem:"))
        self.spin_border = QSpinBox()
        self.spin_border.setRange(0, 10)
        self.spin_border.setValue(4)
        self.spin_border.valueChanged.connect(self._generate_preview)
        row_sizes.addWidget(self.spin_border)
        cfg_layout.addLayout(row_sizes)

        col_left.addWidget(grp_cfg)

        btn_bar = QHBoxLayout()
        self.btn_copy = QPushButton("Copiar Imagem")
        self.btn_copy.clicked.connect(self._copy_image)
        btn_bar.addWidget(self.btn_copy)

        self.btn_save = QPushButton("Salvar Imagem (PNG)...")
        self.btn_save.setProperty("class", "primary")
        self.btn_save.clicked.connect(self._save_image)
        btn_bar.addWidget(self.btn_save)
        col_left.addLayout(btn_bar)

        layout.addLayout(col_left, 1)

        # Coluna da Direita: Preview
        col_right = QVBoxLayout()
        grp_prev = QGroupBox("Pré-Visualização em Tempo Real")
        prev_layout = QVBoxLayout(grp_prev)
        prev_layout.setAlignment(Qt.AlignCenter)

        self.lbl_preview = QLabel()
        self.lbl_preview.setFixedSize(260, 260)
        self.lbl_preview.setStyleSheet("border: 1px solid #444; background-color: #222;")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        prev_layout.addWidget(self.lbl_preview)

        col_right.addWidget(grp_prev)
        layout.addLayout(col_right)

        return tab

    # -------------------------------------------------------------------------
    # Aba 2: Leitor
    # -------------------------------------------------------------------------
    def _build_read_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        grp_src = QGroupBox("Carregar Imagem de QR Code")
        src_layout = QHBoxLayout(grp_src)

        self.txt_read_path = QLineEdit()
        self.txt_read_path.setPlaceholderText("Selecione um arquivo de imagem contendo o QR Code...")
        src_layout.addWidget(self.txt_read_path, 1)

        btn_browse_img = QPushButton("Procurar Imagem...")
        btn_browse_img.clicked.connect(self._on_browse_read_img)
        src_layout.addWidget(btn_browse_img)

        btn_paste_img = QPushButton("Colar da Área de Transferência")
        btn_paste_img.clicked.connect(self._on_paste_clipboard_img)
        src_layout.addWidget(btn_paste_img)

        layout.addWidget(grp_src)

        grp_res = QGroupBox("Conteúdo Decodificado do QR Code")
        res_layout = QVBoxLayout(grp_res)

        self.txt_decoded = QTextEdit()
        self.txt_decoded.setReadOnly(True)
        self.txt_decoded.setPlaceholderText("O texto ou link decodificado aparecerá aqui...")
        res_layout.addWidget(self.txt_decoded)

        row_act = QHBoxLayout()
        btn_copy_text = QPushButton("Copiar Texto Decodificado")
        btn_copy_text.clicked.connect(lambda: QApplication.clipboard().setText(self.txt_decoded.toPlainText()))
        row_act.addWidget(btn_copy_text)
        row_act.addStretch()
        res_layout.addLayout(row_act)

        layout.addWidget(grp_res)
        return tab

    def _generate_preview(self):
        text = self.txt_content.toPlainText().strip()
        if not text:
            self.lbl_preview.clear()
            self._current_qr_img = None
            return

        try:
            img = generate_qrcode(
                content=text,
                box_size=self.spin_size.value(),
                border=self.spin_border.value(),
                fill_color=self._fill_color,
                back_color=self._back_color
            )
            self._current_qr_img = img

            # Converte PIL Image para QPixmap
            bio = BytesIO()
            img.save(bio, format="PNG")
            qimg = QImage.fromData(bio.getvalue(), "PNG")
            pix = QPixmap.fromImage(qimg)
            self.lbl_preview.setPixmap(pix.scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            pass

    def _pick_fill_color(self):
        c = QColorDialog.getColor(QColor(self._fill_color), self, "Cor do QR Code")
        if c.isValid():
            self._fill_color = c.name()
            txt_c = "#FFFFFF" if (c.red()*0.299 + c.green()*0.587 + c.blue()*0.114) < 128 else "#000000"
            self.btn_fill.setText(self._fill_color)
            self.btn_fill.setStyleSheet(f"background-color: {self._fill_color}; color: {txt_c};")
            self._generate_preview()

    def _pick_back_color(self):
        c = QColorDialog.getColor(QColor(self._back_color), self, "Cor de Fundo")
        if c.isValid():
            self._back_color = c.name()
            txt_c = "#FFFFFF" if (c.red()*0.299 + c.green()*0.587 + c.blue()*0.114) < 128 else "#000000"
            self.btn_back.setText(self._back_color)
            self.btn_back.setStyleSheet(f"background-color: {self._back_color}; color: {txt_c};")
            self._generate_preview()

    def _copy_image(self):
        if self._current_qr_img:
            bio = BytesIO()
            self._current_qr_img.save(bio, format="PNG")
            qimg = QImage.fromData(bio.getvalue(), "PNG")
            QApplication.clipboard().setImage(qimg)
            QMessageBox.information(self, "Copiado", "Imagem do QR Code copiada para a área de transferência!")

    def _save_image(self):
        if not self._current_qr_img:
            QMessageBox.warning(self, "Aviso", "Gere um QR Code antes de salvar.")
            return

        f, _ = QFileDialog.getSaveFileName(self, "Salvar QR Code", "qrcode.png", "Imagem PNG (*.png)")
        if f:
            self._current_qr_img.save(f)
            QMessageBox.information(self, "Sucesso", f"QR Code salvo com sucesso em:\n{f}")

    def _on_browse_read_img(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Imagem do QR Code", "", "Imagens (*.png *.jpg *.jpeg *.webp *.bmp);;Todos os Arquivos (*.*)"
        )
        if f:
            self.txt_read_path.setText(f)
            self._process_read(Path(f))

    def _on_paste_clipboard_img(self):
        clip = QApplication.clipboard()
        img = clip.image()
        if img.isNull():
            QMessageBox.warning(self, "Aviso", "Nenhuma imagem encontrada na área de transferência.")
            return

        temp_p = Path.home() / "AppData" / "Local" / "Temp" / "wtbx_qr_paste.png"
        img.save(str(temp_p), "PNG")
        self.txt_read_path.setText(str(temp_p))
        self._process_read(temp_p)

    def _process_read(self, img_path: Path):
        self.txt_decoded.setText("Tentando decodificar código...")
        val = decode_qrcode_from_image(img_path)
        if val:
            self.txt_decoded.setText(val)
        else:
            self.txt_decoded.setText(
                "Não foi possível decodificar automaticamente o QR Code desta imagem.\n"
                "(Para habilitar leitura universal avançada, instale a biblioteca pyzbar ou opencv-python)."
            )
