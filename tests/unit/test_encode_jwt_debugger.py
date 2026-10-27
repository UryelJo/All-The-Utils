"""
Testes unitários rigorosos para o depurador e verificador de JWT (encode.jwt_debugger).
Validações criptográficas reais, assinaturas HMAC e conformidade RFC 7519.
"""
import time
import pytest

from wintoolbox.tools.encode.jwt_debugger.logic import (
    create_signed_jwt,
    decode_jwt_sections,
    split_jwt,
    verify_hmac_signature,
)
from wintoolbox.tools.encode.jwt_debugger.tool import JwtDebuggerTool


def test_jwt_creation_and_hmac_verification():
    payload = {
        "sub": "user_42",
        "role": "editor",
        "iat": 1600000000,
        "exp": 2000000000,
    }
    secret = "chave_super_secreta_wintoolbox_2026"

    # Testa criação e assinatura com HS256
    token_hs256 = create_signed_jwt(payload, secret, algorithm="HS256")
    parts = token_hs256.split(".")
    assert len(parts) == 3

    # Decodificação de seções
    decoded = decode_jwt_sections(token_hs256)
    assert decoded["header"]["alg"] == "HS256"
    assert decoded["header"]["typ"] == "JWT"
    assert decoded["payload"]["sub"] == "user_42"
    assert decoded["payload"]["role"] == "editor"

    # Validação com a chave secreta correta
    res_valid = verify_hmac_signature(token_hs256, secret)
    assert res_valid["valid"] is True
    assert res_valid["error"] is None
    assert res_valid["algorithm"] == "HS256"

    # Validação com chave incorreta
    res_invalid = verify_hmac_signature(token_hs256, "chave_errada")
    assert res_invalid["valid"] is False
    assert "não confere" in res_invalid["error"]


def test_jwt_algorithms_hs384_hs512():
    payload = {"data": "teste_algoritmos"}
    secret = "segredo_comum"

    token_384 = create_signed_jwt(payload, secret, algorithm="HS384")
    token_512 = create_signed_jwt(payload, secret, algorithm="HS512")

    assert verify_hmac_signature(token_384, secret)["valid"] is True
    assert verify_hmac_signature(token_512, secret)["valid"] is True

    # Troca cruzada de assinaturas deve falhar
    assert verify_hmac_signature(token_384, secret + "x")["valid"] is False


def test_jwt_time_claims_analysis():
    now = int(time.time())
    
    # Token expirado
    expired_payload = {
        "exp": now - 3600,
        "iat": now - 7200,
    }
    token_expired = create_signed_jwt(expired_payload, "key")
    res_exp = decode_jwt_sections(token_expired)
    assert res_exp["time_status"]["is_expired"] is True
    assert "Expirado há" in res_exp["time_status"]["summary"]

    # Token futuro
    future_payload = {
        "exp": now + 3600,
        "nbf": now - 60,
    }
    token_future = create_signed_jwt(future_payload, "key")
    res_future = decode_jwt_sections(token_future)
    assert res_future["time_status"]["is_expired"] is False
    assert "Válido por mais" in res_future["time_status"]["summary"]


def test_jwt_debugger_edge_cases():
    with pytest.raises(ValueError, match="esperadas 3 partes"):
        split_jwt("parte1.parte2")

    with pytest.raises(ValueError, match="esperadas 3 partes"):
        split_jwt("uma_parte_so")

    with pytest.raises(ValueError, match="não suportado"):
        create_signed_jwt({}, "key", algorithm="DESCONHECIDO")


def test_jwt_debugger_tool_ui(qtbot):
    tool = JwtDebuggerTool()
    view = tool.build_view()
    qtbot.addWidget(view)

    # Clica no botão demo
    view._load_demo_token()

    assert "Administrador WinToolbox" in view._txt_payload.toPlainText()
    assert "HS256" in view._txt_header.toPlainText()
    assert "Assinatura VÁLIDA" in view._lbl_sig_badge.text()

    # Altera a chave secreta na interface e verifica se o badge vira inválido
    view._txt_secret.setText("segredo_alterado_incorreto")
    assert "Assinatura INVÁLIDA" in view._lbl_sig_badge.text()
