"""
Interface gráfica Fluent da ferramenta Gerador e Validador de HMAC.
"""
from PySide6.QtCore import Qt, QTimer
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
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.encode.hmac.logic import (
    compute_hmac,
    generate_random_secret,
    verify_hmac,
    SUPPORTED_ALGORITHMS,
)


@register
class HMACTool(Tool):
    """Ferramenta para cálculo e verificação de códigos de autenticação de mensagens (HMAC)."""
    id = "encode.hmac"
    title = "Gerador e Validador HMAC"
    category = "Codificação e Hash"
    description = (
        "Calcula e valida assinaturas de autenticação em hash (HMAC) com SHA-256, SHA-512, MD5 "
        "e SHA-1 a partir de chaves em texto ou hexadecimal, ideal para webhooks e segurança de APIs."
    )
    icon = "Shield"

    def __init__(self) -> None:
        super().__init__()
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._on_compute)

    def build_view(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho
        header = QLabel("Gerador e Verificador de Assinaturas HMAC")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        desc = QLabel(
            "Gere códigos de autenticação de mensagem em hash (HMAC) para validar webhooks "
            "(GitHub, Stripe, Mercado Pago, AWS) e compare assinaturas com segurança constante no tempo."
        )
        desc.setStyleSheet("color: gray;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Configurações de Algoritmo e Chave
        opt_frame = QFrame()
        opt_frame.setFrameShape(QFrame.Shape.StyledPanel)
        opt_layout = QHBoxLayout(opt_frame)
        opt_layout.setContentsMargins(10, 10, 10, 10)
        opt_layout.setSpacing(14)

        opt_layout.addWidget(QLabel("Algoritmo:"))
        self.combo_algo = QComboBox()
        for k, v in SUPPORTED_ALGORITHMS.items():
            self.combo_algo.addItem(v, k)
        self.combo_algo.currentIndexChanged.connect(self._on_compute)
        opt_layout.addWidget(self.combo_algo)

        opt_layout.addWidget(QLabel("Formato de Saída:"))
        self.combo_format = QComboBox()
        self.combo_format.addItem("Hexadecimal (minúsculo)", "hex")
        self.combo_format.addItem("Hexadecimal (MAIÚSCULO)", "hex_upper")
        self.combo_format.addItem("Base64", "base64")
        self.combo_format.currentIndexChanged.connect(self._on_compute)
        opt_layout.addWidget(self.combo_format)

        self.chk_key_hex = QCheckBox("Chave secreta é Hexadecimal")
        self.chk_key_hex.toggled.connect(self._on_compute)
        opt_layout.addWidget(self.chk_key_hex)

        opt_layout.addStretch()
        layout.addWidget(opt_frame)

        # Chave Secreta
        grp_key = QGroupBox("Chave Secreta (Secret Key)")
        v_key = QVBoxLayout(grp_key)
        v_key.setSpacing(8)

        row_key = QHBoxLayout()
        self.edit_key = QLineEdit()
        self.edit_key.setPlaceholderText("Digite ou gere a chave secreta compartilhada...")
        self.edit_key.setEchoMode(QLineEdit.EchoMode.Normal)
        self.edit_key.textChanged.connect(self._trigger_debounce)
        row_key.addWidget(self.edit_key, 1)

        btn_toggle_echo = QPushButton("Ocultar")
        btn_toggle_echo.clicked.connect(lambda: self._toggle_key_echo(btn_toggle_echo))
        row_key.addWidget(btn_toggle_echo)

        btn_gen_key = QPushButton("Gerar Chave Aleatória")
        btn_gen_key.clicked.connect(self._generate_key)
        row_key.addWidget(btn_gen_key)
        v_key.addLayout(row_key)
        layout.addWidget(grp_key)

        # Mensagem / Payload
        grp_msg = QGroupBox("Mensagem / Payload para Assinatura")
        v_msg = QVBoxLayout(grp_msg)
        self.edit_msg = QTextEdit()
        self.edit_msg.setPlaceholderText("Cole o payload JSON, texto ou dados da requisição...")
        self.edit_msg.textChanged.connect(self._trigger_debounce)
        v_msg.addWidget(self.edit_msg)
        layout.addWidget(grp_msg)

        # Resultado do HMAC Gerado
        grp_res = QGroupBox("HMAC Calculado")
        v_res = QVBoxLayout(grp_res)
        row_res = QHBoxLayout()

        self.edit_res = QLineEdit()
        self.edit_res.setReadOnly(True)
        self.edit_res.setStyleSheet("font-family: Consolas, monospace; font-size: 14px; font-weight: bold;")
        row_res.addWidget(self.edit_res, 1)

        btn_copy = QPushButton("Copiar HMAC")
        btn_copy.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        btn_copy.clicked.connect(self._copy_hmac)
        row_res.addWidget(btn_copy)
        v_res.addLayout(row_res)
        layout.addWidget(grp_res)

        # Seção de Verificação / Comparação
        grp_verify = QGroupBox("Verificação de Assinatura (Conferir Webhook)")
        v_ver = QVBoxLayout(grp_verify)
        v_ver.setSpacing(8)

        row_ver = QHBoxLayout()
        self.edit_expected = QLineEdit()
        self.edit_expected.setPlaceholderText("Cole a assinatura esperada (ex: header X-Hub-Signature ou similar) para verificar...")
        self.edit_expected.textChanged.connect(self._on_verify_check)
        row_ver.addWidget(self.edit_expected, 1)

        self.lbl_verify_status = QLabel("Aguardando assinatura...")
        self.lbl_verify_status.setStyleSheet("font-weight: bold; padding: 4px 8px; border-radius: 4px;")
        row_ver.addWidget(self.lbl_verify_status)
        v_ver.addLayout(row_ver)
        layout.addWidget(grp_verify)

        # Iniciar com chave e mensagem exemplo
        self.edit_key.setText("minha_chave_secreta_super_segura")
        self.edit_msg.setPlainText('{"event": "payment.succeeded", "amount": 15000}')
        self._on_compute()

        return container

    def _trigger_debounce(self) -> None:
        self._debounce_timer.start()

    def _toggle_key_echo(self, btn: QPushButton) -> None:
        if self.edit_key.echoMode() == QLineEdit.EchoMode.Normal:
            self.edit_key.setEchoMode(QLineEdit.EchoMode.Password)
            btn.setText("Exibir")
        else:
            self.edit_key.setEchoMode(QLineEdit.EchoMode.Normal)
            btn.setText("Ocultar")

    def _generate_key(self) -> None:
        is_hex = self.chk_key_hex.isChecked()
        new_key = generate_random_secret(32, as_hex=is_hex)
        self.edit_key.setText(new_key)
        self._on_compute()

    def _on_compute(self) -> None:
        msg = self.edit_msg.toPlainText()
        key = self.edit_key.text()
        algo = self.combo_algo.currentData()
        fmt = self.combo_format.currentData()
        is_hex = self.chk_key_hex.isChecked()

        if not key:
            self.edit_res.setText("")
            self._on_verify_check()
            return

        try:
            res = compute_hmac(
                message=msg,
                secret_key=key,
                algorithm=algo,
                key_is_hex=is_hex,
                output_format=fmt,
            )
            self.edit_res.setText(res)
        except Exception as e:
            self.edit_res.setText(f"Erro: {e}")

        self._on_verify_check()

    def _on_verify_check(self) -> None:
        expected = self.edit_expected.text().strip()
        if not expected:
            self.lbl_verify_status.setText("Aguardando assinatura...")
            self.lbl_verify_status.setStyleSheet("color: gray;")
            return

        msg = self.edit_msg.toPlainText()
        key = self.edit_key.text()
        algo = self.combo_algo.currentData()
        is_hex = self.chk_key_hex.isChecked()

        # Remove prefixo comum como "sha256=" de webhooks
        if "=" in expected:
            expected = expected.split("=", 1)[1].strip()

        matched = verify_hmac(
            message=msg,
            secret_key=key,
            expected_hmac=expected,
            algorithm=algo,
            key_is_hex=is_hex,
        )

        if matched:
            self.lbl_verify_status.setText("✔ VÁLIDA: Assinatura Autêntica!")
            self.lbl_verify_status.setStyleSheet("color: white; background-color: #107C41; font-weight: bold;")
        else:
            self.lbl_verify_status.setText("✖ INVÁLIDA: Assinatura Não Confere!")
            self.lbl_verify_status.setStyleSheet("color: white; background-color: #D83B01; font-weight: bold;")

    def _copy_hmac(self) -> None:
        txt = self.edit_res.text()
        if txt:
            cb = QApplication.clipboard()
            if cb:
                cb.setText(txt)
