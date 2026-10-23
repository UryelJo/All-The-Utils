"""
Ferramenta: Validador e Gerador de Documentos Brasileiros (CPF, CNPJ, PIS).
Implementação dos cálculos de dígito verificador padrão Receita Federal / Ministério da Economia.
"""
import random
import re
from typing import Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QTabWidget,
    QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register

def validate_cpf(cpf: str) -> Tuple[bool, str]:
    """Valida o número de CPF utilizando o cálculo oficial dos dois dígitos verificadores."""
    digits = [int(c) for c in cpf if c.isdigit()]
    if len(digits) != 11:
        return False, "O CPF deve conter exatamente 11 dígitos numéricos."
    if len(set(digits)) == 1:
        return False, "CPF com todos os dígitos repetidos é inválido."

    # Primeiro dígito
    s = sum(d * w for d, w in zip(digits[:9], range(10, 1, -1)))
    d1 = (s * 10) % 11
    if d1 == 10:
        d1 = 0
    if d1 != digits[9]:
        return False, "Primeiro dígito verificador incorreto."

    # Segundo dígito
    s = sum(d * w for d, w in zip(digits[:10], range(11, 1, -1)))
    d2 = (s * 10) % 11
    if d2 == 10:
        d2 = 0
    if d2 != digits[10]:
        return False, "Segundo dígito verificador incorreto."

    return True, "CPF válido e verificado com sucesso!"

def validate_cnpj(cnpj: str) -> Tuple[bool, str]:
    """Valida o número de CNPJ utilizando os cálculos de módulo 11."""
    digits = [int(c) for c in cnpj if c.isdigit()]
    if len(digits) != 14:
        return False, "O CNPJ deve conter exatamente 14 dígitos numéricos."
    if len(set(digits)) == 1:
        return False, "CNPJ com todos os dígitos repetidos é inválido."

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s1 = sum(d * w for d, w in zip(digits[:12], w1))
    rem1 = s1 % 11
    d1 = 0 if rem1 < 2 else 11 - rem1
    if d1 != digits[12]:
        return False, "Primeiro dígito verificador incorreto."

    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s2 = sum(d * w for d, w in zip(digits[:13], w2))
    rem2 = s2 % 11
    d2 = 0 if rem2 < 2 else 11 - rem2
    if d2 != digits[13]:
        return False, "Segundo dígito verificador incorreto."

    return True, "CNPJ válido e verificado com sucesso!"

def generate_valid_cpf(formatted: bool = True) -> str:
    """Gera um CPF válido aleatório para fins de teste."""
    digits = [random.randint(0, 9) for _ in range(9)]
    s = sum(d * w for d, w in zip(digits, range(10, 1, -1)))
    d1 = (s * 10) % 11
    d1 = 0 if d1 == 10 else d1
    digits.append(d1)

    s = sum(d * w for d, w in zip(digits, range(11, 1, -1)))
    d2 = (s * 10) % 11
    d2 = 0 if d2 == 10 else d2
    digits.append(d2)

    raw = "".join(str(d) for d in digits)
    if formatted:
        return f"{raw[:3]}.{raw[3:6]}.{raw[6:9]}-{raw[9:]}"
    return raw

