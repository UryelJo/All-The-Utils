"""
Interface gráfica do Gerador de Pix Copia e Cola e QR Code (BR Code / Banco Central).
"""
import io
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDoubleSpinBox, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QVBoxLayout, QWidget
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.text.pix_generator.logic import generate_pix_payload
from wintoolbox.ui.widgets.toast import show_toast
from wintoolbox.ui.widgets.tool_header import ToolHeader

_log = get_logger("text.pix_generator.ui")


@register
class PixGeneratorTool(Tool):
    id = "text.pix_generator"
    name = "Gerador de Pix (Copia e Cola e QR Code)"
    category = "Texto e Redação"
    description = "Geração de códigos Pix no padrão oficial BR Code (Banco Central / EMVCo) com valor opcional e QR Code"
    keywords = ["pix", "copia e cola", "qr code", "br code", "banco central", "emv", "pagamento", "chave pix"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return PixGeneratorView(self, parent)


class PixGeneratorView(QWidget):
    def __init__(self, tool: PixGeneratorTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._current_pix_string: str = ""
        self._current_qr_pixmap: Optional[QPixmap] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(ToolHeader(
            self.tool.name,
            self.tool.description,
            self.tool.category
        ))

        # Divisão em dois lados: formulário à esquerda e resultado/QR Code à direita
        main_content = QHBoxLayout()
        main_content.setSpacing(16)

        # Formulário
        form_box = QGroupBox("Dados do Recebedor")
        f_lay = QGridLayout(form_box)
        f_lay.setContentsMargins(14, 14, 14, 14)
        f_lay.setHorizontalSpacing(12)
        f_lay.setVerticalSpacing(8)

        f_lay.addWidget(QLabel("Chave Pix (Obrigatório):"), 0, 0)
        self.txt_key = QLineEdit()
        self.txt_key.setPlaceholderText("CPF, CNPJ, E-mail, Celular ou Chave EVP...")
        f_lay.addWidget(self.txt_key, 0, 1)

        f_lay.addWidget(QLabel("Nome do Beneficiário:"), 1, 0)
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Ex: Fulano de Tal")
        f_lay.addWidget(self.txt_name, 1, 1)

        f_lay.addWidget(QLabel("Cidade do Beneficiário:"), 2, 0)
        self.txt_city = QLineEdit()
        self.txt_city.setText("BRASILIA")
        f_lay.addWidget(self.txt_city, 2, 1)

        f_lay.addWidget(QLabel("Valor (R$) - Opcional:"), 3, 0)
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.0, 9999999.0)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setPrefix("R$ ")
        self.spin_amount.setValue(0.0)
        f_lay.addWidget(self.spin_amount, 3, 1)

        f_lay.addWidget(QLabel("Identificador (TXID):"), 4, 0)
        self.txt_txid = QLineEdit()
        self.txt_txid.setText("***")
        f_lay.addWidget(self.txt_txid, 4, 1)

        f_lay.addWidget(QLabel("Descrição Opcional:"), 5, 0)
        self.txt_desc = QLineEdit()
        self.txt_desc.setPlaceholderText("Ex: Pagamento serviço...")
        f_lay.addWidget(self.txt_desc, 5, 1)

        self.btn_generate = QPushButton("Gerar Pix Copia e Cola")
        self.btn_generate.setProperty("accent", True)
        self.btn_generate.clicked.connect(self._generate_pix)
        f_lay.addWidget(self.btn_generate, 6, 0, 1, 2)

        main_content.addWidget(form_box, stretch=3)

        # Painel de Saída (QR Code e Copia e Cola)
        out_box = QGroupBox("Código Pix e QR Code")
        out_lay = QVBoxLayout(out_box)
        out_lay.setContentsMargins(14, 14, 14, 14)
        out_lay.setSpacing(10)

        # Exibição do QR Code
        self.lbl_qrcode = QLabel("O QR Code gerado aparecerá aqui.")
        self.lbl_qrcode.setAlignment(Qt.AlignCenter)
        self.lbl_qrcode.setFixedSize(180, 180)
        self.lbl_qrcode.setStyleSheet("background-color: #2b2b2b; border: 1px solid #444; border-radius: 4px;")
        out_lay.addWidget(self.lbl_qrcode, alignment=Qt.AlignCenter)

        out_lay.addWidget(QLabel("Código Pix Copia e Cola:"))
        self.txt_pix_code = QTextEdit()
        self.txt_pix_code.setReadOnly(True)
        self.txt_pix_code.setMaximumHeight(80)
        self.txt_pix_code.setStyleSheet("font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 11px;")
        out_lay.addWidget(self.txt_pix_code)

        btn_row = QHBoxLayout()
        self.btn_copy = QPushButton("Copiar Código Pix")
        self.btn_copy.clicked.connect(self._copy_pix)
        btn_row.addWidget(self.btn_copy)

        self.btn_save_qr = QPushButton("Salvar Imagem QR Code...")
        self.btn_save_qr.clicked.connect(self._save_qrcode)
        btn_row.addWidget(self.btn_save_qr)

        out_lay.addLayout(btn_row)
        main_content.addWidget(out_box, stretch=2)

        layout.addLayout(main_content)
        layout.addStretch()

    def _generate_pix(self) -> None:
        key = self.txt_key.text().strip()
        if not key:
            show_toast(self, "Preencha a Chave Pix.", is_error=True)
            return

        name = self.txt_name.text().strip() or "Recebedor Pix"
        city = self.txt_city.text().strip() or "Brasilia"
        val = self.spin_amount.value()
        amt = val if val > 0 else None
        txid = self.txt_txid.text().strip() or "***"
        desc = self.txt_desc.text().strip()

        try:
            payload = generate_pix_payload(key, name, city, amount=amt, txid=txid, description=desc)
            self._current_pix_string = payload
            self.txt_pix_code.setText(payload)

            # Renderiza QR Code via biblioteca qrcode se disponível
            self._render_qrcode(payload)
            show_toast(self, "Código Pix gerado com sucesso!")
        except Exception as exc:
            show_toast(self, f"Erro ao gerar Pix: {exc}", is_error=True)

    def _render_qrcode(self, text: str) -> None:
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(text)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qimg = QImage.fromData(buf.getvalue())
            pixmap = QPixmap.fromImage(qimg)
            self._current_qr_pixmap = pixmap
            scaled = pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_qrcode.setPixmap(scaled)
        except Exception as exc:
            _log.warning("Falha ao desenhar QR Code com qrcode: %s", exc)
            self.lbl_qrcode.setText("QR Code não gerado (biblioteca qrcode ausente).")

    def _copy_pix(self) -> None:
        if self._current_pix_string:
            QApplication.clipboard().setText(self._current_pix_string)
            show_toast(self, "Código Pix Copia e Cola copiado!")
        else:
            show_toast(self, "Nenhum código Pix gerado ainda.", is_error=True)

    def _save_qrcode(self) -> None:
        if not self._current_qr_pixmap:
            show_toast(self, "Gere o código Pix primeiro.", is_error=True)
            return

        dest, _ = QFileDialog.getSaveFileName(self, "Salvar QR Code Pix", "pix_qrcode.png", "Imagens PNG (*.png)")
        if dest:
            self._current_qr_pixmap.save(dest, "PNG")
            show_toast(self, "Imagem do QR Code salva com sucesso!")
