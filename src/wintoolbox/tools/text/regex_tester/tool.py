"""
Ferramenta: Testador Interativo de Expressões Regulares (RegEx Tester).
Permite testar padrões, inspecionar grupos de captura e realizar substituições em tempo real.
"""
import re
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QSplitter,
    QTabWidget, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.ui.widgets.data_table import Column, DataTableView
from wintoolbox.tools.text.regex_tester.logic import (
    COMMON_REGEX_PATTERNS,
    RegexMatchItem,
    apply_regex_replace,
    find_regex_matches,
)


@register
class RegexTesterTool(Tool):
    id = "text.regex_tester"
    name = "Testador de Expressões Regulares (RegEx)"
    category = "Texto e Redação"
    description = "Teste padrões regex em tempo real, inspecione grupos de captura, substituições e catálogo de padrões"
    keywords = ["regex", "regexp", "expressao regular", "padrao", "email", "cpf", "busca", "substituicao"]

    def __init__(self) -> None:
        super().__init__()
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._evaluate_regex)

    def build_ui(self) -> QWidget:
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Seleção de Padrões Comuns
        preset_bar = QHBoxLayout()
        preset_bar.addWidget(QLabel("Padrões Prontos:"))
        self.cmb_preset = QComboBox()
        self.cmb_preset.addItem("Personalizado...")
        for name in COMMON_REGEX_PATTERNS:
            self.cmb_preset.addItem(name)
        self.cmb_preset.currentTextChanged.connect(self._on_preset_selected)
        preset_bar.addWidget(self.cmb_preset, stretch=1)
        main_layout.addLayout(preset_bar)

        # Campo da Expressão Regular
        pattern_layout = QHBoxLayout()
        pattern_layout.addWidget(QLabel("<b>Padrão RegEx:</b>"))
        self.txt_pattern = QLineEdit(r"([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
        self.txt_pattern.setStyleSheet("font-family: Consolas, monospace; font-size: 13px;")
        self.txt_pattern.textChanged.connect(self._schedule_eval)
        pattern_layout.addWidget(self.txt_pattern, stretch=1)
        main_layout.addLayout(pattern_layout)

        # Flags
        flags_bar = QHBoxLayout()
        self.chk_i = QCheckBox("Ignorar Maiúsculas/Minúsculas (re.I)")
        self.chk_i.stateChanged.connect(self._schedule_eval)
        flags_bar.addWidget(self.chk_i)

        self.chk_m = QCheckBox("Multilinha ^ e $ (re.M)")
        self.chk_m.stateChanged.connect(self._schedule_eval)
        flags_bar.addWidget(self.chk_m)

        self.chk_s = QCheckBox("Ponto (.) casa Quebra de Linha (re.S)")
        self.chk_s.stateChanged.connect(self._schedule_eval)
        flags_bar.addWidget(self.chk_s)

        flags_bar.addStretch()
        main_layout.addLayout(flags_bar)

        # Splitter Vertical: Texto e Resultados
        splitter = QSplitter(Qt.Vertical)

        # Texto de Teste
        text_widget = QWidget()
        t_layout = QVBoxLayout(text_widget)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.setSpacing(6)
        t_layout.addWidget(QLabel("<b>Texto Alvo para Teste:</b>"))

        self.txt_input = QPlainTextEdit()
        self.txt_input.setPlaceholderText("Cole o texto de teste aqui...")
        self.txt_input.setPlainText(
            "Entre em contato pelo e-mail suporte@empresa.com.br ou admin@tech.io.\n"
            "Financeiro: faturamento@financeiro.org"
        )
        self.txt_input.textChanged.connect(self._schedule_eval)
        t_layout.addWidget(self.txt_input)
        splitter.addWidget(text_widget)

        # Abas: Ocorrências e Substituição
        tabs = QTabWidget()

        # Aba 1: Matches e Grupos
        tab_matches = QWidget()
        m_layout = QVBoxLayout(tab_matches)
        m_layout.setContentsMargins(6, 6, 6, 6)

        columns = [
            Column("rank_display", "#", width=50),
            Column("span_display", "Posição (Início..Fim)", width=160),
            Column("full_match", "Texto Casado (Match)", width=240),
            Column("groups_display", "Grupos de Captura", stretch=True),
        ]
        self.table_matches = DataTableView(columns, key="span_display", parent=tab_matches)
        m_layout.addWidget(self.table_matches)
        tabs.addTab(tab_matches, "Ocorrências Encontradas (Matches)")

        # Aba 2: Substituição
        tab_replace = QWidget()
        r_layout = QVBoxLayout(tab_replace)
        r_layout.setContentsMargins(8, 8, 8, 8)
        r_layout.setSpacing(8)

        r_input_box = QHBoxLayout()
        r_input_box.addWidget(QLabel("Substituir por:"))
        self.txt_replace = QLineEdit(r"[EMAIL: \1]")
        self.txt_replace.setStyleSheet("font-family: Consolas, monospace;")
        self.txt_replace.textChanged.connect(self._schedule_eval)
        r_input_box.addWidget(self.txt_replace, stretch=1)
        r_layout.addLayout(r_input_box)

        self.txt_result = QPlainTextEdit()
        self.txt_result.setReadOnly(True)
        r_layout.addWidget(self.txt_result)
        tabs.addTab(tab_replace, "Substituição (Replace)")

        splitter.addWidget(tabs)
        splitter.setSizes([180, 260])
        main_layout.addWidget(splitter)

        # Status
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
        main_layout.addWidget(self.lbl_status)

        self._evaluate_regex()
        return container

    def _on_preset_selected(self, text: str) -> None:
        if text in COMMON_REGEX_PATTERNS:
            item = COMMON_REGEX_PATTERNS[text]
            self.txt_pattern.setText(item["pattern"])
            self.lbl_status.setText(item["description"])

    def _schedule_eval(self) -> None:
        self._debounce_timer.start()

    def _evaluate_regex(self) -> None:
        pattern = self.txt_pattern.text().strip()
        text = self.txt_input.toPlainText()

        flags = 0
        if self.chk_i.isChecked():
            flags |= re.IGNORECASE
        if self.chk_m.isChecked():
            flags |= re.MULTILINE
        if self.chk_s.isChecked():
            flags |= re.DOTALL

        if not pattern:
            self.table_matches.set_records([])
            self.txt_result.setPlainText(text)
            self.lbl_status.setText("Digite um padrão regex para testar.")
            self.lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
            return

        try:
            matches = find_regex_matches(pattern, text, flags=flags)
            self.lbl_status.setText(f"{len(matches)} ocorrência(s) encontrada(s) no texto.")
            self.lbl_status.setStyleSheet("color: #16a34a; font-weight: 600; font-size: 12px;")

            rows: List[Dict[str, Any]] = []
            for m in matches:
                groups_txt = ", ".join(f"{k}: '{v}'" for k, v in m.groups.items()) if m.groups else "Nenhum grupo"
                rows.append({
                    "rank_display": str(m.index),
                    "span_display": f"{m.span[0]} até {m.span[1]}",
                    "full_match": m.full_match,
                    "groups_display": groups_txt,
                })
            self.table_matches.set_records(rows)

            # Substituição
            rep_str = self.txt_replace.text()
            replaced = apply_regex_replace(pattern, rep_str, text, flags=flags)
            self.txt_result.setPlainText(replaced)

        except re.error as e:
            self.lbl_status.setText(f"Erro de sintaxe no RegEx: {e}")
            self.lbl_status.setStyleSheet("color: #dc2626; font-weight: 600; font-size: 12px;")
            self.table_matches.set_records([])