def generate_valid_cnpj(formatted: bool = True) -> str:
    """Gera um CNPJ válido aleatório com sufixo matriz 0001."""
    digits = [random.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s1 = sum(d * w for d, w in zip(digits, w1))
    rem1 = s1 % 11
    d1 = 0 if rem1 < 2 else 11 - rem1
    digits.append(d1)

    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s2 = sum(d * w for d, w in zip(digits, w2))
    rem2 = s2 % 11
    d2 = 0 if rem2 < 2 else 11 - rem2
    digits.append(d2)

    raw = "".join(str(d) for d in digits)
    if formatted:
        return f"{raw[:2]}.{raw[2:5]}.{raw[5:8]}/{raw[8:12]}-{raw[12:]}"
    return raw

@register
class ValidatorsBrTool(Tool):
    id = "text.validators_br"
    name = "Validador e Gerador de Documentos BR"
    category = "Texto e Redação"
    description = "Validação oficial e geração de CPF, CNPJ e documentos brasileiros para testes"
    keywords = ["cpf", "cnpj", "validador", "gerador", "documentos", "receita", "federal", "brasil"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return ValidatorsBrView(self, parent)

class ValidatorsBrView(QWidget):
    def __init__(self, tool: ValidatorsBrTool, parent: Optional[QWidget] = None):
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

        tabs = QTabWidget()

        # ABA 1: Validador de Documentos
        tab_val = QWidget()
        l_val = QVBoxLayout(tab_val)
        l_val.setSpacing(12)

        card_v = QFrame()
        card_v.setProperty("class", "card")
        l_cv = QVBoxLayout(card_v)
        l_cv.setSpacing(10)

        row_v1 = QHBoxLayout()
        row_v1.addWidget(QLabel("Tipo de Documento:"))
        self.cmb_doc_type = QComboBox()
        self.cmb_doc_type.addItems(["CPF", "CNPJ"])
        self.cmb_doc_type.currentTextChanged.connect(self._validate_now)
        row_v1.addWidget(self.cmb_doc_type)

        row_v1.addWidget(QLabel("Número:"))
        self.txt_doc_input = QLineEdit()
        self.txt_doc_input.setPlaceholderText("Digite o número com ou sem pontuação...")
        self.txt_doc_input.textChanged.connect(self._validate_now)
        row_v1.addWidget(self.txt_doc_input, stretch=1)
        l_cv.addLayout(row_v1)

        self.lbl_val_result = QLabel("Aguardando digitação...")
        self.lbl_val_result.setStyleSheet("font-size: 14px; font-weight: 600;")
        l_cv.addWidget(self.lbl_val_result)

        row_v_actions = QHBoxLayout()
        btn_format = QPushButton("Aplicar Pontuação")
        btn_format.clicked.connect(self._format_doc)
        row_v_actions.addWidget(btn_format)

        btn_unformat = QPushButton("Remover Pontuação (Só Números)")
        btn_unformat.clicked.connect(self._unformat_doc)
        row_v_actions.addWidget(btn_unformat)
        row_v_actions.addStretch()
        l_cv.addLayout(row_v_actions)

        l_val.addWidget(card_v)
        l_val.addStretch()
        tabs.addTab(tab_val, "Validação de Documentos")

        # ABA 2: Gerador de Documentos para Testes
        tab_gen = QWidget()
        l_gen = QVBoxLayout(tab_gen)
        l_gen.setSpacing(12)

        card_g = QFrame()
        card_g.setProperty("class", "card")
        l_cg = QVBoxLayout(card_g)
        l_cg.setSpacing(10)

        row_g1 = QHBoxLayout()
        row_g1.addWidget(QLabel("Gerar Documento:"))
        self.cmb_gen_type = QComboBox()
        self.cmb_gen_type.addItems(["CPF", "CNPJ"])
        row_g1.addWidget(self.cmb_gen_type)

        self.chk_mask = QCheckBox("Com pontuação (máscara padrão)")
        self.chk_mask.setChecked(True)
        row_g1.addWidget(self.chk_mask)

        btn_gen = QPushButton("Gerar Número Válido")
        btn_gen.setProperty("class", "primary")
        btn_gen.clicked.connect(self._generate_doc)
        row_g1.addWidget(btn_gen)
        row_g1.addStretch()
        l_cg.addLayout(row_g1)

        row_g2 = QHBoxLayout()
        row_g2.addWidget(QLabel("Documento Gerado:"))
        self.txt_gen_output = QLineEdit()
        self.txt_gen_output.setReadOnly(True)
        self.txt_gen_output.setStyleSheet("font-size: 15px; font-weight: 600; color: #0078d4;")
        row_g2.addWidget(self.txt_gen_output, stretch=1)

        btn_copy_gen = QPushButton("Copiar")
        btn_copy_gen.clicked.connect(self._copy_gen)
        row_g2.addWidget(btn_copy_gen)
        l_cg.addLayout(row_g2)

        lbl_g_info = QLabel("Nota: Documentos gerados respeitam as regras matemáticas oficiais e devem ser usados apenas em ambientes de teste e desenvolvimento de software.")
        lbl_g_info.setProperty("class", "secondary")
        l_cg.addWidget(lbl_g_info)

        l_gen.addWidget(card_g)
        l_gen.addStretch()
        tabs.addTab(tab_gen, "Gerador para Homologação")

        layout.addWidget(tabs)
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _validate_now(self):
        text = self.txt_doc_input.text().strip()
        doc_type = self.cmb_doc_type.currentText()
        if not text:
            self.lbl_val_result.setText("Aguardando digitação...")
            self.lbl_val_result.setStyleSheet("font-size: 14px; font-weight: 600; color: #aaa;")
            return

        if doc_type == "CPF":
            valid, msg = validate_cpf(text)
        else:
            valid, msg = validate_cnpj(text)

        if valid:
            self.lbl_val_result.setText(f"[VÁLIDO] {msg}")
            self.lbl_val_result.setStyleSheet("font-size: 14px; font-weight: 600; color: #7ee787;")
        else:
            self.lbl_val_result.setText(f"[INVÁLIDO] {msg}")
            self.lbl_val_result.setStyleSheet("font-size: 14px; font-weight: 600; color: #ffa198;")

    def _format_doc(self):
        nums = "".join(filter(str.isdigit, self.txt_doc_input.text()))
        if self.cmb_doc_type.currentText() == "CPF" and len(nums) == 11:
            self.txt_doc_input.setText(f"{nums[:3]}.{nums[3:6]}.{nums[6:9]}-{nums[9:]}")
        elif self.cmb_doc_type.currentText() == "CNPJ" and len(nums) == 14:
            self.txt_doc_input.setText(f"{nums[:2]}.{nums[2:5]}.{nums[5:8]}/{nums[8:12]}-{nums[12:]}")

    def _unformat_doc(self):
        nums = "".join(filter(str.isdigit, self.txt_doc_input.text()))
        self.txt_doc_input.setText(nums)

    def _generate_doc(self):
        doc_type = self.cmb_gen_type.currentText()
        mask = self.chk_mask.isChecked()
        if doc_type == "CPF":
            res = generate_valid_cpf(mask)
        else:
            res = generate_valid_cnpj(mask)
        self.txt_gen_output.setText(res)

    def _copy_gen(self):
        text = self.txt_gen_output.text().strip()
        if text:
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Copiado", f"{text} copiado para a área de transferência!")
