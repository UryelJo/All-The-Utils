"""
Ferramenta: Transformações de Texto e Manipulação de Linhas.
Permite alterar caixa, remover acentos, converter em slugs, ordenar linhas, remover duplicadas e obter estatísticas.
"""
import re
import unicodedata
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register

def remove_accents(text: str) -> str:
    """Remove acentos e diacríticos mantendo letras base."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])

def to_camel_case(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    if not words:
        return ""
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])

def to_snake_case(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    return "_".join(w.lower() for w in words)

def to_kebab_case(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    return "-".join(w.lower() for w in words)

def to_slug(text: str) -> str:
    clean = remove_accents(text.lower())
    clean = re.sub(r"[^a-z0-9]+", "-", clean)
    return clean.strip("-")

@register
class TextTransformTool(Tool):
    id = "text.transform"
    name = "Transformações de Texto e Linhas"
    category = "Texto e Redação"
    description = "Altera caixa de texto, remove acentos, formata casos de código, ordena e limpa linhas"
    keywords = ["texto", "maiusculas", "minusculas", "camelcase", "snake_case", "slug", "acentos", "linhas", "duplicadas"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return TextTransformView(self, parent)

class TextTransformView(QWidget):
    def __init__(self, tool: TextTransformTool, parent: Optional[QWidget] = None):
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

        # Editor de Texto
        col_ed = QVBoxLayout()
        col_ed.addWidget(QLabel("Texto para Edição:"))
        self.txt_content = QPlainTextEdit()
        self.txt_content.setPlaceholderText("Cole ou digite o texto aqui para aplicar as transformações...")
        self.txt_content.setFixedHeight(180)
        self.txt_content.textChanged.connect(self._update_stats)
        col_ed.addWidget(self.txt_content)
        layout.addLayout(col_ed)

        # Barra de Estatísticas em Tempo Real
        self.lbl_stats = QLabel("0 caracteres | 0 palavras | 0 linhas | 0 bytes")
        self.lbl_stats.setProperty("class", "secondary")
        self.lbl_stats.setStyleSheet("font-weight: 500;")
        layout.addWidget(self.lbl_stats)

        # Painel de Botões de Ação de Caixa
        card_cases = QFrame()
        card_cases.setProperty("class", "card")
        l_cases = QVBoxLayout(card_cases)
        l_cases.setSpacing(8)

        lbl_c_title = QLabel("Transformações de Caixa e Notação")
        lbl_c_title.setStyleSheet("font-weight: 600;")
        l_cases.addWidget(lbl_c_title)

        grid_cases = QGridLayout()
        grid_cases.setSpacing(8)

        btn_upper = QPushButton("MAIÚSCULAS")
        btn_upper.clicked.connect(lambda: self._apply(lambda s: s.upper()))
        grid_cases.addWidget(btn_upper, 0, 0)

        btn_lower = QPushButton("minúsculas")
        btn_lower.clicked.connect(lambda: self._apply(lambda s: s.lower()))
        grid_cases.addWidget(btn_lower, 0, 1)

        btn_title = QPushButton("Primeira Letra Maiúscula")
        btn_title.clicked.connect(lambda: self._apply(lambda s: s.title()))
        grid_cases.addWidget(btn_title, 0, 2)

        btn_camel = QPushButton("camelCase")
        btn_camel.clicked.connect(lambda: self._apply(to_camel_case))
        grid_cases.addWidget(btn_camel, 0, 3)

        btn_snake = QPushButton("snake_case")
        btn_snake.clicked.connect(lambda: self._apply(to_snake_case))
        grid_cases.addWidget(btn_snake, 1, 0)

        btn_kebab = QPushButton("kebab-case")
        btn_kebab.clicked.connect(lambda: self._apply(to_kebab_case))
        grid_cases.addWidget(btn_kebab, 1, 1)

        btn_slug = QPushButton("Gerar Slug Web")
        btn_slug.clicked.connect(lambda: self._apply(to_slug))
        grid_cases.addWidget(btn_slug, 1, 2)

        btn_accents = QPushButton("Remover Acentos")
        btn_accents.clicked.connect(lambda: self._apply(remove_accents))
        grid_cases.addWidget(btn_accents, 1, 3)

        l_cases.addLayout(grid_cases)
        layout.addWidget(card_cases)

        # Painel de Operações em Linhas
        card_lines = QFrame()
        card_lines.setProperty("class", "card")
        l_lines = QVBoxLayout(card_lines)
        l_lines.setSpacing(8)

        lbl_l_title = QLabel("Manipulação de Linhas e Listas")
        lbl_l_title.setStyleSheet("font-weight: 600;")
        l_lines.addWidget(lbl_l_title)

        grid_lines = QGridLayout()
        grid_lines.setSpacing(8)

        btn_sort_az = QPushButton("Ordenar Linhas (A → Z)")
        btn_sort_az.clicked.connect(self._sort_lines_asc)
        grid_lines.addWidget(btn_sort_az, 0, 0)

        btn_sort_za = QPushButton("Ordenar Linhas (Z → A)")
        btn_sort_za.clicked.connect(self._sort_lines_desc)
        grid_lines.addWidget(btn_sort_za, 0, 1)

        btn_dedup = QPushButton("Remover Linhas Duplicadas")
        btn_dedup.clicked.connect(self._dedup_lines)
        grid_lines.addWidget(btn_dedup, 0, 2)

        btn_empty = QPushButton("Remover Linhas Vazias")
        btn_empty.clicked.connect(self._remove_empty_lines)
        grid_lines.addWidget(btn_empty, 0, 3)

        btn_reverse = QPushButton("Inverter Ordem das Linhas")
        btn_reverse.clicked.connect(self._reverse_lines)
        grid_lines.addWidget(btn_reverse, 1, 0)

        btn_number = QPushButton("Numerar Linhas (1, 2, 3...)")
        btn_number.clicked.connect(self._number_lines)
        grid_lines.addWidget(btn_number, 1, 1)

        btn_trim = QPushButton("Remover Espaços das Bordas")
        btn_trim.clicked.connect(self._trim_lines)
        grid_lines.addWidget(btn_trim, 1, 2)

        btn_copy = QPushButton("Copiar Texto Final")
        btn_copy.setProperty("class", "primary")
        btn_copy.clicked.connect(self._copy_text)
        grid_lines.addWidget(btn_copy, 1, 3)

        l_lines.addLayout(grid_lines)

        # Prefixo e Sufixo
        row_affix = QHBoxLayout()
        row_affix.addWidget(QLabel("Prefixo:"))
        self.txt_prefix = QLineEdit()
        self.txt_prefix.setPlaceholderText("ex: - ou [")
        row_affix.addWidget(self.txt_prefix)

        row_affix.addWidget(QLabel("Sufixo:"))
        self.txt_suffix = QLineEdit()
        self.txt_suffix.setPlaceholderText("ex: , ou ]")
        row_affix.addWidget(self.txt_suffix)

        btn_affix = QPushButton("Aplicar em Todas as Linhas")
        btn_affix.clicked.connect(self._apply_prefix_suffix)
        row_affix.addWidget(btn_affix)
        l_lines.addLayout(row_affix)

        layout.addWidget(card_lines)
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        self._update_stats()

    def _update_stats(self):
        text = self.txt_content.toPlainText()
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        lines = len(text.splitlines()) if text else 0
        b_size = len(text.encode("utf-8"))
        self.lbl_stats.setText(f"{chars:,} caracteres | {words:,} palavras | {lines:,} linhas | {b_size:,} bytes UTF-8")

    def _apply(self, func):
        text = self.txt_content.toPlainText()
        self.txt_content.setPlainText(func(text))

    def _sort_lines_asc(self):
        lines = self.txt_content.toPlainText().splitlines()
        self.txt_content.setPlainText("\n".join(sorted(lines)))

    def _sort_lines_desc(self):
        lines = self.txt_content.toPlainText().splitlines()
        self.txt_content.setPlainText("\n".join(sorted(lines, reverse=True)))

    def _dedup_lines(self):
        lines = self.txt_content.toPlainText().splitlines()
        seen = set()
        unique = []
        for l in lines:
            if l not in seen:
                seen.add(l)
                unique.append(l)
        self.txt_content.setPlainText("\n".join(unique))

    def _remove_empty_lines(self):
        lines = self.txt_content.toPlainText().splitlines()
        self.txt_content.setPlainText("\n".join([l for l in lines if l.strip()]))

    def _reverse_lines(self):
        lines = self.txt_content.toPlainText().splitlines()
        self.txt_content.setPlainText("\n".join(reversed(lines)))

    def _number_lines(self):
        lines = self.txt_content.toPlainText().splitlines()
        numbered = [f"{i+1}. {l}" for i, l in enumerate(lines)]
        self.txt_content.setPlainText("\n".join(numbered))

    def _trim_lines(self):
        lines = self.txt_content.toPlainText().splitlines()
        self.txt_content.setPlainText("\n".join([l.strip() for l in lines]))

    def _apply_prefix_suffix(self):
        prefix = self.txt_prefix.text()
        suffix = self.txt_suffix.text()
        lines = self.txt_content.toPlainText().splitlines()
        res = [f"{prefix}{l}{suffix}" for l in lines]
        self.txt_content.setPlainText("\n".join(res))

    def _copy_text(self):
        text = self.txt_content.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Copiado", "Texto copiado para a área de transferência!")
