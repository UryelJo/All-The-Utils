"""
Lógica pura da ferramenta Inspetor e Decodificador de Tokens JWT (JSON Web Tokens).
Sem dependência de UI.
"""
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from typing import Any, Dict, Optional, Tuple


@dataclass
class JwtExpirationInfo:
    has_expiration: bool
    is_expired: bool
    status_text: str
    detail_text: str
    status_type: str  # 'valid', 'expired', 'none'


def decode_jwt_unverified(jwt_token: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
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


def parse_jwt_expiration(payload: Dict[str, Any]) -> JwtExpirationInfo:
    """Verifica e formata o tempo de vida/expiração contido na claim 'exp'."""
    if "exp" not in payload or not isinstance(payload["exp"], (int, float)):
        return JwtExpirationInfo(
            has_expiration=False,
            is_expired=False,
            status_text="[SEM EXPIRAÇÃO] O token não define claim 'exp'.",
            detail_text="Este token não possui tempo limite de vida definido.",
            status_type="none",
        )

    exp_ts = payload["exp"]
    now_ts = time.time()
    exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc).astimezone()
    dt_str = exp_dt.strftime("%d/%m/%Y às %H:%M:%S (%Z)")

    if now_ts > exp_ts:
        diff_mins = int((now_ts - exp_ts) / 60)
        return JwtExpirationInfo(
            has_expiration=True,
            is_expired=True,
            status_text="[EXPIRADO] Este token já perdeu a validade!",
            detail_text=f"Expirou em: {dt_str} (há aproximadamente {diff_mins} minutos)",
            status_type="expired",
        )
    else:
        diff_mins = int((exp_ts - now_ts) / 60)
        return JwtExpirationInfo(
            has_expiration=True,
            is_expired=False,
            status_text="[VÁLIDO] O token está ativo dentro do período de validade.",
            detail_text=f"Expira em: {dt_str} (restam aproximadamente {diff_mins} minutos)",
            status_type="valid",
        )
