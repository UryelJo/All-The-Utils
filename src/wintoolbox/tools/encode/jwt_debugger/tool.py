"""
Interface gráfica do Depurador e Verificador de JWT (JSON Web Tokens).
Permite depuração visual com separação de cabeçalho, claims/payload,
análise de expiração RFC 7519 e verificação criptográfica de assinatura HMAC.
"""
import json
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.registry import Tool, register
from wintoolbox.tools.encode.jwt_debugger.logic import (
    create_signed_jwt,
    decode_jwt_sections,
    verify_hmac_signature,
)


@register
class JwtDebuggerTool(Tool):
    id = "encode.jwt_debugger"
    name = "Depurador e Verificador de JWT"
    category = "Codificação e Hash"
    description = (
        "Depura e valida tokens JWT, inspeciona claims temporais (exp/nbf/iat) e "
        "verifica assinaturas criptográficas HMAC (HS256/384/512)."
    )
    keywords = ["jwt", "token", "debugger", "hmac", "sha256", "claims", "bearer", "assinatura"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return JwtDebuggerView(self, parent)


class JwtDebuggerView(QWidget):
    def __init__(self, tool: JwtDebuggerTool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.tool = tool
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Cabeçalho
        lbl_title = QLabel(self.tool.name)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1f2937;")
        root_layout.addWidget(lbl_title)

        lbl_desc = QLabel(self.tool.description)
        lbl_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        root_layout.addWidget(lbl_desc)

        # Splitter Principal: Esquerda (Entrada do Token), Direita (Decodificação e Verificação)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Painel Esquerdo: Entrada
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        lbl_in = QLabel("Token JWT Codificado:")
        lbl_in.setStyleSheet("font-weight: bold; color: #374151;")
        left_layout.addWidget(lbl_in)

        self._txt_token = QPlainTextEdit()
        self._txt_token.setFont(QFont("Consolas", 9))
        self._txt_token.setPlaceholderText("Cole seu token JWT aqui (ex: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...)")
        self._txt_token.textChanged.connect(self._on_token_changed)
        left_layout.addWidget(self._txt_token)

        # Botão para gerar token de exemplo
        btn_sample = QPushButton("Carregar Token de Demonstração")
        btn_sample.clicked.connect(self._load_demo_token)
        left_layout.addWidget(btn_sample)

        splitter.addWidget(left_widget)

        # Painel Direito: Conteúdo Decodificado
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)

        right_content = QWidget()
        right_layout = QVBoxLayout(right_content)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Seção Header
        group_header = QGroupBox("Cabeçalho (Header)")
        group_header.setStyleSheet("QGroupBox { font-weight: bold; color: #b91c1c; }")
        gh_layout = QVBoxLayout(group_header)
        self._txt_header = QPlainTextEdit()
        self._txt_header.setReadOnly(True)
        self._txt_header.setFont(QFont("Consolas", 9))
        self._txt_header.setMaximumHeight(110)
        gh_layout.addWidget(self._txt_header)
        right_layout.addWidget(group_header)

        # Seção Payload
        group_payload = QGroupBox("Carga Útil / Dados (Payload / Claims)")
        group_payload.setStyleSheet("QGroupBox { font-weight: bold; color: #6d28d9; }")
        gp_layout = QVBoxLayout(group_payload)
        self._txt_payload = QPlainTextEdit()
        self._txt_payload.setReadOnly(True)
        self._txt_payload.setFont(QFont("Consolas", 9))
        self._txt_payload.setMinimumHeight(140)
        gp_layout.addWidget(self._txt_payload)

        # Status de Validade Temporal
        self._lbl_time_info = QLabel("Status de Validade: Nenhum token carregado")
        self._lbl_time_info.setStyleSheet("color: #4b5563; font-size: 11px;")
        gp_layout.addWidget(self._lbl_time_info)
        right_layout.addWidget(group_payload)

        # Seção Verificação de Assinatura
        group_sig = QGroupBox("Verificação Criptográfica de Assinatura")
        group_sig.setStyleSheet("QGroupBox { font-weight: bold; color: #047857; }")
        gs_layout = QVBoxLayout(group_sig)

        sec_layout = QHBoxLayout()
        lbl_sec = QLabel("Chave Secreta (Secret):")
        sec_layout.addWidget(lbl_sec)
        self._txt_secret = QLineEdit()
        self._txt_secret.setPlaceholderText("Digite o segredo HMAC para verificar a assinatura...")
        self._txt_secret.textChanged.connect(self._verify_signature)
        sec_layout.addWidget(self._txt_secret)

        self._chk_b64_secret = QCheckBox("Segredo em Base64")
        self._chk_b64_secret.toggled.connect(self._verify_signature)
        sec_layout.addWidget(self._chk_b64_secret)
        gs_layout.addLayout(sec_layout)

        self._lbl_sig_badge = QLabel("Aguardando verificação")
        self._lbl_sig_badge.setStyleSheet(
            "padding: 6px; border-radius: 4px; background: #f3f4f6; color: #4b5563; font-weight: bold;"
        )
        gs_layout.addWidget(self._lbl_sig_badge)

        right_layout.addWidget(group_sig)
        right_layout.addStretch()

        right_scroll.setWidget(right_content)
        splitter.addWidget(right_scroll)
        splitter.setSizes([320, 480])

        root_layout.addWidget(splitter)

    def _on_token_changed(self):
        raw = self._txt_token.toPlainText().strip()
        if not raw:
            self._txt_header.clear()
            self._txt_payload.clear()
            self._lbl_time_info.setText("Status de Validade: Nenhum token carregado")
            self._lbl_sig_badge.setText("Aguardando token")
            self._lbl_sig_badge.setStyleSheet("background: #f3f4f6; color: #4b5563; padding: 6px; font-weight: bold;")
            return

        try:
            res = decode_jwt_sections(raw)
            self._txt_header.setPlainText(json.dumps(res["header"], indent=2))
            self._txt_payload.setPlainText(json.dumps(res["payload"], indent=2))

            time_st = res["time_status"]
            summary = time_st.get("summary", "")
            exp_fmt = time_st.get("exp_formatted")
            if exp_fmt:
                summary += f" (Expira em: {exp_fmt})"
            self._lbl_time_info.setText(f"Status Temporal: {summary}")

            # Reavalia assinatura se já houver segredo
            self._verify_signature()
        except Exception as exc:
            self._txt_header.setPlainText(f"Erro ao analisar: {exc}")
            self._txt_payload.clear()
            self._lbl_sig_badge.setText("Formato Inválido")
            self._lbl_sig_badge.setStyleSheet("background: #fee2e2; color: #b91c1c; padding: 6px; font-weight: bold;")

    def _verify_signature(self):
        raw = self._txt_token.toPlainText().strip()
        secret = self._txt_secret.text()

        if not raw or "." not in raw:
            return

        if not secret:
            self._lbl_sig_badge.setText("Insira a chave secreta para validar a assinatura")
            self._lbl_sig_badge.setStyleSheet("background: #fef3c7; color: #92400e; padding: 6px; font-weight: bold;")
            return

        is_b64 = self._chk_b64_secret.isChecked()
        res = verify_hmac_signature(raw, secret, is_secret_base64=is_b64)

        if res["valid"]:
            self._lbl_sig_badge.setText(f"Assinatura VÁLIDA ({res['algorithm']})")
            self._lbl_sig_badge.setStyleSheet(
                "background: #d1fae5; color: #065f46; border: 1px solid #10b981; padding: 6px; font-weight: bold;"
            )
        else:
            err = res.get("error", "Assinatura inválida")
            self._lbl_sig_badge.setText(f"Assinatura INVÁLIDA: {err}")
            self._lbl_sig_badge.setStyleSheet(
                "background: #fee2e2; color: #991b1b; border: 1px solid #ef4444; padding: 6px; font-weight: bold;"
            )

    def _load_demo_token(self):
        # Gera um token demonstrativo assinado com chave "segredo123"
        demo_payload = {
            "sub": "usuario_12345",
            "name": "Administrador WinToolbox",
            "role": "admin",
            "iat": 1700000000,
            "exp": 1900000000,
        }
        token = create_signed_jwt(demo_payload, "segredo123", algorithm="HS256")
        self._txt_token.setPlainText(token)
        self._txt_secret.setText("segredo123")
