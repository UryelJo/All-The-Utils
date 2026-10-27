"""
Interface gráfica Fluent da ferramenta Conversor IDN Punycode e Entidades HTML.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.encode.punycode_html.logic import (
    decode_html_entities,
    domain_to_punycode,
    encode_html_entities,
    punycode_to_domain,
)


@register
class PunycodeHtmlTool(Tool):
    """Ferramenta para conversão de domínios internacionalizados (IDN/Punycode) e entidades HTML."""
    id = "encode.punycode_html"
    name = "Conversor Punycode e HTML"
    title = "Conversor Punycode e HTML"
    category = "Codificação e Hash"
    description = (
        "Converte domínios internacionalizados com acentos para Punycode (xn--...) e vice-versa, "
        "além de codificar e decodificar entidades de caracteres HTML (nomeadas, decimais e hexadecimais)."
    )
    icon = "Globe"

    def build_view(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho
        header = QLabel("Conversor IDN Punycode e Entidades HTML")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Utilitário web para codificação de domínios internacionalizados com suporte a caracteres não-ASCII (IDN / Punycode) "
            "e manipulação completa de entidades de caracteres para desenvolvimento HTML/XML."
        )
        desc.setStyleSheet("color: gray;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Tabs de Trabalho
        tabs = QTabWidget()

        # Tab 1: Domínios IDN / Punycode
        tab_puny = QWidget()
        v_puny = QVBoxLayout(tab_puny)
        v_puny.setContentsMargins(10, 10, 10, 10)
        v_puny.setSpacing(12)

        bar_puny_actions = QHBoxLayout()
        btn_to_puny = QPushButton("Converter para Punycode (xn--...) ▶")
        btn_to_puny.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        btn_to_puny.clicked.connect(self._convert_to_punycode)
        bar_puny_actions.addWidget(btn_to_puny)

        btn_from_puny = QPushButton("◀ Converter para Domínio Unicode")
        btn_from_puny.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        btn_from_puny.clicked.connect(self._convert_from_punycode)
        bar_puny_actions.addWidget(btn_from_puny)

        bar_puny_actions.addStretch()
        v_puny.addLayout(bar_puny_actions)

        split_puny = QSplitter(Qt.Orientation.Horizontal)

        grp_p_in = QGroupBox("Domínio / URL de Entrada")
        v_pi = QVBoxLayout(grp_p_in)
        self.edit_puny_in = QTextEdit()
        self.edit_puny_in.setPlaceholderText("Ex: münchen.de ou café.com.br ou https://ações.org/carteira")
        v_pi.addWidget(self.edit_puny_in)

        quick_puny = QHBoxLayout()
        quick_puny.addWidget(QLabel("Exemplos:"))
        for s in ["münchen.de", "café.com.br", "xn--mnchen-3ya.de"]:
            btn_s = QPushButton(s)
            btn_s.clicked.connect(lambda _, val=s: self.edit_puny_in.setPlainText(val))
            quick_puny.addWidget(btn_s)
        quick_puny.addStretch()
        v_pi.addLayout(quick_puny)
        split_puny.addWidget(grp_p_in)

        grp_p_out = QGroupBox("Resultado da Conversão")
        v_po = QVBoxLayout(grp_p_out)
        self.edit_puny_out = QTextEdit()
        self.edit_puny_out.setReadOnly(True)
        self.edit_puny_out.setStyleSheet("font-family: Consolas, monospace; font-size: 14px;")
        v_po.addWidget(self.edit_puny_out)

        btn_copy_puny = QPushButton("Copiar Resultado")
        btn_copy_puny.clicked.connect(lambda: self._copy_text(self.edit_puny_out.toPlainText()))
        v_po.addWidget(btn_copy_puny)
        split_puny.addWidget(grp_p_out)

        v_puny.addWidget(split_puny)
        tabs.addTab(tab_puny, "Domínios IDN / Punycode")

        # Tab 2: Entidades HTML
        tab_html = QWidget()
        v_html = QVBoxLayout(tab_html)
        v_html.setContentsMargins(10, 10, 10, 10)
        v_html.setSpacing(12)

        bar_html_actions = QHBoxLayout()
        bar_html_actions.addWidget(QLabel("Formato de Codificação:"))
        self.combo_html_mode = QComboBox()
        self.combo_html_mode.addItem("Entidades Nomeadas (&copy;, &lt;)", "named")
        self.combo_html_mode.addItem("Entidades Decimais (&#169;, &#60;)", "decimal")
        self.combo_html_mode.addItem("Entidades Hexadecimais (&#xA9;, &#x3C;)", "hex")
        bar_html_actions.addWidget(self.combo_html_mode)

        btn_encode_html = QPushButton("Codificar Texto para HTML ▶")
        btn_encode_html.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        btn_encode_html.clicked.connect(self._encode_html)
        bar_html_actions.addWidget(btn_encode_html)

        btn_decode_html = QPushButton("◀ Decodificar HTML para Texto")
        btn_decode_html.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        btn_decode_html.clicked.connect(self._decode_html)
        bar_html_actions.addWidget(btn_decode_html)

        bar_html_actions.addStretch()
        v_html.addLayout(bar_html_actions)

        split_html = QSplitter(Qt.Orientation.Horizontal)

        grp_h_in = QGroupBox("Texto / HTML de Entrada")
        v_hi = QVBoxLayout(grp_h_in)
        self.edit_html_in = QTextEdit()
        self.edit_html_in.setPlaceholderText("Cole o texto com caracteres especiais ou o código HTML com entidades...")
        v_hi.addWidget(self.edit_html_in)

        quick_html = QHBoxLayout()
        quick_html.addWidget(QLabel("Exemplos:"))
        btn_h_ex = QPushButton("Atenção: 5 < 10 & 20 > 15 © 2026")
        btn_h_ex.clicked.connect(lambda: self.edit_html_in.setPlainText("Atenção: 5 < 10 & 20 > 15 © 2026"))
        quick_html.addWidget(btn_h_ex)
        quick_html.addStretch()
        v_hi.addLayout(quick_html)
        split_html.addWidget(grp_h_in)

        grp_h_out = QGroupBox("Resultado")
        v_ho = QVBoxLayout(grp_h_out)
        self.edit_html_out = QTextEdit()
        self.edit_html_out.setReadOnly(True)
        self.edit_html_out.setStyleSheet("font-family: Consolas, monospace; font-size: 14px;")
        v_ho.addWidget(self.edit_html_out)

        btn_copy_html = QPushButton("Copiar Resultado")
        btn_copy_html.clicked.connect(lambda: self._copy_text(self.edit_html_out.toPlainText()))
        v_ho.addWidget(btn_copy_html)
        split_html.addWidget(grp_h_out)

        v_html.addWidget(split_html)
        tabs.addTab(tab_html, "Entidades de Caracteres HTML")

        layout.addWidget(tabs, 1)

        self.edit_puny_in.setPlainText("münchen.de\ncafé.com.br")
        self.edit_html_in.setPlainText("Atenção: 5 < 10 & 20 > 15 © 2026")

        return container

    def _convert_to_punycode(self) -> None:
        lines = self.edit_puny_in.toPlainText().splitlines()
        res = [domain_to_punycode(line) for line in lines]
        self.edit_puny_out.setPlainText("\n".join(res))

    def _convert_from_punycode(self) -> None:
        lines = self.edit_puny_in.toPlainText().splitlines()
        res = [punycode_to_domain(line) for line in lines]
        self.edit_puny_out.setPlainText("\n".join(res))

    def _encode_html(self) -> None:
        text = self.edit_html_in.toPlainText()
        mode = self.combo_html_mode.currentData()
        res = encode_html_entities(text, mode=mode)
        self.edit_html_out.setPlainText(res)

    def _decode_html(self) -> None:
        text = self.edit_html_in.toPlainText()
        res = decode_html_entities(text)
        self.edit_html_out.setPlainText(res)

    def _copy_text(self, text: str) -> None:
        if text:
            cb = QApplication.clipboard()
            if cb:
                cb.setText(text)
