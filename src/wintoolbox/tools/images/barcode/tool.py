"""
Ferramenta: Gerador de Códigos de Barras (1D).
Permite criar, visualizar e exportar códigos Code128, EAN-13, EAN-8, ITF e Code 39 em PNG e SVG.
"""
import io
from pathlib import Path
from typing import Optional
from PIL import Image

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QClipboard, QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider,
    QSpinBox, QVBoxLayout, QWidget, QMessageBox
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.images.barcode.logic import (
    SUPPORTED_BARCODE_FORMATS,
    generate_barcode_image,
    generate_barcode_svg,
    save_barcode_file,
)


@register
class BarcodeGeneratorTool(Tool):
    id = "images.barcode"
    name = "Gerador de Código de Barras"
    category = "Imagens"
    description = "Crie códigos de barras 1D (Code128, EAN-13, EAN-8, ITF, Code 39) com prévia e exportação PNG/SVG"
    keywords = ["barcode", "codigo de barras", "code128", "ean13", "ean8", "etiqueta", "leitor", "comercial", "svg"]

    def __init__(self) -> None:
        super().__init__()
        self._current_image: Optional[Image.Image] = None
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(250)
        self._update_timer.timeout.connect(self._render_preview)

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QHBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(20)

        # Painel Lateral de Controles
        ctrl_panel = QFrame()
        ctrl_panel.setFixedWidth(340)
        ctrl_layout = QVBoxLayout(ctrl_panel)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(12)

        lbl_title = QLabel("Configuração do Código")
        lbl_title.setStyleSheet("font-weight: 600; font-size: 14px;")
        ctrl_layout.addWidget(lbl_title)

        # Formato
        ctrl_layout.addWidget(QLabel("Padrão do código de barras:"))
        self.cmb_format = QComboBox()
        self.cmb_format.addItems(SUPPORTED_BARCODE_FORMATS)
        self.cmb_format.currentTextChanged.connect(self._on_format_changed)
        ctrl_layout.addWidget(self.cmb_format)

        # Valor / Conteúdo
        ctrl_layout.addWidget(QLabel("Conteúdo / Código:"))
        self.txt_value = QLineEdit()
        self.txt_value.setPlaceholderText("Ex: WIN-TOOLBOX-2026")
        self.txt_value.setText("WIN-TOOLBOX-2026")
        self.txt_value.textChanged.connect(self._schedule_render)
        ctrl_layout.addWidget(self.txt_value)

        # Altura da Barra
        self.lbl_height = QLabel("Altura da barra (120 px):")
        ctrl_layout.addWidget(self.lbl_height)
        self.slider_height = QSlider(Qt.Horizontal)
        self.slider_height.setRange(50, 250)
        self.slider_height.setValue(120)
        self.slider_height.valueChanged.connect(self._on_height_changed)
        ctrl_layout.addWidget(self.slider_height)

        # Espessura
        self.lbl_width = QLabel("Espessura das barras (3x):")
        ctrl_layout.addWidget(self.lbl_width)
        self.slider_width = QSlider(Qt.Horizontal)
        self.slider_width.setRange(1, 6)
        self.slider_width.setValue(3)
        self.slider_width.valueChanged.connect(self._on_width_changed)
        ctrl_layout.addWidget(self.slider_width)

        # Texto legível
        self.chk_text = QCheckBox("Exibir texto numérico/alfanumérico abaixo")
        self.chk_text.setChecked(True)
        self.chk_text.stateChanged.connect(self._schedule_render)
        ctrl_layout.addWidget(self.chk_text)

        # Status / Erro de Validação
        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #d32f2f; font-size: 11px;")
        ctrl_layout.addWidget(self.lbl_status)

        ctrl_layout.addStretch()

        # Ações
        self.btn_copy = QPushButton("Copiar Imagem")
        self.btn_copy.clicked.connect(self._copy_image)
        ctrl_layout.addWidget(self.btn_copy)

        self.btn_save_png = QPushButton("Salvar Imagem (PNG)...")
        self.btn_save_png.clicked.connect(self._save_png)
        ctrl_layout.addWidget(self.btn_save_png)

        self.btn_save_svg = QPushButton("Salvar Vetorial (SVG)...")
        self.btn_save_svg.clicked.connect(self._save_svg)
        ctrl_layout.addWidget(self.btn_save_svg)

        main_layout.addWidget(ctrl_panel)

        # Área de Visualização Central
        preview_frame = QFrame()
        preview_frame.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;"
        )
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(20, 20, 20, 20)

        self.lbl_preview = QLabel("Gerando código...")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.lbl_preview)

        main_layout.addWidget(preview_frame, stretch=1)

        self._render_preview()
        return container

    def _on_format_changed(self, fmt: str) -> None:
        if fmt == "EAN13" and not self.txt_value.text().isdigit():
            self.txt_value.setText("789123456789")
        elif fmt == "EAN8" and not self.txt_value.text().isdigit():
            self.txt_value.setText("1234567")
        elif fmt == "UPCA" and not self.txt_value.text().isdigit():
            self.txt_value.setText("01234567890")
        self._schedule_render()

    def _on_height_changed(self, val: int) -> None:
        self.lbl_height.setText(f"Altura da barra ({val} px):")
        self._schedule_render()

    def _on_width_changed(self, val: int) -> None:
        self.lbl_width.setText(f"Espessura das barras ({val}x):")
        self._schedule_render()

    def _schedule_render(self) -> None:
        self._update_timer.start()

    def _render_preview(self) -> None:
        val = self.txt_value.text().strip()
        fmt = self.cmb_format.currentText()
        if not val:
            self.lbl_preview.setText("Digite um valor para gerar o código de barras")
            self.lbl_status.setText("")
            self._current_image = None
            return

        try:
            img = generate_barcode_image(
                format_name=fmt,
                value=val,
                bar_width=self.slider_width.value(),
                bar_height=self.slider_height.value(),
                quiet_zone=24,
                show_text=self.chk_text.isChecked()
            )
            self._current_image = img
            self.lbl_status.setText("")

            # Converte PIL RGBA para QPixmap
            raw_data = img.tobytes("raw", "RGBA")
            qimg = QImage(raw_data, img.width, img.height, QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimg)

            # Reduz visualmente se ultrapassar a área de preview
            scaled_pixmap = pixmap.scaled(
                600, 360,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ) if (pixmap.width() > 600 or pixmap.height() > 360) else pixmap

            self.lbl_preview.setPixmap(scaled_pixmap)
        except Exception as e:
            self.lbl_status.setText(f"Erro: {e}")
            self.lbl_preview.setText("Não foi possível gerar a prévia com os parâmetros atuais")
            self._current_image = None

    def _copy_image(self) -> None:
        if self._current_image is None:
            return
        raw_data = self._current_image.tobytes("raw", "RGBA")
        qimg = QImage(raw_data, self._current_image.width, self._current_image.height, QImage.Format_RGBA8888)
        QGuiApplication.clipboard().setImage(qimg)
        self.lbl_status.setText("Imagem do código copiada para a área de transferência!")

    def _save_png(self) -> None:
        if self._current_image is None:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Código de Barras (PNG)",
            "codigo_de_barras.png",
            "Imagens PNG (*.png)"
        )
        if file_path:
            self._current_image.save(file_path, "PNG")
            self.lbl_status.setText(f"Arquivo salvo com sucesso: {Path(file_path).name}")

    def _save_svg(self) -> None:
        val = self.txt_value.text().strip()
        fmt = self.cmb_format.currentText()
        if not val:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Salvar Código de Barras (SVG)",
            "codigo_de_barras.svg",
            "Vetores SVG (*.svg)"
        )
        if file_path:
            try:
                svg_data = generate_barcode_svg(
                    format_name=fmt,
                    value=val,
                    bar_width=float(self.slider_width.value()),
                    bar_height=float(self.slider_height.value())
                )
                Path(file_path).write_text(svg_data, encoding="utf-8")
                self.lbl_status.setText(f"Vetor SVG salvo com sucesso: {Path(file_path).name}")
            except Exception as e:
                self.lbl_status.setText(f"Erro ao salvar SVG: {e}")
