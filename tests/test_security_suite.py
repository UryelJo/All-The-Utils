"""Testes das ferramentas de segurança ofensiva e forense de hashes."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from wintoolbox.tools.security.hash_cracker.logic import HashCracker, calcular_hash
from wintoolbox.tools.security.hash_identify.logic import identify_hash, identify_hash_type
from wintoolbox.tools.security.jwt_secret_cracker.logic import (
    JWTInvalido,
    crack_jwt_secret,
    gerar_jwt,
    parse_jwt,
    verificar_assinatura,
)
from wintoolbox.tools.security.rainbow_generator.logic import (
    consultar_hash,
    gerar_rainbow,
    metadados_tabela,
)


def test_identify_hash_prefixos_e_comprimentos():
    assert identify_hash_type("5d41402abc4b2a76b9719d911017c592") == "MD5"
    assert identify_hash_type("a" * 64) == "SHA-256"
    assert identify_hash_type("$2b$12$" + "a" * 53) == "bcrypt"
    assert identify_hash_type("pbkdf2_sha256$600000$salt$hash") == "Django (PBKDF2-SHA256)"
    assert identify_hash_type("*2470C0C06DEE42FD1618BB99005ADCA2EC9D1E19").startswith("MySQL")
    assert identify_hash_type("texto qualquer") is None


def test_identify_hash_ambiguidade_32_hex():
    candidatos = identify_hash("8846f7eaee8fb117ad06bdd830b7586c")
    nomes = {c.algorithm for c in candidatos}
    assert "MD5" in nomes
    assert "NTLM" in nomes
    assert all(c.confidence in {"Alto", "Médio", "Baixa", "Baixo"} for c in candidatos)


def test_hash_cracker_wordlist(tmp_path: Path):
    wordlist = tmp_path / "lista.txt"
    wordlist.write_text("alpha\nbeta\nsenha-forte\n", encoding="utf-8")
    alvo = hashlib.sha256(b"senha-forte").hexdigest()
    resultado = HashCracker(alvo, "SHA-256", wordlist).quebrar_wordlist()
    assert resultado.found is True
    assert resultado.password == "senha-forte"
    assert resultado.attempts == 3


def test_hash_cracker_forca_bruta_e_ntlm():
    alvo = hashlib.md5(b"ba").hexdigest()
    resultado = HashCracker(alvo, "MD5").quebrar_forca_bruta("ab", 1, 2)
    assert resultado.found is True
    assert resultado.password == "ba"

    # NTLM de "password" é bem conhecido.
    assert calcular_hash("password", "NTLM") == "8846f7eaee8fb117ad06bdd830b7586c"
    alvo_ntlm = calcular_hash("abc", "NTLM")
    assert HashCracker(alvo_ntlm, "NTLM").quebrar_wordlist(
        # A lista interna não contém "abc"; força bruta cobre.
    ).found is False
    assert HashCracker(alvo_ntlm, "NTLM").quebrar_forca_bruta("abc", 1, 3).found is True


def test_rainbow_gera_e_consulta(tmp_path: Path):
    destino = tmp_path / "rainbow.db"
    progresso = []
    resultado = gerar_rainbow(
        destino, "MD5", "ab", 1, 2, on_progresso=lambda atual, total: progresso.append((atual, total))
    )
    assert resultado.gerados == 6
    assert progresso[-1] == (6, 6)
    assert consultar_hash(destino, hashlib.md5(b"ab").hexdigest()) == "ab"
    assert consultar_hash(destino, "0" * 32) is None
    meta = metadados_tabela(destino)
    assert meta["algoritmo"] == "MD5"
    assert meta["charset"] == "ab"


def test_jwt_parse_crack_e_reassinatura():
    token = gerar_jwt({"sub": "42", "exp": 9999999999}, "segredo-de-teste", "HS256")
    info = parse_jwt(token)
    assert info.header["alg"] == "HS256"
    assert info.payload["sub"] == "42"
    assert info.expirado is False
    assert verificar_assinatura(token, "segredo-de-teste") is True
    assert verificar_assinatura(token, "errado") is False

    resultado = crack_jwt_secret(token, ["errado", "segredo-de-teste"])
    assert resultado.found is True
    assert resultado.secret == "segredo-de-teste"

    with pytest.raises(JWTInvalido):
        parse_jwt("apenas.duas")


def test_jwt_expirado():
    token = gerar_jwt({"sub": "1", "exp": 1}, "x", "HS384")
    assert parse_jwt(token).expirado is True
