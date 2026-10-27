"""
Interface gráfica da ferramenta de Conversão de Números e Moeda para Extenso.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.text.number_words.logic import (
    currency_to_words,
    number_to_words,
    ordinal_to_words,
)


@register
class NumberWordsTool(Tool):
    """Ferramenta para conversão de numerais e valores monetários para extenso."""
    id = "text.number_words"
    title = "Número por Extenso"
    category = "Texto e Redação"
    description = (
        "Converte valores numéricos e monetários (BRL) para extenso em português do Brasil, "
        "com formatação especial para cheques, recibos e numerais ordinais."
    )
    icon = "Money"

    def build_view(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Cabeçalho
        header = QLabel("Conversor de Números e Valores por Extenso")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Digite um número ou valor monetário abaixo para gerar instantaneamente a escrita por extenso "
            "com conformidade às regras ortográficas brasileiras, ideal para preenchimento de recibos e contratos."
        )
        desc.setStyleSheet("color: gray;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Configurações e Modos
        ctrl_frame = QFrame()
        ctrl_frame.setFrameShape(QFrame.Shape.StyledPanel)
        ctrl_layout = QHBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(10, 10, 10, 10)
        ctrl_layout.setSpacing(16)

        ctrl_layout.addWidget(QLabel("Modo de Conversão:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "Valor Monetário (Reais e Centavos)",
            "Cardinal Puro (Número Inteiro)",
            "Ordinal (Posição / Ordem)",
        ])
        self.combo_mode.currentIndexChanged.connect(self._on_convert)
        ctrl_layout.addWidget(self.combo_mode)

        self.chk_cheque = QCheckBox("Formato de Cheque (# MAIÚSCULAS #)")
        self.chk_cheque.toggled.connect(self._on_convert)
        ctrl_layout.addWidget(self.chk_cheque)

        self.chk_feminine = QCheckBox("Feminino (para ordinais)")
        self.chk_feminine.toggled.connect(self._on_convert)
        ctrl_layout.addWidget(self.chk_feminine)

        ctrl_layout.addStretch()
        layout.addWidget(ctrl_frame)

        # Caixa de Entrada
        grp_input = QGroupBox("Entrada de Dados")
        input_layout = QVBoxLayout(grp_input)
        input_layout.setSpacing(8)

        self.edit_input = QLineEdit()
        self.edit_input.setPlaceholderText("Ex: 1250,50 ou R$ 1.250,50 ou 42")
        self.edit_input.setStyleSheet("font-size: 16px; padding: 6px;")
        self.edit_input.textChanged.connect(self._on_convert)
        input_layout.addWidget(self.edit_input)

        # Botões de Exemplo Rápido
        quick_layout = QHBoxLayout()
        quick_layout.addWidget(QLabel("Exemplos rápidos:"))
        for sample in ["R$ 1.250,50", "2.000.000,00", "150,00", "42", "23"]:
            btn_quick = QPushButton(sample)
            btn_quick.clicked.connect(lambda _, s=sample: self._set_quick_example(s))
            quick_layout.addWidget(btn_quick)
        quick_layout.addStretch()
        input_layout.addLayout(quick_layout)

        layout.addWidget(grp_input)

        # Caixa de Saída / Resultado
        grp_output = QGroupBox("Resultado por Extenso")
        out_layout = QVBoxLayout(grp_output)
        out_layout.setSpacing(10)

        self.text_result = QTextEdit()
        self.text_result.setReadOnly(True)
        self.text_result.setStyleSheet("font-size: 16px; font-weight: 500; line-height: 1.4;")
        self.text_result.setMaximumHeight(130)
        out_layout.addWidget(self.text_result)

        btn_row = QHBoxLayout()
        self.btn_copy = QPushButton("Copiar Extenso")
        self.btn_copy.setStyleSheet("font-weight: bold; padding: 8px 16px;")
        self.btn_copy.clicked.connect(self._on_copy)
        btn_row.addWidget(self.btn_copy)

        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setStyleSheet("color: #107C41; font-weight: bold;")
        btn_row.addWidget(self.lbl_feedback)
        btn_row.addStretch()
        out_layout.addLayout(btn_row)

        layout.addWidget(grp_output)
        layout.addStretch()

        self._set_quick_example("R$ 1.250,50")
        return container

    def _set_quick_example(self, text: str) -> None:
        self.edit_input.setText(text)
        self._on_convert()

    def _on_convert(self) -> None:
        raw_val = self.edit_input.text().strip()
        self.lbl_feedback.setText("")

        if not raw_val:
            self.text_result.setPlainText("")
            return

        mode_idx = self.combo_mode.currentIndex()
        cheque = self.chk_cheque.isChecked()
        feminine = self.chk_feminine.isChecked()

        try:
            if mode_idx == 0:  # Moeda
                res = currency_to_words(raw_val, cheque_format=cheque)
            elif mode_idx == 1:  # Cardinal
                # Limpa não-dígitos
                cleaned = "".join(c for c in raw_val if c.isdigit() or c == "-")
                if cleaned:
                    n = int(cleaned)
                    res = number_to_words(n)
                    if cheque:
                        res = f"# {res.upper()} #"
                else:
                    res = ""
            else:  # Ordinal
                cleaned = "".join(c for c in raw_val if c.isdigit())
                if cleaned:
                    n = int(cleaned)
                    res = ordinal_to_words(n, feminine=feminine)
                    if cheque:
                        res = f"# {res.upper()} #"
                else:
                    res = ""

            self.text_result.setPlainText(res)
        except Exception as e:
            self.text_result.setPlainText(f"Erro ao converter: {e}")

    def _on_copy(self) -> None:
        text = self.text_result.toPlainText()
        if not text:
            return
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            self.lbl_feedback.setText("Copiado com sucesso!")
