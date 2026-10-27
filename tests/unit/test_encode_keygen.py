"""
Testes unitários rigorosos para geração de pares de chaves criptográficas (keygen).
Em conformidade com o Princípio da Validação do Efeito Real (Black-Box Testing).
"""
import pytest
from cryptography.hazmat.primitives import serialization
from wintoolbox.tools.encode.keygen.logic import (
    compute_openssh_fingerprints,
    generate_key_pair,
)


def test_generate_ed25519_key_pair():
    """Valida geração real de chave Ed25519 sem senha e recarregamento criptográfico."""
    pair = generate_key_pair(algorithm="ed25519", comment="teste@wintoolbox")

    assert pair.algorithm == "ed25519"
    assert pair.comment == "teste@wintoolbox"
    assert pair.public_key_openssh.startswith("ssh-ed25519 AAA")
    assert pair.public_key_openssh.endswith("teste@wintoolbox")
    assert "BEGIN PUBLIC KEY" in pair.public_key_pem
    assert "BEGIN PRIVATE KEY" in pair.private_key_pem or "BEGIN OPENSSH PRIVATE KEY" in pair.private_key_openssh

    # Validação Black-Box: carrega a chave privada de volta usando cryptography
    loaded_priv = serialization.load_pem_private_key(
        pair.private_key_pem.encode("ascii"),
        password=None,
    )
    assert loaded_priv is not None

    # Validação de Fingerprints
    assert pair.fingerprint_sha256.startswith("SHA256:")
    assert len(pair.fingerprint_sha256) > 20
    assert len(pair.fingerprint_md5.split(":")) == 16


def test_generate_rsa_key_pair_with_passphrase():
    """Valida geração de chave RSA 2048 com senha de proteção (AES-256)."""
    passphrase = "senha_muito_segura_123"
    pair = generate_key_pair(algorithm="rsa2048", passphrase=passphrase, comment="servidor-prod")

    assert pair.public_key_openssh.startswith("ssh-rsa AAA")
    assert "ENCRYPTED PRIVATE KEY" in pair.private_key_pem

    # Validação Black-Box: tentar carregar sem senha deve falhar
    with pytest.raises(TypeError):
        serialization.load_pem_private_key(
            pair.private_key_pem.encode("ascii"),
            password=None,
        )

    # Carregar com a senha correta deve suceder
    loaded_priv = serialization.load_pem_private_key(
        pair.private_key_pem.encode("ascii"),
        password=passphrase.encode("utf-8"),
    )
    assert loaded_priv is not None


def test_compute_openssh_fingerprints():
    """Valida cálculo de fingerprints a partir de chave pública conhecida."""
    # Gera uma chave real para testar
    pair = generate_key_pair("ed25519")
    fp_sha, fp_md5 = compute_openssh_fingerprints(pair.public_key_openssh)
    assert fp_sha == pair.fingerprint_sha256
    assert fp_md5 == pair.fingerprint_md5

    # Entrada vazia ou malformada
    assert compute_openssh_fingerprints("") == ("", "")
    assert compute_openssh_fingerprints("invalido") == ("", "")
