"""
Ferramenta: Gerador de Identificadores (UUID, ULID) e Senhas Seguras.
Permite gerar chaves aleatórias individuais ou em lote para desenvolvimento e segurança.
"""
import secrets
import string
import time
import uuid
from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register

CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

def generate_ulid() -> str:
    """Gera um ULID compatível de 26 caracteres (timestamp 48-bit + 80-bit aleatório)."""
    ms = int(time.time() * 1000)
    # 10 caracteres de tempo
    t_chars = []
    for _ in range(10):
        t_chars.append(CROCKFORD_BASE32[ms % 32])
        ms //= 32
    time_part = "".join(reversed(t_chars))

    # 16 caracteres de entropia aleatória
    rand_part = "".join(secrets.choice(CROCKFORD_BASE32) for _ in range(16))
    return f"{time_part}{rand_part}"

def generate_secure_password(length: int = 16, use_upper: bool = True, use_lower: bool = True, use_digits: bool = True, use_special: bool = True) -> str:
    """Gera uma senha segura com entropia criptográfica."""
    chars = ""
    if use_upper:
        chars += string.ascii_uppercase
    if use_lower:
        chars += string.ascii_lowercase
    if use_digits:
        chars += string.digits
    if use_special:
        chars += "!@#$%&*-_=+?"

    if not chars:
        chars = string.ascii_letters + string.digits

    return "".join(secrets.choice(chars) for _ in range(length))

@register
class GeneratorsTool(Tool):
    id = "encode.generators"
    name = "Gerador de UUID, ULID e Senhas Seguras"
    category = "Codificação e Hash"
    description = "Gera identificadores únicos UUID v4/v1, ULID e senhas aleatórias seguras em lote"
    keywords = ["uuid", "ulid", "guid", "senha", "password", "seguranca", "gerador", "lote", "hash"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return GeneratorsView(self, parent)

class GeneratorsView(QWidget):
    def __init__(self, tool: GeneratorsTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setProperty("class", "title")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setProperty("class", "secondary")
        layout.addWidget(lbl_desc)

        # Configurações do Gerador
        card_cfg = QFrame()
        card_cfg.setProperty("class", "card")
        l_cfg = QVBoxLayout(card_cfg)
        l_cfg.setSpacing(10)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Tipo de Geração:"))
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["UUID v4 (Aleatório)", "UUID v1 (Baseado em Tempo)", "ULID (Ordenável)", "Senha Segura"])
        self.cmb_type.currentTextChanged.connect(self._on_type_change)
        row1.addWidget(self.cmb_type)

        row1.addWidget(QLabel("Quantidade:"))
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 500)
        self.spin_count.setValue(5)
        row1.addWidget(self.spin_count)

        self.btn_gen = QPushButton("Gerar Itens")
        self.btn_gen.setProperty("class", "primary")
        self.btn_gen.clicked.connect(self._generate)
        row1.addWidget(self.btn_gen)
        row1.addStretch()
        l_cfg.addLayout(row1)

        # Opções de UUID / ULID
        self.row_uuid_opts = QHBoxLayout()
        self.chk_upper = QCheckBox("Em maiúsculas")
        self.row_uuid_opts.addWidget(self.chk_upper)

        self.chk_hyphens = QCheckBox("Incluir hífens")
        self.chk_hyphens.setChecked(True)
        self.row_uuid_opts.addWidget(self.chk_hyphens)
        self.row_uuid_opts.addStretch()
        l_cfg.addLayout(self.row_uuid_opts)

        # Opções de Senha Segura
        self.row_pwd_opts = QHBoxLayout()
        self.row_pwd_opts.addWidget(QLabel("Tamanho:"))
        self.spin_pwd_len = QSpinBox()
        self.spin_pwd_len.setRange(6, 128)
        self.spin_pwd_len.setValue(16)
        self.row_pwd_opts.addWidget(self.spin_pwd_len)

        self.chk_pwd_upper = QCheckBox("A-Z")
        self.chk_pwd_upper.setChecked(True)
        self.row_pwd_opts.addWidget(self.chk_pwd_upper)

        self.chk_pwd_lower = QCheckBox("a-z")
        self.chk_pwd_lower.setChecked(True)
        self.row_pwd_opts.addWidget(self.chk_pwd_lower)

        self.chk_pwd_digits = QCheckBox("0-9")
        self.chk_pwd_digits.setChecked(True)
        self.row_pwd_opts.addWidget(self.chk_pwd_digits)

        self.chk_pwd_special = QCheckBox("Símbolos (!@#)")
        self.chk_pwd_special.setChecked(True)
        self.row_pwd_opts.addWidget(self.chk_pwd_special)
        self.row_pwd_opts.addStretch()
        l_cfg.addLayout(self.row_pwd_opts)

        layout.addWidget(card_cfg)

        # Resultado
        col_res = QVBoxLayout()
        row_res_bar = QHBoxLayout()
        row_res_bar.addWidget(QLabel("Resultado Gerado:"))
        row_res_bar.addStretch()

        btn_copy_all = QPushButton("Copiar Todos")
        btn_copy_all.clicked.connect(self._copy_all)
        row_res_bar.addWidget(btn_copy_all)

        btn_clear = QPushButton("Limpar")
        btn_clear.clicked.connect(self._clear)
        row_res_bar.addWidget(btn_clear)
        col_res.addLayout(row_res_bar)

        self.txt_output = QPlainTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setFixedHeight(220)
        col_res.addWidget(self.txt_output)

        layout.addLayout(col_res)
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        self._on_type_change(self.cmb_type.currentText())
        self._generate()

    def _on_type_change(self, mode: str):
        is_pwd = mode == "Senha Segura"
        # Mostra/oculta opções pertinentes
        for i in range(self.row_pwd_opts.count()):
            w = self.row_pwd_opts.itemAt(i).widget()
            if w:
                w.setVisible(is_pwd)

        for i in range(self.row_uuid_opts.count()):
            w = self.row_uuid_opts.itemAt(i).widget()
            if w:
                w.setVisible(not is_pwd)

    def _generate(self):
        mode = self.cmb_type.currentText()
        count = self.spin_count.value()
        items = []

        if mode == "UUID v4 (Aleatório)":
            for _ in range(count):
                u = uuid.uuid4()
                val = str(u) if self.chk_hyphens.isChecked() else u.hex
                if self.chk_upper.isChecked():
                    val = val.upper()
                items.append(val)
        elif mode == "UUID v1 (Baseado em Tempo)":
            for _ in range(count):
                u = uuid.uuid1()
                val = str(u) if self.chk_hyphens.isChecked() else u.hex
                if self.chk_upper.isChecked():
                    val = val.upper()
                items.append(val)
        elif mode == "ULID (Ordenável)":
            for _ in range(count):
                val = generate_ulid()
                if not self.chk_upper.isChecked():
                    val = val.lower()
                items.append(val)
        elif mode == "Senha Segura":
            length = self.spin_pwd_len.value()
            u = self.chk_pwd_upper.isChecked()
            l = self.chk_pwd_lower.isChecked()
            d = self.chk_pwd_digits.isChecked()
            s = self.chk_pwd_special.isChecked()
            for _ in range(count):
                items.append(generate_secure_password(length, u, l, d, s))

        self.txt_output.setPlainText("\n".join(items))

    def _copy_all(self):
        text = self.txt_output.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Copiado", "Lista copiada para a área de transferência!")

    def _clear(self):
        self.txt_output.clear()
