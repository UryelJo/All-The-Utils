"""
Lógica pura para geração e verificação de códigos de autenticação de mensagem em hash (HMAC).

Suporta:
- Algoritmos de digest: SHA-256, SHA-512, SHA-384, SHA-224, SHA-1, MD5, SHA3-256, SHA3-512
- Chaves secretas em texto UTF-8 ou bytes decodificados de Hexadecimal
- Saída em Hexadecimal (minúsculo ou maiúsculo) e Base64
- Validação constante no tempo (hmac.compare_digest) resistente a timing attacks
- Geração de chaves secretas aleatórias criptograficamente seguras (secrets)

Isolado de qualquer biblioteca de interface gráfica.
"""
import base64
import hashlib
import hmac
import secrets
from typing import Dict, Optional, Tuple


SUPPORTED_ALGORITHMS: Dict[str, str] = {
    "sha256": "SHA-256",
    "sha512": "SHA-512",
    "sha384": "SHA-384",
    "sha224": "SHA-224",
    "sha1": "SHA-1",
    "md5": "MD5",
    "sha3_256": "SHA3-256",
    "sha3_512": "SHA3-512",
}


def generate_random_secret(length_bytes: int = 32, as_hex: bool = False) -> str:
    """Gera uma chave secreta criptograficamente segura."""
    token_bytes = secrets.token_bytes(length_bytes)
    return token_bytes.hex() if as_hex else base64.b64encode(token_bytes).decode("ascii")


def _prepare_key(key: str | bytes, key_is_hex: bool) -> bytes:
    """Converte chave em bytes apropriados, tratando hexadecimal quando especificado."""
    if isinstance(key, bytes):
        return key
    if key_is_hex:
        clean_hex = "".join(key.split())
        if len(clean_hex) % 2 != 0:
            clean_hex = "0" + clean_hex
        return bytes.fromhex(clean_hex)
    return key.encode("utf-8")


def _prepare_message(message: str | bytes) -> bytes:
    """Garante que a mensagem seja uma sequência de bytes."""
    if isinstance(message, bytes):
        return message
    return message.encode("utf-8")


def compute_hmac(
    message: str | bytes,
    secret_key: str | bytes,
    algorithm: str = "sha256",
    key_is_hex: bool = False,
    output_format: str = "hex"  # "hex", "hex_upper", "base64"
) -> str:
    """
    Calcula o HMAC da mensagem com a chave e algoritmo especificados.
    """
    algo_clean = algorithm.lower().replace("-", "_")
    if not hasattr(hashlib, algo_clean):
        raise ValueError(f"Algoritmo de hash não suportado: '{algorithm}'.")

    digest_mod = getattr(hashlib, algo_clean)
    k_bytes = _prepare_key(secret_key, key_is_hex)
    m_bytes = _prepare_message(message)

    h = hmac.new(k_bytes, m_bytes, digest_mod)
    raw_digest = h.digest()

    if output_format == "hex_upper":
        return h.hexdigest().upper()
    elif output_format == "base64":
        return base64.b64encode(raw_digest).decode("ascii")
    else:
        return h.hexdigest().lower()


def verify_hmac(
    message: str | bytes,
    secret_key: str | bytes,
    expected_hmac: str,
    algorithm: str = "sha256",
    key_is_hex: bool = False
) -> bool:
    """
    Verifica se o HMAC fornecido coincide de forma segura (tempo constante).
    Aceita expected_hmac em Hexadecimal ou Base64.
    """
    clean_expected = expected_hmac.strip()
    if not clean_expected:
        return False

    algo_clean = algorithm.lower().replace("-", "_")
    if not hasattr(hashlib, algo_clean):
        return False

    digest_mod = getattr(hashlib, algo_clean)
    k_bytes = _prepare_key(secret_key, key_is_hex)
    m_bytes = _prepare_message(message)
    actual_digest = hmac.new(k_bytes, m_bytes, digest_mod).digest()

    # Tenta comparação em formato hexadecimal
    actual_hex = actual_digest.hex()
    if hmac.compare_digest(actual_hex.lower(), clean_expected.lower()):
        return True

    # Tenta comparação em formato Base64
    actual_b64 = base64.b64encode(actual_digest).decode("ascii")
    if hmac.compare_digest(actual_b64, clean_expected):
        return True

    return False
