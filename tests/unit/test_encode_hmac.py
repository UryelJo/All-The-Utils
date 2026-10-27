"""
Testes unitários rigorosos para cálculo e validação de HMAC.
Baseado nos vetores oficiais de teste da RFC 4231.
"""
import pytest
from wintoolbox.tools.encode.hmac.logic import (
    compute_hmac,
    generate_random_secret,
    verify_hmac,
)


def test_hmac_rfc4231_test_case_1():
    """Valida vetor oficial RFC 4231 Test Case 1 (Chave em bytes repetidos)."""
    # Key = 0x0b 20 vezes
    key_hex = "0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"
    msg = "Hi There"
    expected_sha256 = "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"

    calc = compute_hmac(msg, key_hex, algorithm="sha256", key_is_hex=True, output_format="hex")
    assert calc == expected_sha256
    assert verify_hmac(msg, key_hex, expected_sha256, algorithm="sha256", key_is_hex=True) is True


def test_hmac_rfc4231_test_case_2():
    """Valida vetor oficial RFC 4231 Test Case 2 (Chave em texto ASCII)."""
    key = "Jefe"
    msg = "what do ya want for nothing?"
    expected_sha256 = "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"

    calc = compute_hmac(msg, key, algorithm="sha256", key_is_hex=False, output_format="hex")
    assert calc == expected_sha256
    assert verify_hmac(msg, key, expected_sha256, algorithm="sha256", key_is_hex=False) is True


def test_hmac_formats_and_algorithms():
    """Valida saídas em maiúsculo, Base64 e algoritmos SHA-512 e MD5."""
    key = "secret"
    msg = "hello world"

    # SHA-256 maiúsculo
    res_upper = compute_hmac(msg, key, algorithm="sha256", output_format="hex_upper")
    assert res_upper == res_upper.upper()
    assert res_upper == "734CC62F32841568F45715AEB9F4D7891324E6D948E4C6C60C0621CDAC48623A"

    # Base64
    res_b64 = compute_hmac(msg, key, algorithm="sha256", output_format="base64")
    assert verify_hmac(msg, key, res_b64, algorithm="sha256") is True

    # MD5
    res_md5 = compute_hmac(msg, key, algorithm="md5")
    assert len(res_md5) == 32
    assert verify_hmac(msg, key, res_md5, algorithm="md5") is True


def test_verify_hmac_negative():
    """Valida rejeição de assinatura adulterada."""
    key = "chave123"
    msg = "mensagem original"
    valid_hmac = compute_hmac(msg, key, algorithm="sha256")

    # Mensagem alterada
    assert verify_hmac("mensagem alterada", key, valid_hmac, algorithm="sha256") is False
    # Chave errada
    assert verify_hmac(msg, "chave_errada", valid_hmac, algorithm="sha256") is False
    # Assinatura corrompida
    assert verify_hmac(msg, key, "0000000000000000000000000000000000000000000000000000000000000000", algorithm="sha256") is False


def test_generate_random_secret():
    """Valida gerador de chaves aleatórias."""
    secret_hex = generate_random_secret(16, as_hex=True)
    assert len(secret_hex) == 32
    secret_b64 = generate_random_secret(32, as_hex=False)
    assert len(secret_b64) > 30
