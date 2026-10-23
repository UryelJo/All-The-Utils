"""
Ferramenta: Inspetor e Decodificador de Tokens JWT (JSON Web Tokens).
Permite visualizar cabeçalhos, claims, status de expiração e datas formatadas.
"""
import base64
import json
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from wintoolbox.core.registry import Tool, register

def decode_jwt_unverified(jwt_token: str) -> Tuple[Dict, Dict, str]:
    """Decodifica as partes do token JWT sem verificação criptográfica da assinatura."""
    parts = jwt_token.strip().split(".")
    if len(parts) < 2:
        raise ValueError("O token JWT deve conter pelo menos duas partes separadas por ponto (Header.Payload).")

    def b64_decode(data: str) -> str:
        data = data.replace("-", "+").replace("_", "/")
        missing = len(data) % 4
        if missing:
            data += "=" * (4 - missing)
        return base64.b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")

    header_json = b64_decode(parts[0])
    payload_json = b64_decode(parts[1])
    signature = parts[2] if len(parts) > 2 else ""

    header = json.loads(header_json)
    payload = json.loads(payload_json)

    return header, payload, signature

@register
class JwtDecoderTool(Tool):
    id = "encode.jwt"
    name = "Inspetor e Decodificador de JWT"
    category = "Codificação e Hash"
    description = "Decodifica tokens JWT inspecionando cabeçalho, claims e datas de validade"
    keywords = ["jwt", "token", "auth", "bearer", "claims", "decodificar", "expiracao"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return JwtDecoderView(self, parent)

class JwtDecoderView(QWidget):
    def __init__(self, tool: JwtDecoderTool, parent: Optional[QWidget] = None):
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

        # Entrada do Token JWT
        col_in = QVBoxLayout()
        col_in.addWidget(QLabel("Token JWT Codificado:"))
        self.txt_jwt_in = QPlainTextEdit()
        self.txt_jwt_in.setPlaceholderText("Cole o token JWT (ex: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...) aqui...")
        self.txt_jwt_in.setFixedHeight(90)
        self.txt_jwt_in.textChanged.connect(self._decode_token)
        col_in.addWidget(self.txt_jwt_in)
        layout.addLayout(col_in)

        # Status do Token
        card_status = QFrame()
        card_status.setProperty("class", "card")
        l_stat = QVBoxLayout(card_status)
        l_stat.setSpacing(6)

        self.lbl_exp_status = QLabel("Aguardando token...")
        self.lbl_exp_status.setStyleSheet("font-size: 14px; font-weight: 600;")
        l_stat.addWidget(self.lbl_exp_status)

        self.lbl_exp_human = QLabel("")
        self.lbl_exp_human.setProperty("class", "secondary")
        l_stat.addWidget(self.lbl_exp_human)
        layout.addWidget(card_status)

        # Saídas (Header e Payload)
        col_views = QHBoxLayout()
        col_views.setSpacing(12)

        # Lado 1: Cabeçalho (Header)
        col_h = QVBoxLayout()
        col_h.addWidget(QLabel("Cabeçalho (Header / Algoritmo):"))
        self.txt_header = QPlainTextEdit()
        self.txt_header.setReadOnly(True)
        self.txt_header.setFixedHeight(220)
        col_h.addWidget(self.txt_header)
        col_views.addLayout(col_h, stretch=1)

        # Lado 2: Payload (Claims)
        col_p = QVBoxLayout()
        col_p.addWidget(QLabel("Carga Útil (Payload / Claims):"))
        self.txt_payload = QPlainTextEdit()
        self.txt_payload.setReadOnly(True)
        self.txt_payload.setFixedHeight(220)
        col_p.addWidget(self.txt_payload)
        col_views.addLayout(col_p, stretch=2)

        layout.addLayout(col_views)
        layout.addStretch()

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    def _decode_token(self):
        token = self.txt_jwt_in.toPlainText().strip()
        if not token:
            self.lbl_exp_status.setText("Aguardando token...")
            self.lbl_exp_status.setStyleSheet("font-size: 14px; font-weight: 600; color: #aaa;")
            self.lbl_exp_human.setText("")
            self.txt_header.clear()
            self.txt_payload.clear()
            return

        try:
            header, payload, sig = decode_jwt_unverified(token)
            self.txt_header.setPlainText(json.dumps(header, indent=2, ensure_ascii=False))
            self.txt_payload.setPlainText(json.dumps(payload, indent=2, ensure_ascii=False))

            # Analisa data de expiração
            if "exp" in payload and isinstance(payload["exp"], (int, float)):
                exp_ts = payload["exp"]
                now_ts = time.time()
                exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc).astimezone()
                dt_str = exp_dt.strftime("%d/%m/%Y às %H:%M:%S (%Z)")

                if now_ts > exp_ts:
                    diff_mins = int((now_ts - exp_ts) / 60)
                    self.lbl_exp_status.setText("[EXPIRADO] Este token já perdeu a validade!")
                    self.lbl_exp_status.setStyleSheet("font-size: 14px; font-weight: 600; color: #ffa198;")
                    self.lbl_exp_human.setText(f"Expirou em: {dt_str} (há aproximadamente {diff_mins} minutos)")
                else:
                    diff_mins = int((exp_ts - now_ts) / 60)
                    self.lbl_exp_status.setText("[VÁLIDO] O token está ativo dentro do período de validade.")
                    self.lbl_exp_status.setStyleSheet("font-size: 14px; font-weight: 600; color: #7ee787;")
                    self.lbl_exp_human.setText(f"Expira em: {dt_str} (restam aproximadamente {diff_mins} minutos)")
            else:
                self.lbl_exp_status.setText("[SEM EXPIRAÇÃO] O token não define claim 'exp'.")
                self.lbl_exp_status.setStyleSheet("font-size: 14px; font-weight: 600; color: #e3b341;")
                self.lbl_exp_human.setText("Este token não possui tempo limite de vida definido.")

        except Exception as e:
            self.lbl_exp_status.setText("[TOKEN INVÁLIDO] Não foi possível decodificar.")
            self.lbl_exp_status.setStyleSheet("font-size: 14px; font-weight: 600; color: #ffa198;")
            self.lbl_exp_human.setText(str(e))
            self.txt_header.clear()
            self.txt_payload.clear()
