"""
Lógica pura para o Depurador e Verificador Criptográfico de JWT (JSON Web Tokens).
Implementa especificação RFC 7519, verificação e assinatura HMAC (HS256, HS384, HS512),
cálculo de validade temporal (iat, nbf, exp) e parsing seguro.

Zero dependências de interface gráfica.
"""
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


def _b64url_decode(payload: str) -> bytes:
    """Decodifica Base64 URL-safe adicionando o padding necessário."""
    rem = len(payload) % 4
    if rem > 0:
        payload += "=" * (4 - rem)
    return base64.urlsafe_b64decode(payload)


def _b64url_encode(data: bytes) -> str:
    """Codifica bytes em Base64 URL-safe sem padding."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def split_jwt(token: str) -> Tuple[str, str, str]:
    """
    Divide o token JWT em suas 3 partes: header, payload e signature.
    Lança ValueError se a estrutura for inválida.
    """
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError(f"Formato JWT inválido: esperadas 3 partes separadas por ponto, recebidas {len(parts)}.")
    return parts[0], parts[1], parts[2]


def decode_jwt_sections(token: str) -> Dict[str, Any]:
    """
    Decodifica as partes do JWT sem verificar a assinatura.
    Retorna os dicionários de Header, Payload e metadados de tempo.
    """
    header_b64, payload_b64, signature_b64 = split_jwt(token)

    try:
        header_bytes = _b64url_decode(header_b64)
        header_data = json.loads(header_bytes.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Falha ao decodificar Header do JWT: {exc}") from exc

    try:
        payload_bytes = _b64url_decode(payload_b64)
        payload_data = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Falha ao decodificar Payload do JWT: {exc}") from exc

    # Análise temporal das claims padrão RFC 7519
    now = int(time.time())
    time_analysis = _analyze_time_claims(payload_data, now)

    return {
        "header": header_data,
        "payload": payload_data,
        "signature_b64": signature_b64,
        "algorithm": header_data.get("alg", "none"),
        "time_status": time_analysis,
    }


def _analyze_time_claims(payload: Dict[str, Any], current_timestamp: int) -> Dict[str, Any]:
    """
    Analisa as claims 'iat' (emitido em), 'nbf' (não antes de) e 'exp' (expiração).
    """
    res: Dict[str, Any] = {
        "is_expired": False,
        "is_not_yet_valid": False,
        "exp_formatted": None,
        "iat_formatted": None,
        "nbf_formatted": None,
        "summary": "Sem dados de expiração",
    }

    if "exp" in payload and isinstance(payload["exp"], (int, float)):
        exp_ts = int(payload["exp"])
        exp_dt = datetime.fromtimestamp(exp_ts, timezone.utc)
        res["exp_formatted"] = exp_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        if current_timestamp > exp_ts:
            res["is_expired"] = True
            diff = current_timestamp - exp_ts
            res["summary"] = f"Expirado há {diff} segundos"
        else:
            diff = exp_ts - current_timestamp
            res["summary"] = f"Válido por mais {diff} segundos"

    if "nbf" in payload and isinstance(payload["nbf"], (int, float)):
        nbf_ts = int(payload["nbf"])
        nbf_dt = datetime.fromtimestamp(nbf_ts, timezone.utc)
        res["nbf_formatted"] = nbf_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        if current_timestamp < nbf_ts:
            res["is_not_yet_valid"] = True
            diff = nbf_ts - current_timestamp
            res["summary"] = f"Ainda não é válido (ativo em {diff}s)"

    if "iat" in payload and isinstance(payload["iat"], (int, float)):
        iat_ts = int(payload["iat"])
        iat_dt = datetime.fromtimestamp(iat_ts, timezone.utc)
        res["iat_formatted"] = iat_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    return res


HMAC_HASH_MAP = {
    "HS256": hashlib.sha256,
    "HS384": hashlib.sha384,
    "HS512": hashlib.sha512,
}


def verify_hmac_signature(
    token: str, secret: str, is_secret_base64: bool = False
) -> Dict[str, Any]:
    """
    Verifica a assinatura criptográfica de um token JWT para algoritmos HMAC (HS256/384/512).
    """
    header_b64, payload_b64, signature_b64 = split_jwt(token)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    try:
        header_bytes = _b64url_decode(header_b64)
        header_data = json.loads(header_bytes.decode("utf-8"))
    except Exception as exc:
        return {"valid": False, "error": f"Header inválido: {exc}"}

    alg = header_data.get("alg")
    if alg not in HMAC_HASH_MAP:
        return {
            "valid": False,
            "error": f"Algoritmo '{alg}' não é suportado para verificação HMAC (esperado HS256, HS384 ou HS512).",
        }

    hash_func = HMAC_HASH_MAP[alg]

    try:
        if is_secret_base64:
            secret_bytes = base64.b64decode(secret)
        else:
            secret_bytes = secret.encode("utf-8")
    except Exception as exc:
        return {"valid": False, "error": f"Falha ao decodificar segredo em Base64: {exc}"}

    computed_digest = hmac.new(secret_bytes, signing_input, hash_func).digest()
    computed_sig_b64 = _b64url_encode(computed_digest)

    is_valid = hmac.compare_digest(computed_sig_b64, signature_b64)
    return {
        "valid": is_valid,
        "algorithm": alg,
        "computed_signature": computed_sig_b64,
        "received_signature": signature_b64,
        "error": None if is_valid else "Assinatura HMAC não confere com o segredo informado.",
    }


def create_signed_jwt(
    payload: Dict[str, Any],
    secret: str,
    algorithm: str = "HS256",
    custom_header: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Cria e assina um novo token JWT HMAC.
    Útil para testes, depuração e simulação.
    """
    if algorithm not in HMAC_HASH_MAP:
        raise ValueError(f"Algoritmo não suportado: {algorithm}")

    header = {"typ": "JWT", "alg": algorithm}
    if custom_header:
        header.update(custom_header)

    header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    header_b64 = _b64url_encode(header_json)
    payload_b64 = _b64url_encode(payload_json)

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    secret_bytes = secret.encode("utf-8")
    hash_func = HMAC_HASH_MAP[algorithm]

    digest = hmac.new(secret_bytes, signing_input, hash_func).digest()
    sig_b64 = _b64url_encode(digest)

    return f"{header_b64}.{payload_b64}.{sig_b64}"
