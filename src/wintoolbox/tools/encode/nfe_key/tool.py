"""
Interface gráfica Fluent da ferramenta Decodificador de Chave de Acesso NF-e.
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
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.encode.nfe_key.logic import (
    decode_nfe_key,
    format_nfe_key,
    generate_sample_nfe_key,
    NFeKeyInfo,
)


@register
class NFeKeyTool(Tool):
    """Ferramenta para validação, decodificação e análise de chaves de documentos fiscais (NF-e, NFC-e, CT-e)."""
    id = "encode.nfe_key"
    title = "Decodificador de Chave NF-e"
    category = "Codificação e Hash"
    description = (
        "Valida e decodifica a chave de acesso de 44 dígitos de documentos fiscais eletrônicos (NF-e, NFC-e, CT-e, MDF-e): "
        "calcula dígito verificador Módulo 11 SEFAZ e extrai UF, data, CNPJ, modelo, série e número da nota."
    )
    icon = "Document"

    def __init__(self) -> None:
        super().__init__()
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._on_parse)
        self._last_info: NFeKeyInfo | None = None

    def build_view(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho
        header = QLabel("Decodificador de Chave de Acesso Fiscal (NF-e / NFC-e / CT-e)")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Digite ou cole a chave de 44 dígitos da nota fiscal para conferir a autenticidade do dígito verificador (DV) "
            "e inspecionar instantaneamente os metadados oficiais definidos pela SEFAZ."
        )
        desc.setStyleSheet("color: gray;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Entrada
        grp_in = QGroupBox("Chave de Acesso (44 dígitos)")
        v_in = QVBoxLayout(grp_in)
        v_in.setSpacing(8)

        self.edit_input = QLineEdit()
        self.edit_input.setPlaceholderText("Ex: 3526 0300 0000 0000 0191 5500 1000 1234 5619 8765 4321")
        self.edit_input.setStyleSheet("font-family: Consolas, monospace; font-size: 15px; padding: 6px;")
        self.edit_input.textChanged.connect(self._trigger_debounce)
        v_in.addWidget(self.edit_input)

        bar_samples = QHBoxLayout()
        bar_samples.addWidget(QLabel("Exemplos para teste:"))

        btn_sample_sp = QPushButton("Gerar NF-e SP (Mod 55)")
        btn_sample_sp.clicked.connect(lambda: self._set_sample("35", "55"))
        bar_samples.addWidget(btn_sample_sp)

        btn_sample_rj = QPushButton("Gerar NFC-e RJ (Mod 65)")
        btn_sample_rj.clicked.connect(lambda: self._set_sample("33", "65"))
        bar_samples.addWidget(btn_sample_rj)

        btn_sample_pr = QPushButton("Gerar CT-e PR (Mod 57)")
        btn_sample_pr.clicked.connect(lambda: self._set_sample("41", "57"))
        bar_samples.addWidget(btn_sample_pr)

        bar_samples.addStretch()
        btn_clear = QPushButton("Limpar")
        btn_clear.clicked.connect(self.edit_input.clear)
        bar_samples.addWidget(btn_clear)

        v_in.addLayout(bar_samples)
        layout.addWidget(grp_in)

        # Banner de Validade
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

        # Grade com Metadados
        grp_details = QGroupBox("Metadados Fiscais Decodificados")
        grid = QGridLayout(grp_details)
        grid.setSpacing(12)

        grid.addWidget(QLabel("UF do Emitente:"), 0, 0)
        self.lbl_uf = QLabel("-")
        self.lbl_uf.setStyleSheet("font-weight: bold; font-size: 14px;")
        grid.addWidget(self.lbl_uf, 0, 1)

        grid.addWidget(QLabel("Ano e Mês de Emissão:"), 0, 2)
        self.lbl_data = QLabel("-")
        self.lbl_data.setStyleSheet("font-weight: bold; font-size: 14px;")
        grid.addWidget(self.lbl_data, 0, 3)

        grid.addWidget(QLabel("CNPJ do Emitente:"), 1, 0)
        self.lbl_cnpj = QLabel("-")
        self.lbl_cnpj.setStyleSheet("font-family: Consolas, monospace; font-weight: bold; font-size: 14px; color: #0078D4;")
        grid.addWidget(self.lbl_cnpj, 1, 1)

        grid.addWidget(QLabel("Modelo de Documento:"), 1, 2)
        self.lbl_modelo = QLabel("-")
        self.lbl_modelo.setStyleSheet("font-weight: bold;")
        grid.addWidget(self.lbl_modelo, 1, 3)

        grid.addWidget(QLabel("Série / Número da Nota:"), 2, 0)
        self.lbl_serie_num = QLabel("-")
        self.lbl_serie_num.setStyleSheet("font-weight: bold;")
        grid.addWidget(self.lbl_serie_num, 2, 1)

        grid.addWidget(QLabel("Tipo de Emissão:"), 2, 2)
        self.lbl_tipo_emissao = QLabel("-")
        grid.addWidget(self.lbl_tipo_emissao, 2, 3)

        grid.addWidget(QLabel("Código Numérico / DV:"), 3, 0)
        self.lbl_cnf_cdv = QLabel("-")
        grid.addWidget(self.lbl_cnf_cdv, 3, 1)

        layout.addWidget(grp_details)

        # Cópia e Formatação
        grp_copy = QGroupBox("Chave Formatada para Consulta")
        v_copy = QVBoxLayout(grp_copy)
        row_cp = QHBoxLayout()

        self.edit_formatted = QLineEdit()
        self.edit_formatted.setReadOnly(True)
        self.edit_formatted.setStyleSheet("font-family: Consolas, monospace; font-size: 14px;")
        row_cp.addWidget(self.edit_formatted, 1)

        btn_copy = QPushButton("Copiar Chave")
        btn_copy.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        btn_copy.clicked.connect(self._copy_key)
        row_cp.addWidget(btn_copy)
        v_copy.addLayout(row_cp)
        layout.addWidget(grp_copy)

        layout.addStretch()

        self._set_sample("35", "55")
        return container

    def _set_sample(self, uf: str, mod: str) -> None:
        key = generate_sample_nfe_key(uf, mod)
        self.edit_input.setText(format_nfe_key(key))
        self._on_parse()

    def _trigger_debounce(self) -> None:
        self._debounce_timer.start()

    def _on_parse(self) -> None:
        raw = self.edit_input.text()
        info = decode_nfe_key(raw)
        self._last_info = info

        if not raw.strip():
            self.lbl_status_icon.setText("ℹ")
            self.lbl_status_text.setText("Digite ou cole a chave de 44 dígitos acima.")
            self.frame_status.setStyleSheet("background-color: rgba(0, 120, 212, 0.1); border-radius: 6px;")
            self._clear_fields()
            return

        if info.is_valid:
            self.lbl_status_icon.setText("✔")
            self.lbl_status_text.setText("Chave Válida! O Dígito Verificador Módulo 11 foi validado com sucesso.")
            self.frame_status.setStyleSheet("background-color: rgba(16, 124, 65, 0.15); color: #107C41; border-radius: 6px;")
        else:
            self.lbl_status_icon.setText("✖")
            self.lbl_status_text.setText(f"Atenção: {info.erro_mensagem}")
            self.frame_status.setStyleSheet("background-color: rgba(216, 59, 1, 0.15); color: #D83B01; border-radius: 6px;")

        self.lbl_uf.setText(f"{info.uf_codigo} - {info.uf_nome}" if info.uf_codigo else "-")
        self.lbl_data.setText(info.data_emissao_formatada or "-")
        self.lbl_cnpj.setText(info.cnpj_formatado or "-")
        self.lbl_modelo.setText(f"{info.modelo_codigo} - {info.modelo_nome}" if info.modelo_codigo else "-")
        self.lbl_serie_num.setText(f"Série {info.serie} | Nº {info.numero_nota:,}".replace(",", ".") if info.numero_nota else "-")
        self.lbl_tipo_emissao.setText(info.tipo_emissao_nome or "-")
        self.lbl_cnf_cdv.setText(f"cNF: {info.codigo_numerico} | cDV: {info.digito_verificador}" if info.codigo_numerico else "-")

        self.edit_formatted.setText(format_nfe_key(info.raw_key))

    def _clear_fields(self) -> None:
        self.lbl_uf.setText("-")
        self.lbl_data.setText("-")
        self.lbl_cnpj.setText("-")
        self.lbl_modelo.setText("-")
        self.lbl_serie_num.setText("-")
        self.lbl_tipo_emissao.setText("-")
        self.lbl_cnf_cdv.setText("-")
        self.edit_formatted.clear()

    def _copy_key(self) -> None:
        txt = self.edit_formatted.text()
        if txt:
            cb = QApplication.clipboard()
            if cb:
                cb.setText(txt)
