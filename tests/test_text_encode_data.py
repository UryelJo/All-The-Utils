"""
Testes unitários e de integração para a Fase 1: Texto, Dados e Codificação.
"""
import json
from pathlib import Path
import pytest
from wintoolbox.core.registry import get_all_tools, get_categories, get_tool
from wintoolbox.tools.text.diff.tool import compute_diff_html
from wintoolbox.tools.text.transform.tool import remove_accents, to_camel_case, to_slug
from wintoolbox.tools.text.validators_br.tool import (
    generate_valid_cnpj, generate_valid_cpf, validate_cnpj, validate_cpf
)
from wintoolbox.tools.encode.crypto_hash.tool import compute_text_hashes
from wintoolbox.tools.encode.encoders.tool import decode_text, encode_text
from wintoolbox.tools.encode.jwt.tool import decode_jwt_unverified
from wintoolbox.tools.encode.generators.tool import generate_secure_password, generate_ulid
from wintoolbox.tools.data.converter.logic import load_data, save_data
from wintoolbox.tools.data.beautifier.tool import beautify_code, minify_code

def test_phase1_tools_registered():
    tools = get_all_tools()
    tool_ids = [t.id for t in tools]

    expected = [
        "text.diff",
        "text.regex",
        "text.transform",
        "text.validators_br",
        "encode.crypto_hash",
        "encode.encoders",
        "encode.jwt",
        "encode.generators",
        "encode.converter",
        "data.converter",
        "data.beautifier"
    ]
    for exp_id in expected:
        assert exp_id in tool_ids, f"Ferramenta {exp_id} não registrada!"

def test_categories_populated():
    cats = get_categories()
    assert "Texto e Redação" in cats
    assert len(cats["Texto e Redação"]) >= 4

    assert "Codificação e Hash" in cats
    assert len(cats["Codificação e Hash"]) >= 5

    assert "Dados e Estruturas" in cats
    assert len(cats["Dados e Estruturas"]) >= 2

def test_diff_logic():
    html_res, added, removed, equal = compute_diff_html("linha 1\nlinha 2", "linha 1\nlinha alterada")
    assert added == 1
    assert removed == 1
    assert equal == 1
    assert "linha alterada" in html_res

def test_text_transformations():
    assert remove_accents("Atenção, coração e café!") == "Atencao, coracao e cafe!"
    assert to_camel_case("meu nome completo") == "meuNomeCompleto"
    assert to_slug("Título de Artigo com Acentos 2026") == "titulo-de-artigo-com-acentos-2026"

def test_document_validation_and_generation():
    cpf = generate_valid_cpf(formatted=True)
    valid_cpf, msg = validate_cpf(cpf)
    assert valid_cpf, f"CPF gerado {cpf} falhou na validação: {msg}"

    cnpj = generate_valid_cnpj(formatted=True)
    valid_cnpj, msg_c = validate_cnpj(cnpj)
    assert valid_cnpj, f"CNPJ gerado {cnpj} falhou na validação: {msg_c}"

    invalid_cpf, _ = validate_cpf("111.111.111-11")
    assert not invalid_cpf

def test_crypto_hashes():
    h = compute_text_hashes("WinToolbox", secret_key="chave")
    assert len(h["MD5"]) == 32
    assert len(h["SHA-256"]) == 64
    assert "HMAC-SHA256" in h

def test_encoders():
    original = "Texto com acentos & caracteres especiais"
    b64 = encode_text(original, "Base64")
    assert decode_text(b64, "Base64") == original

    url_enc = encode_text("parametro=valor com espacos", "URL Encode")
    assert decode_text(url_enc, "URL Encode") == "parametro=valor com espacos"

    html_enc = encode_text("<script>alert('xss');</script>", "HTML Entities")
    assert "&lt;script&gt;" in html_enc

def test_jwt_decoding():
    # Token JWT exemplo: {"alg":"HS256","typ":"JWT"}.{"sub":"1234567890","name":"John Doe","iat":1516239022}
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    header, payload, sig = decode_jwt_unverified(token)
    assert header.get("alg") == "HS256"
    assert payload.get("name") == "John Doe"

def test_generators():
    ulid = generate_ulid()
    assert len(ulid) == 26
    pwd = generate_secure_password(length=24)
    assert len(pwd) == 24

def test_data_conversion_roundtrip(tmp_path: Path):
    sample = {"sistema": "WinToolbox", "versao": 1, "ativo": True}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(sample), encoding="utf-8")

    data = load_data(json_file)
    assert data["sistema"] == "WinToolbox"

    yaml_file = tmp_path / "test.yaml"
    save_data(data, yaml_file, "YAML")
    assert yaml_file.exists()

    data_back = load_data(yaml_file)
    assert data_back["versao"] == 1

def test_beautifier_and_minifier():
    raw_json = '{"a":1,"b":[2,3]}'
    pretty = beautify_code(raw_json, "JSON", indent=2)
    assert "\n" in pretty
    mini = minify_code(pretty, "JSON")
    assert "\n" not in mini
    assert mini == '{"a":1,"b":[2,3]}'
