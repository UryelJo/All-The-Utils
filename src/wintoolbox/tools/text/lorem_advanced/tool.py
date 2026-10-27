"""
Ferramenta: Gerador de Textos Fictícios Temáticos (Lorem Ipsum Avançado).
Gera textos para layouts, mockups e testes em diversos temas (Corporativo, Jurídico, Sci-Fi, Culinária, Latim).
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QSpinBox, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.text.lorem_advanced.logic import generate_lorem_text


@register
class LoremAdvancedTool(Tool):
    id = "text.lorem_advanced"
    name = "Gerador de Textos Fictícios (Lorem Temático)"
    category = "Texto e Redação"
    description = "Gere textos fictícios e mockups em diversos temas (Corporativo, Jurídico, Gastronomia, Sci-Fi e Latim)"
    keywords = ["lorem", "ipsum", "dummy text", "gerador", "lero lero", "juridico", "startup", "mockup", "layout"]

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Painel de Opções
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;")
        grid = QGridLayout(ctrl_frame)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # Tema
        grid.addWidget(QLabel("Tema do Vocabulário:"), 0, 0)
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems([
            "Corporativo / Startup",
            "Jurídico / Forense",
            "Gastronomia",
            "Ficção Científica (Sci-Fi)",
            "Clássico (Latim)",
        ])
        grid.addWidget(self.cmb_theme, 0, 1)

        # Unidade
        grid.addWidget(QLabel("Unidade de Contagem:"), 0, 2)
        self.cmb_unit = QComboBox()
        self.cmb_unit.addItems(["Parágrafos", "Frases", "Palavras"])
        self.cmb_unit.currentTextChanged.connect(self._on_unit_changed)
        grid.addWidget(self.cmb_unit, 0, 3)

        # Quantidade
        self.lbl_count = QLabel("Quantidade (3):")
        grid.addWidget(self.lbl_count, 1, 0)
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 100)
        self.spin_count.setValue(3)
        self.spin_count.valueChanged.connect(lambda v: self.lbl_count.setText(f"Quantidade ({v}):"))
        grid.addWidget(self.spin_count, 1, 1)

        # Formato de Saída
        grid.addWidget(QLabel("Formato de Saída:"), 1, 2)
        self.cmb_fmt = QComboBox()
        self.cmb_fmt.addItems(["Texto Puro", "HTML (<p>)", "Markdown"])
        grid.addWidget(self.cmb_fmt, 1, 3)

        # Checkbox Iniciar com lead
        self.chk_lead = QCheckBox("Iniciar sempre com frase clássica de abertura")
        self.chk_lead.setChecked(True)
        grid.addWidget(self.chk_lead, 2, 0, 1, 4)

        main_layout.addWidget(ctrl_frame)

        # Botões de Ação
        btn_bar = QHBoxLayout()
        self.btn_generate = QPushButton("Gerar Texto Fictício")
        self.btn_generate.setStyleSheet("font-weight: 600;")
        self.btn_generate.clicked.connect(self._generate)
        btn_bar.addWidget(self.btn_generate)

        self.btn_copy = QPushButton("Copiar Texto")
        self.btn_copy.clicked.connect(self._copy_text)
        btn_bar.addWidget(self.btn_copy)

        btn_bar.addStretch()
        main_layout.addLayout(btn_bar)

        # Editor de Saída
        self.txt_output = QPlainTextEdit()
        self.txt_output.setStyleSheet("font-size: 13px; line-height: 1.5;")
        self.txt_output.textChanged.connect(self._update_stats)
        main_layout.addWidget(self.txt_output)

        # Estatísticas no Rodapé
        self.lbl_stats = QLabel("0 palavras | 0 caracteres")
        self.lbl_stats.setStyleSheet("color: #64748b; font-size: 12px;")
        main_layout.addWidget(self.lbl_stats)

        self._generate()
        return container

    def _on_unit_changed(self, text: str) -> None:
        if text == "Palavras":
            self.spin_count.setRange(5, 500)
            self.spin_count.setValue(50)
        elif text == "Frases":
            self.spin_count.setRange(1, 50)
            self.spin_count.setValue(5)
        else:
            self.spin_count.setRange(1, 25)
            self.spin_count.setValue(3)

    def _generate(self) -> None:
        t_text = self.cmb_theme.currentText()
        if "Corporativo" in t_text:
            theme = "corporativo"
        elif "Jurídico" in t_text:
            theme = "juridico"
        elif "Gastronomia" in t_text:
            theme = "gastronomia"
        elif "Ficção" in t_text:
            theme = "sci_fi"
        else:
            theme = "classico"

        u_text = self.cmb_unit.currentText()
        unit = "words" if "Palavras" in u_text else ("sentences" if "Frases" in u_text else "paragraphs")

        f_text = self.cmb_fmt.currentText()
        fmt = "html" if "HTML" in f_text else ("markdown" if "Markdown" in f_text else "text")

        count = self.spin_count.value()
        lead = self.chk_lead.isChecked()

        generated = generate_lorem_text(
            theme=theme,
            unit=unit,
            count=count,
            output_format=fmt,
            start_with_lead=lead
        )
        self.txt_output.setPlainText(generated)

    def _update_stats(self) -> None:
        txt = self.txt_output.toPlainText().strip()
        if not txt:
            self.lbl_stats.setText("0 palavras | 0 caracteres")
            return
        words = len(txt.split())
        chars = len(txt)
        self.lbl_stats.setText(f"{words:,} palavras | {chars:,} caracteres".replace(",", "."))

    def _copy_text(self) -> None:
        txt = self.txt_output.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)
            self.lbl_stats.setText(f"Texto copiado para a área de transferência! ({len(txt)} caracteres)")
            self.lbl_stats.setStyleSheet("color: #16a34a; font-weight: 600; font-size: 12px;")
