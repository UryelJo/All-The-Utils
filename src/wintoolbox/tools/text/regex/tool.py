"""
Ferramenta: Testador e Depurador de Expressões Regulares (Regex).
Permite testar expressões regulares, visualizar correspondências, grupos de captura e realizar substituições.
"""
import re
from typing import Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from .logic import evaluate_regex
from wintoolbox.ui.widgets.sortable_table import (
    SmartTableWidgetItem, enable_sorting_on_table, batch_table_update
)

@register
class RegexTesterTool(Tool):
    id = "text.regex"
    name = "Testador de Expressões Regulares (Regex)"
    category = "Texto e Redação"
    description = "Testa expressões regulares em tempo real com grupos de captura, substituição e flags"
    keywords = ["regex", "regexp", "expressao", "regular", "match", "substituir", "padrao", "texto"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return RegexTesterView(self, parent)

class RegexTesterView(QWidget):
    def __init__(self, tool: RegexTesterTool, parent: Optional[QWidget] = None):
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

        # Card de Expressão Regular e Flags
        card_regex = QFrame()
        card_regex.setProperty("class", "card")
        l_reg = QVBoxLayout(card_regex)
        l_reg.setSpacing(10)

        row_pat = QHBoxLayout()
        row_pat.addWidget(QLabel("Padrão Regex:"))
        self.txt_pattern = QLineEdit(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
        self.txt_pattern.textChanged.connect(self._run_regex)
        row_pat.addWidget(self.txt_pattern, stretch=1)
        l_reg.addLayout(row_pat)

        # Flags
        row_flags = QHBoxLayout()
        row_flags.addWidget(QLabel("Opções/Flags:"))
        self.chk_i = QCheckBox("Ignorar maiúsculas/minúsculas (i)")
        self.chk_i.setChecked(True)
        self.chk_i.stateChanged.connect(self._run_regex)
        row_flags.addWidget(self.chk_i)

        self.chk_m = QCheckBox("Multilinha (m)")
        self.chk_m.stateChanged.connect(self._run_regex)
        row_flags.addWidget(self.chk_m)

        self.chk_s = QCheckBox("Ponto inclui quebra de linha (s)")
        self.chk_s.stateChanged.connect(self._run_regex)
        row_flags.addWidget(self.chk_s)
        row_flags.addStretch()
        l_reg.addLayout(row_flags)

        layout.addWidget(card_regex)

        # Texto de Teste
        col_test = QVBoxLayout()
        col_test.addWidget(QLabel("Texto para Testar:"))
        self.txt_input = QPlainTextEdit()
        self.txt_input.setPlaceholderText("Digite ou cole o texto que será avaliado pelo Regex...")
        self.txt_input.setPlainText(
            "Entre em contato pelo e-mail suporte@empresa.com.br ou vendas@contato.io para mais detalhes.\n"
            "Outro e-mail de teste: admin@localhost.net."
        )
        self.txt_input.setFixedHeight(120)
        self.txt_input.textChanged.connect(self._run_regex)
        col_test.addWidget(self.txt_input)
        layout.addLayout(col_test)

        # Abas de Resultado
        tabs = QTabWidget()

        # ABA 1: Correspondências (Matches)
        tab_matches = QWidget()
        l_matches = QVBoxLayout(tab_matches)
        l_matches.setSpacing(8)

        self.lbl_match_count = QLabel("Correspondências encontradas: 0")
        self.lbl_match_count.setStyleSheet("font-weight: 600;")
        l_matches.addWidget(self.lbl_match_count)

        self.table_matches = QTableWidget(0, 4)
        self.table_matches.setHorizontalHeaderLabels(["#", "Texto Encontrado", "Posição (Início - Fim)", "Grupos de Captura"])
        self.table_matches.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_matches.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_matches.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_matches.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table_matches.verticalHeader().setVisible(False)
        self.table_matches.setFixedHeight(180)
        enable_sorting_on_table(self.table_matches)
        l_matches.addWidget(self.table_matches)

        tabs.addTab(tab_matches, "Correspondências Encontradas")

        # ABA 2: Substituição
        tab_sub = QWidget()
        l_sub = QVBoxLayout(tab_sub)
        l_sub.setSpacing(10)

        row_sub_in = QHBoxLayout()
        row_sub_in.addWidget(QLabel("Substituir por:"))
        self.txt_replacement = QLineEdit("[E-MAIL OCULTO]")
        self.txt_replacement.textChanged.connect(self._run_regex)
        row_sub_in.addWidget(self.txt_replacement, stretch=1)

        self.btn_copy_sub = QPushButton("Copiar Resultado")
        self.btn_copy_sub.clicked.connect(self._copy_sub_result)
        row_sub_in.addWidget(self.btn_copy_sub)
        l_sub.addLayout(row_sub_in)

        l_sub.addWidget(QLabel("Texto Resultante:"))
        self.txt_sub_result = QPlainTextEdit()
        self.txt_sub_result.setReadOnly(True)
        self.txt_sub_result.setFixedHeight(140)
        l_sub.addWidget(self.txt_sub_result)

        tabs.addTab(tab_sub, "Substituição")

        # ABA 3: Referência Rápida de Sintaxe
        tab_cheat = QWidget()
        l_cheat = QVBoxLayout(tab_cheat)
        lbl_cheat_content = QLabel(
            "• <b>\\d</b> = Dígito [0-9] | <b>\\D</b> = Não-dígito<br>"
            "• <b>\\w</b> = Caractere alfanumérico [a-zA-Z0-9_] | <b>\\W</b> = Não-alfanumérico<br>"
            "• <b>\\s</b> = Espaço em branco ou tabulação | <b>\\S</b> = Não-espaço<br>"
            "• <b>^</b> = Início da linha | <b>$</b> = Fim da linha<br>"
            "• <b>*</b> = 0 ou mais vezes | <b>+</b> = 1 ou mais vezes | <b>?</b> = Opcional (0 ou 1)<br>"
            "• <b>{n,m}</b> = De n a m repetições<br>"
            "• <b>(grupo)</b> = Grupo de captura | <b>(?:não-captura)</b> = Agrupamento sem capturar<br>"
            "• <b>(?P&lt;nome&gt;...)</b> = Grupo nomeado"
        )
        lbl_cheat_content.setTextFormat(Qt.RichText)
        lbl_cheat_content.setProperty("class", "secondary")
        l_cheat.addWidget(lbl_cheat_content)
        l_cheat.addStretch()
        tabs.addTab(tab_cheat, "Guia Rápido de Sintaxe")

        layout.addWidget(tabs)
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        # Executa a primeira avaliação
        self._run_regex()

    def _run_regex(self):
        pattern = self.txt_pattern.text()
        text = self.txt_input.toPlainText()
        repl = self.txt_replacement.text()

        res = evaluate_regex(
            pattern=pattern,
            text=text,
            replacement=repl,
            ignore_case=self.chk_i.isChecked(),
            multiline=self.chk_m.isChecked(),
            dotall=self.chk_s.isChecked(),
        )

        if not pattern:
            self.lbl_match_count.setText(res.error_message or "Informe um padrão regex.")
            self.lbl_match_count.setStyleSheet("font-weight: 600;")
            self.table_matches.setRowCount(0)
            self.txt_sub_result.setPlainText(res.substituted_text)
            return

        if not res.is_valid:
            self.lbl_match_count.setText(res.error_message or "Erro no regex")
            self.lbl_match_count.setStyleSheet("font-weight: 600; color: #ffa198;")
            self.table_matches.setRowCount(0)
            self.txt_sub_result.setPlainText(res.substituted_text)
            return

        self.lbl_match_count.setText(f"Correspondências encontradas: {len(res.matches)}")
        self.lbl_match_count.setStyleSheet("font-weight: 600; color: #7ee787;")

        with batch_table_update(self.table_matches):
            self.table_matches.setRowCount(len(res.matches))
            for i, m in enumerate(res.matches):
                self.table_matches.setItem(i, 0, SmartTableWidgetItem(str(m.index), sort_value=m.index, user_data=m))
                self.table_matches.setItem(i, 1, SmartTableWidgetItem(m.text))
                self.table_matches.setItem(i, 2, SmartTableWidgetItem(f"{m.start} - {m.end}", sort_value=m.start))

                groups_str = ", ".join(f"g{idx+1}='{g}'" for idx, g in enumerate(m.groups)) if m.groups else "-"
                self.table_matches.setItem(i, 3, SmartTableWidgetItem(groups_str))

        self.txt_sub_result.setPlainText(res.substituted_text)

    def _copy_sub_result(self):
        text = self.txt_sub_result.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
