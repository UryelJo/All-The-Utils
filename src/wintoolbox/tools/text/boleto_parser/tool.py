"""
Interface gráfica Fluent da ferramenta Decodificador e Validador de Boletos.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
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
from wintoolbox.tools.text.boleto_parser.logic import (
    BoletoInfo,
    decode_boleto,
    format_linha_digitavel,
)


@register
class BoletoParserTool(Tool):
    """Ferramenta para decodificação, validação e conversão de boletos de cobrança e concessionárias."""
    id = "text.boleto_parser"
    title = "Decodificador de Boletos"
    category = "Texto e Redação"
    description = (
        "Valida e decodifica linha digitável e código de barras de boletos bancários (FEBRABAN) "
        "e concessionárias: identifica banco, valor, data de vencimento e converte entre formatos."
    )
    icon = "Barcode"

    def __init__(self) -> None:
        super().__init__()
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._on_parse)
        self._last_info: BoletoInfo | None = None

    def build_view(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho
        header = QLabel("Decodificador e Validador de Boletos FEBRABAN")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Digite ou cole a linha digitável (47 ou 48 dígitos) ou o código de barras (44 dígitos). "
            "A ferramenta verifica a autenticidade dos dígitos verificadores (Módulo 10 e 11), "
            "identifica o banco emissor, extrai o valor nominal e calcula a data de vencimento."
        )
        desc.setStyleSheet("color: gray;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Entrada
        grp_input = QGroupBox("Linha Digitável ou Código de Barras")
        v_in = QVBoxLayout(grp_input)
        v_in.setSpacing(8)

        self.edit_input = QLineEdit()
        self.edit_input.setPlaceholderText("Ex: 34191.09008 00000.282111 00557.740008 6 99990000015025")
        self.edit_input.setStyleSheet("font-size: 15px; padding: 6px;")
        self.edit_input.textChanged.connect(self._trigger_debounce)
        v_in.addWidget(self.edit_input)

        # Exemplos rápidos
        bar_samples = QHBoxLayout()
        bar_samples.addWidget(QLabel("Exemplos para teste:"))

        btn_itau = QPushButton("Itaú Cobrança")
        btn_itau.clicked.connect(lambda: self._set_sample(
            "34191.09008 00000.282111 00557.740008 6 99990000015025"
        ))
        bar_samples.addWidget(btn_itau)

        btn_bb = QPushButton("Banco do Brasil")
        btn_bb.clicked.connect(lambda: self._set_sample(
            "00190.00009 01887.892008 00000.000187 1 99990000035000"
        ))
        bar_samples.addWidget(btn_bb)

        btn_concess = QPushButton("Concessionária")
        btn_concess.clicked.connect(lambda: self._set_sample(
            "836200000011 050001380004 000000000001 000000000002"
        ))
        bar_samples.addWidget(btn_concess)

        bar_samples.addStretch()
        btn_clear = QPushButton("Limpar")
        btn_clear.clicked.connect(self.edit_input.clear)
        bar_samples.addWidget(btn_clear)

        v_in.addLayout(bar_samples)
        layout.addWidget(grp_input)

        # Card de Status / Validade
        self.frame_status = QFrame()
        self.frame_status.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame_status.setStyleSheet("background-color: rgba(0, 120, 212, 0.1); border-radius: 6px;")
        status_layout = QHBoxLayout(self.frame_status)
        status_layout.setContentsMargins(12, 10, 12, 10)

        self.lbl_status_icon = QLabel("ℹ")
        self.lbl_status_icon.setStyleSheet("font-size: 20px; font-weight: bold;")
        status_layout.addWidget(self.lbl_status_icon)

        self.lbl_status_text = QLabel("Aguardando entrada de dados...")
        self.lbl_status_text.setStyleSheet("font-size: 14px; font-weight: bold;")
        status_layout.addWidget(self.lbl_status_text, 1)

        layout.addWidget(self.frame_status)

        # Grade com Dados Decodificados
        grp_details = QGroupBox("Dados Extraídos do Documento")
        grid = QGridLayout(grp_details)
        grid.setSpacing(12)

        grid.addWidget(QLabel("Instituição Financeira / Segmento:"), 0, 0)
        self.lbl_banco = QLabel("-")
        self.lbl_banco.setStyleSheet("font-weight: bold; font-size: 14px;")
        grid.addWidget(self.lbl_banco, 0, 1)

        grid.addWidget(QLabel("Valor Nominal:"), 0, 2)
        self.lbl_valor = QLabel("-")
        self.lbl_valor.setStyleSheet("font-size: 16px; font-weight: bold; color: #107C41;")
        grid.addWidget(self.lbl_valor, 0, 3)

        grid.addWidget(QLabel("Data de Vencimento:"), 1, 0)
        self.lbl_vencimento = QLabel("-")
        self.lbl_vencimento.setStyleSheet("font-weight: bold; font-size: 14px;")
        grid.addWidget(self.lbl_vencimento, 1, 1)

        grid.addWidget(QLabel("Tipo de Documento:"), 1, 2)
        self.lbl_tipo = QLabel("-")
        self.lbl_tipo.setStyleSheet("font-weight: bold;")
        grid.addWidget(self.lbl_tipo, 1, 3)

        grid.addWidget(QLabel("Fator de Vencimento:"), 2, 0)
        self.lbl_fator = QLabel("-")
        grid.addWidget(self.lbl_fator, 2, 1)

        grid.addWidget(QLabel("Campo Livre:"), 2, 2)
        self.lbl_campo_livre = QLabel("-")
        grid.addWidget(self.lbl_campo_livre, 2, 3)

        layout.addWidget(grp_details)

        # Códigos Formatados para Cópia
        grp_codes = QGroupBox("Códigos Prontos para Uso")
        v_codes = QVBoxLayout(grp_codes)
        v_codes.setSpacing(10)

        # Linha Digitável
        row_ld = QHBoxLayout()
        row_ld.addWidget(QLabel("Linha Digitável:"))
        self.edit_res_linha = QLineEdit()
        self.edit_res_linha.setReadOnly(True)
        row_ld.addWidget(self.edit_res_linha, 1)
        btn_copy_linha = QPushButton("Copiar")
        btn_copy_linha.clicked.connect(lambda: self._copy_text(self.edit_res_linha.text()))
        row_ld.addWidget(btn_copy_linha)
        v_codes.addLayout(row_ld)

        # Código de Barras
        row_cb = QHBoxLayout()
        row_cb.addWidget(QLabel("Código de Barras (44 dígitos):"))
        self.edit_res_barras = QLineEdit()
        self.edit_res_barras.setReadOnly(True)
        row_cb.addWidget(self.edit_res_barras, 1)
        btn_copy_barras = QPushButton("Copiar")
        btn_copy_barras.clicked.connect(lambda: self._copy_text(self.edit_res_barras.text()))
        row_cb.addWidget(btn_copy_barras)
        v_codes.addLayout(row_cb)

        layout.addWidget(grp_codes)
        layout.addStretch()

        self._set_sample("34191.09008 00000.282111 00557.740008 6 99990000015025")
        return container

    def _set_sample(self, text: str) -> None:
        self.edit_input.setText(text)
        self._on_parse()

    def _trigger_debounce(self) -> None:
        self._debounce_timer.start()

    def _on_parse(self) -> None:
        raw = self.edit_input.text()
        info = decode_boleto(raw)
        self._last_info = info

        if not raw.strip():
            self.lbl_status_icon.setText("ℹ")
            self.lbl_status_text.setText("Digite ou cole a linha digitável acima.")
            self.frame_status.setStyleSheet("background-color: rgba(0, 120, 212, 0.1); border-radius: 6px;")
            self._clear_fields()
            return

        if info.is_valid:
            self.lbl_status_icon.setText("✔")
            self.lbl_status_text.setText("Boleto Válido! Todos os dígitos verificadores foram conferidos com sucesso.")
            self.frame_status.setStyleSheet("background-color: rgba(16, 124, 65, 0.15); color: #107C41; border-radius: 6px;")
        else:
            self.lbl_status_icon.setText("✖")
            self.lbl_status_text.setText(f"Atenção: {info.erro_mensagem}")
            self.frame_status.setStyleSheet("background-color: rgba(216, 59, 1, 0.15); color: #D83B01; border-radius: 6px;")

        self.lbl_banco.setText(f"{info.banco_codigo} - {info.banco_nome}" if info.banco_codigo else "-")
        self.lbl_tipo.setText("Cobrança Bancária" if info.tipo == "COBRANCA" else "Concessionária / Tributo")

        if info.valor is not None:
            self.lbl_valor.setText(f"R$ {info.valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        else:
            self.lbl_valor.setText("Não informado / Variável")

        if info.data_vencimento is not None:
            self.lbl_vencimento.setText(info.data_vencimento.strftime("%d/%m/%Y"))
        else:
            self.lbl_vencimento.setText("Sem vencimento / Não identificado")

        self.lbl_fator.setText(str(info.fator_vencimento) if info.fator_vencimento else "-")
        self.lbl_campo_livre.setText(info.campo_livre or "-")

        self.edit_res_linha.setText(format_linha_digitavel(info.linha_digitavel))
        self.edit_res_barras.setText(info.codigo_barras)

    def _clear_fields(self) -> None:
        self.lbl_banco.setText("-")
        self.lbl_valor.setText("-")
        self.lbl_vencimento.setText("-")
        self.lbl_tipo.setText("-")
        self.lbl_fator.setText("-")
        self.lbl_campo_livre.setText("-")
        self.edit_res_linha.clear()
        self.edit_res_barras.clear()

    def _copy_text(self, text: str) -> None:
        if text:
            cb = QApplication.clipboard()
            if cb:
                cb.setText(text)
