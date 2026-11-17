"""
Ferramenta: Gerador e Leitor de QR Code e Códigos de Barras.
Permite criar, visualizar e exportar QR Codes e Códigos de Barras lineares (1D)
em PNG e SVG, além de decodificar códigos a partir de fotos ou área de transferência.
"""
from io import BytesIO
from pathlib import Path
from typing import Optional
from PIL import Image

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSlider, QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.images.barcode.logic import (
    SUPPORTED_BARCODE_FORMATS,
    generate_barcode_image,
    generate_barcode_svg,
    save_barcode_file,
    validate_barcode_input,
)
from wintoolbox.tools.images.qrcode.logic import (
    decode_qrcode_from_image, generate_qrcode
)
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("images.qrcode.ui")


@register
class QrCodeTool(Tool):
    id = "images.qrcode"
    name = "QR Code e Códigos de Barras"
    category = "Imagens"
    description = "Geração de QR Codes personalizados, códigos de barras 1D (EAN, Code128) e leitura de códigos a partir de imagens"
    keywords = [
        "qrcode", "qr", "código", "barras", "barcode", "code128", "ean13",
        "ean8", "etiqueta", "link", "wifi", "gerador", "leitor", "escanear"
    ]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return QrCodeView(self, parent)


class QrCodeView(QWidget):
    def __init__(self, tool: QrCodeTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool

        # Estado QR Code
        self._current_qr_img: Optional[Image.Image] = None
        self._fill_color = "#000000"
        self._back_color = "#FFFFFF"

        # Estado Código de Barras 1D
        self._current_barcode_img: Optional[Image.Image] = None
        self._barcode_timer = QTimer(self)
        self._barcode_timer.setSingleShot(True)
        self._barcode_timer.setInterval(200)
        self._barcode_timer.timeout.connect(self._render_barcode_preview)

        self._build_ui()
        self._generate_qr_preview()
        self._render_barcode_preview()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)

        root_layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
        ))

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_qr_generator_tab(), "Gerador de QR Code")
        self.tabs.addTab(self._build_barcode_generator_tab(), "Código de Barras 1D")
        self.tabs.addTab(self._build_reader_tab(), "Leitor / Decodificador")
        root_layout.addWidget(self.tabs, stretch=1)

    # -------------------------------------------------------------------------
    # Aba 1: Gerador de QR Code
    # -------------------------------------------------------------------------
    def _build_qr_generator_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(16)

        col_left = QVBoxLayout()
        col_left.setSpacing(10)

        col_left.addWidget(QLabel("Conteúdo / Texto ou URL:"))
        self.txt_qr_content = QTextEdit()
        self.txt_qr_content.setPlaceholderText("Cole aqui a URL, texto, número de telefone ou chave PIX...")
        self.txt_qr_content.setText("https://github.com")
        self.txt_qr_content.textChanged.connect(self._generate_qr_preview)
        col_left.addWidget(self.txt_qr_content)

        grp_cfg = QGroupBox("Estilo e Parâmetros")
        cfg_layout = QVBoxLayout(grp_cfg)
        cfg_layout.setSpacing(10)

        row_colors = QHBoxLayout()
        row_colors.addWidget(QLabel("Cor do Código:"))
        self.btn_qr_fill = QPushButton("#000000")
        self.btn_qr_fill.setStyleSheet("background-color: #000000; color: #FFFFFF; font-weight: bold;")
        self.btn_qr_fill.clicked.connect(self._pick_qr_fill_color)
        row_colors.addWidget(self.btn_qr_fill)

        row_colors.addSpacing(14)
        row_colors.addWidget(QLabel("Cor de Fundo:"))
        self.btn_qr_back = QPushButton("#FFFFFF")
        self.btn_qr_back.setStyleSheet("background-color: #FFFFFF; color: #000000; font-weight: bold;")
        self.btn_qr_back.clicked.connect(self._pick_qr_back_color)
        row_colors.addWidget(self.btn_qr_back)
        cfg_layout.addLayout(row_colors)

        row_sizes = QHBoxLayout()
        row_sizes.addWidget(QLabel("Módulo (Tamanho):"))
        self.spin_qr_size = QSpinBox()
        self.spin_qr_size.setRange(4, 40)
        self.spin_qr_size.setValue(10)
        self.spin_qr_size.valueChanged.connect(self._generate_qr_preview)
        row_sizes.addWidget(self.spin_qr_size)

        row_sizes.addSpacing(14)
        row_sizes.addWidget(QLabel("Margem:"))
        self.spin_qr_border = QSpinBox()
        self.spin_qr_border.setRange(0, 10)
        self.spin_qr_border.setValue(4)
        self.spin_qr_border.valueChanged.connect(self._generate_qr_preview)
        row_sizes.addWidget(self.spin_qr_border)
        cfg_layout.addLayout(row_sizes)

        col_left.addWidget(grp_cfg)

        btn_bar = QHBoxLayout()
        self.btn_copy_qr = QPushButton("Copiar Imagem")
        self.btn_copy_qr.clicked.connect(self._copy_qr_image)
        btn_bar.addWidget(self.btn_copy_qr)

        self.btn_save_qr = QPushButton("Salvar Imagem (PNG)...")
        self.btn_save_qr.setProperty("accent", True)
        self.btn_save_qr.clicked.connect(self._save_qr_image)
        btn_bar.addWidget(self.btn_save_qr)
        col_left.addLayout(btn_bar)

        layout.addLayout(col_left, stretch=1)

        # Coluna da Direita: Preview
        col_right = QVBoxLayout()
        grp_prev = QGroupBox("Pré-Visualização em Tempo Real")
        prev_layout = QVBoxLayout(grp_prev)
        prev_layout.setAlignment(Qt.AlignCenter)

        self.lbl_qr_preview = QLabel()
        self.lbl_qr_preview.setFixedSize(280, 280)
        self.lbl_qr_preview.setStyleSheet("border: 1px solid rgba(255, 255, 255, 0.1); background-color: #1a1a1a; border-radius: 8px;")
        self.lbl_qr_preview.setAlignment(Qt.AlignCenter)
        prev_layout.addWidget(self.lbl_qr_preview)

        col_right.addWidget(grp_prev)
        layout.addLayout(col_right)

        return tab

    # -------------------------------------------------------------------------
    # Aba 2: Gerador de Códigos de Barras 1D
    # -------------------------------------------------------------------------
    def _build_barcode_generator_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(16)

        col_left = QVBoxLayout()
        col_left.setSpacing(10)

        grp_cfg = QGroupBox("Configurações do Código de Barras")
        cfg_layout = QVBoxLayout(grp_cfg)
        cfg_layout.setSpacing(10)

        cfg_layout.addWidget(QLabel("Padrão do Código:"))
        self.cmb_bc_format = QComboBox()
        self.cmb_bc_format.addItems(SUPPORTED_BARCODE_FORMATS)
        self.cmb_bc_format.currentTextChanged.connect(self._on_bc_format_changed)
        cfg_layout.addWidget(self.cmb_bc_format)

        cfg_layout.addWidget(QLabel("Conteúdo / Código numérico ou alfanumérico:"))
        self.txt_bc_value = QLineEdit()
        self.txt_bc_value.setPlaceholderText("Ex: WIN-TOOLBOX-2026")
        self.txt_bc_value.setText("WIN-TOOLBOX-2026")
        self.txt_bc_value.textChanged.connect(self._schedule_barcode_render)
        cfg_layout.addWidget(self.txt_bc_value)

        row_dim = QHBoxLayout()
        row_dim.addWidget(QLabel("Altura (px):"))
        self.spin_bc_height = QSpinBox()
        self.spin_bc_height.setRange(40, 300)
        self.spin_bc_height.setValue(120)
        self.spin_bc_height.valueChanged.connect(self._schedule_barcode_render)
        row_dim.addWidget(self.spin_bc_height)

        row_dim.addSpacing(14)
        row_dim.addWidget(QLabel("Espessura:"))
        self.spin_bc_scale = QSpinBox()
        self.spin_bc_scale.setRange(1, 6)
        self.spin_bc_scale.setValue(3)
        self.spin_bc_scale.valueChanged.connect(self._schedule_barcode_render)
        row_dim.addWidget(self.spin_bc_scale)
        cfg_layout.addLayout(row_dim)

        self.chk_bc_text = QCheckBox("Exibir texto legível abaixo das barras")
        self.chk_bc_text.setChecked(True)
        self.chk_bc_text.toggled.connect(self._schedule_barcode_render)
        cfg_layout.addWidget(self.chk_bc_text)

        self.lbl_bc_status = QLabel("")
        self.lbl_bc_status.setStyleSheet("color: #EF4444; font-size: 11px;")
        cfg_layout.addWidget(self.lbl_bc_status)

        col_left.addWidget(grp_cfg)

        btn_bar = QHBoxLayout()
        self.btn_copy_bc = QPushButton("Copiar Imagem")
        self.btn_copy_bc.clicked.connect(self._copy_barcode_image)
        btn_bar.addWidget(self.btn_copy_bc)

        self.btn_save_bc_png = QPushButton("Salvar PNG...")
        self.btn_save_bc_png.setProperty("accent", True)
        self.btn_save_bc_png.clicked.connect(lambda: self._save_barcode_file("png"))
        btn_bar.addWidget(self.btn_save_bc_png)

        self.btn_save_bc_svg = QPushButton("Salvar Vetor (SVG)...")
        self.btn_save_bc_svg.clicked.connect(lambda: self._save_barcode_file("svg"))
        btn_bar.addWidget(self.btn_save_bc_svg)

        col_left.addLayout(btn_bar)
        col_left.addStretch(1)

        layout.addLayout(col_left, stretch=1)

        # Coluna da Direita: Preview
        col_right = QVBoxLayout()
        grp_prev = QGroupBox("Pré-Visualização do Código 1D")
        prev_layout = QVBoxLayout(grp_prev)
        prev_layout.setAlignment(Qt.AlignCenter)

        self.lbl_bc_preview = QLabel()
        self.lbl_bc_preview.setMinimumSize(320, 200)
        self.lbl_bc_preview.setStyleSheet("border: 1px solid rgba(255, 255, 255, 0.1); background-color: #1a1a1a; border-radius: 8px;")
        self.lbl_bc_preview.setAlignment(Qt.AlignCenter)
        prev_layout.addWidget(self.lbl_bc_preview)

        col_right.addWidget(grp_prev)
        layout.addLayout(col_right, stretch=1)

        return tab

    # -------------------------------------------------------------------------
    # Aba 3: Leitor / Decodificador Universal
    # -------------------------------------------------------------------------
    def _build_reader_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(12)

        grp_src = QGroupBox("Carregar Imagem de Código")
        src_layout = QHBoxLayout(grp_src)
        src_layout.setSpacing(10)

        self.txt_read_path = QLineEdit()
        self.txt_read_path.setPlaceholderText("Selecione um arquivo de imagem com QR Code ou Código de Barras...")
        src_layout.addWidget(self.txt_read_path, 1)

        btn_browse_img = QPushButton("Procurar Imagem...")
        btn_browse_img.clicked.connect(self._on_browse_read_img)
        src_layout.addWidget(btn_browse_img)

        btn_paste_img = QPushButton("Colar da Área de Transferência")
        btn_paste_img.clicked.connect(self._on_paste_clipboard_img)
        src_layout.addWidget(btn_paste_img)

        layout.addWidget(grp_src)

        grp_res = QGroupBox("Conteúdo Decodificado")
        res_layout = QVBoxLayout(grp_res)
        res_layout.setSpacing(10)

        self.txt_decoded = QTextEdit()
        self.txt_decoded.setReadOnly(True)
        self.txt_decoded.setPlaceholderText("O texto, link ou número decodificado aparecerá aqui...")
        res_layout.addWidget(self.txt_decoded)

        row_act = QHBoxLayout()
        btn_copy_text = QPushButton("Copiar Texto Decodificado")
        btn_copy_text.clicked.connect(self._copy_decoded_text)
        row_act.addWidget(btn_copy_text)
        row_act.addStretch()
        res_layout.addLayout(row_act)

        layout.addWidget(grp_res)
        return tab

    # -------------------------------------------------------------------------
    # Métodos do QR Code
    # -------------------------------------------------------------------------
    def _generate_qr_preview(self) -> None:
        text = self.txt_qr_content.toPlainText().strip()
        if not text:
            self.lbl_qr_preview.clear()
            self._current_qr_img = None
            return

        try:
            img = generate_qrcode(
                content=text,
                box_size=self.spin_qr_size.value(),
                border=self.spin_qr_border.value(),
                fill_color=self._fill_color,
                back_color=self._back_color
            )
            self._current_qr_img = img

            bio = BytesIO()
            img.save(bio, format="PNG")
            qimg = QImage.fromData(bio.getvalue(), "PNG")
            pix = QPixmap.fromImage(qimg)
            self.lbl_qr_preview.setPixmap(pix.scaled(260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as e:
            _log.warning(f"Erro ao gerar QR preview: {e}")

    def _pick_qr_fill_color(self) -> None:
        c = QColorDialog.getColor(QColor(self._fill_color), self, "Cor do QR Code")
        if c.isValid():
            self._fill_color = c.name()
            txt_c = "#FFFFFF" if (c.red()*0.299 + c.green()*0.587 + c.blue()*0.114) < 128 else "#000000"
            self.btn_qr_fill.setText(self._fill_color)
            self.btn_qr_fill.setStyleSheet(f"background-color: {self._fill_color}; color: {txt_c}; font-weight: bold;")
            self._generate_qr_preview()

    def _pick_qr_back_color(self) -> None:
        c = QColorDialog.getColor(QColor(self._back_color), self, "Cor de Fundo")
        if c.isValid():
            self._back_color = c.name()
            txt_c = "#FFFFFF" if (c.red()*0.299 + c.green()*0.587 + c.blue()*0.114) < 128 else "#000000"
            self.btn_qr_back.setText(self._back_color)
            self.btn_qr_back.setStyleSheet(f"background-color: {self._back_color}; color: {txt_c}; font-weight: bold;")
            self._generate_qr_preview()

    def _copy_qr_image(self) -> None:
        if self._current_qr_img:
            bio = BytesIO()
            self._current_qr_img.save(bio, format="PNG")
            qimg = QImage.fromData(bio.getvalue(), "PNG")
            QApplication.clipboard().setImage(qimg)
            show_toast(self, "QR Code copiado para a área de transferência!", duration_ms=2500)

    def _save_qr_image(self) -> None:
        if not self._current_qr_img:
            QMessageBox.warning(self, "Aviso", "Gere um QR Code antes de salvar.")
            return

        f, _ = QFileDialog.getSaveFileName(self, "Salvar QR Code", "qrcode.png", "Imagem PNG (*.png)")
        if f:
            self._current_qr_img.save(f)
            show_toast(self, "QR Code salvo com sucesso!", duration_ms=3000)

    # -------------------------------------------------------------------------
    # Métodos de Código de Barras 1D
    # -------------------------------------------------------------------------
    def _on_bc_format_changed(self, fmt: str) -> None:
        if fmt == "EAN13":
            self.txt_bc_value.setText("789123456789")
        elif fmt == "EAN8":
            self.txt_bc_value.setText("7891234")
        elif fmt == "UPCA":
            self.txt_bc_value.setText("01234567890")
        elif fmt == "I2of5":
            self.txt_bc_value.setText("12345678")
        elif fmt == "Standard39":
            self.txt_bc_value.setText("CODE39-TEST")
        else:
            self.txt_bc_value.setText("WIN-TOOLBOX-2026")
        self._render_barcode_preview()

    def _schedule_barcode_render(self) -> None:
        self._barcode_timer.start()

    def _render_barcode_preview(self) -> None:
        val = self.txt_bc_value.text().strip()
        fmt = self.cmb_bc_format.currentText()
        if not val:
            self.lbl_bc_preview.clear()
            self.lbl_bc_status.setText("Digite um valor para o código de barras.")
            self._current_barcode_img = None
            return

        try:
            norm_val = validate_barcode_input(fmt, val)
            self.lbl_bc_status.setText("")
        except ValueError as err:
            self.lbl_bc_status.setText(str(err))
            self.lbl_bc_preview.clear()
            self._current_barcode_img = None
            return

        try:
            img = generate_barcode_image(
                format_name=fmt,
                value=norm_val,
                bar_width=self.spin_bc_scale.value(),
                bar_height=self.spin_bc_height.value(),
                show_text=self.chk_bc_text.isChecked()
            )
            self._current_barcode_img = img

            bio = BytesIO()
            img.save(bio, format="PNG")
            qimg = QImage.fromData(bio.getvalue(), "PNG")
            pix = QPixmap.fromImage(qimg)
            self.lbl_bc_preview.setPixmap(pix.scaled(
                self.lbl_bc_preview.width() - 10,
                self.lbl_bc_preview.height() - 10,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
        except Exception as e:
            self.lbl_bc_status.setText(f"Erro na renderização: {e}")
            _log.warning(f"Erro ao renderizar código de barras: {e}")

    def _copy_barcode_image(self) -> None:
        if self._current_barcode_img:
            bio = BytesIO()
            self._current_barcode_img.save(bio, format="PNG")
            qimg = QImage.fromData(bio.getvalue(), "PNG")
            QApplication.clipboard().setImage(qimg)
            show_toast(self, "Código de barras copiado para a área de transferência!", duration_ms=2500)

    def _save_barcode_file(self, ext: str) -> None:
        fmt = self.cmb_bc_format.currentText()
        val = self.txt_bc_value.text().strip()
        try:
            norm_val = validate_barcode_input(fmt, val)
        except ValueError as err:
            QMessageBox.warning(self, "Erro de Validação", str(err))
            return

        filter_str = "Imagem PNG (*.png)" if ext == "png" else "Gráfico Vetorial SVG (*.svg)"
        default_name = f"barcode_{fmt.lower()}_{norm_val}.{ext}"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Salvar Código de Barras ({ext.upper()})",
            default_name,
            filter_str
        )
        if not save_path:
            return

        target = Path(save_path)
        try:
            save_barcode_file(
                target,
                format_name=fmt,
                value=norm_val,
                bar_height=self.spin_bc_height.value(),
                bar_width_scale=self.spin_bc_scale.value(),
                show_text=self.chk_bc_text.isChecked()
            )
            show_toast(self, f"Código de barras salvo com sucesso em {target.name}!", duration_ms=3000)
        except Exception as e:
            _log.error(f"Erro ao salvar arquivo de código de barras: {e}")
            QMessageBox.critical(self, "Erro", f"Falha ao salvar:\n{e}")

    # -------------------------------------------------------------------------
    # Métodos do Leitor
    # -------------------------------------------------------------------------
    def _on_browse_read_img(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Imagem do Código", "", "Imagens (*.png *.jpg *.jpeg *.webp *.bmp);;Todos os Arquivos (*.*)"
        )
        if f:
            self.txt_read_path.setText(f)
            self._process_read(Path(f))

    def _on_paste_clipboard_img(self) -> None:
        clip = QApplication.clipboard()
        img = clip.image()
        if img.isNull():
            QMessageBox.warning(self, "Aviso", "Nenhuma imagem encontrada na área de transferência.")
            return

        temp_p = Path.home() / "AppData" / "Local" / "Temp" / "wtbx_code_paste.png"
        img.save(str(temp_p), "PNG")
        self.txt_read_path.setText(str(temp_p))
        self._process_read(temp_p)

    def _process_read(self, img_path: Path) -> None:
        self.txt_decoded.setText("Tentando decodificar código...")
        val = decode_qrcode_from_image(img_path)
        if val:
            self.txt_decoded.setText(val)
            show_toast(self, "Código detectado e decodificado!", duration_ms=2500)
        else:
            self.txt_decoded.setText(
                "Não foi possível decodificar automaticamente o código desta imagem.\n"
                "Verifique se a imagem está nítida e se o código ocupa uma área legível da foto."
            )

    def _copy_decoded_text(self) -> None:
        txt = self.txt_decoded.toPlainText().strip()
        if txt:
            QApplication.clipboard().setText(txt)
            show_toast(self, "Texto copiado para a área de transferência!", duration_ms=2000)
