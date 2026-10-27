"""
Testes unitários para dev.selfsigned_cert.
Valida geração real de chaves e certificados X.509 com validação via cryptography.
"""
import pytest
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes

from wintoolbox.tools.dev.selfsigned_cert.logic import (
    export_pkcs12_pfx,
    generate_self_signed_cert,
    parse_san_entries,
)


def test_parse_san_entries():
    """Valida conversão de strings para DNSName e IPAddress."""
    entries = parse_san_entries(["localhost", "127.0.0.1", "::1", "*.meuapp.local"])
    assert len(entries) == 4
    types = [type(e) for e in entries]
    assert x509.DNSName in types
    assert x509.IPAddress in types


def test_generate_self_signed_cert_rsa_and_verification():
    """Testa geração completa de certificado RSA 2048 com SANs."""
    res = generate_self_signed_cert(
        common_name="api.local",
        organization="WinToolbox Teste",
        san_list=["localhost", "127.0.0.1"],
        validity_days=30,
        key_type="RSA_2048",
        is_ca=False
    )

    assert "BEGIN CERTIFICATE" in res.cert_pem
    assert "BEGIN RSA PRIVATE KEY" in res.key_pem
    assert len(res.fingerprint_sha256) > 20
    assert res.subject_cn == "api.local"

    # Validação do certificado X509 com leitor nativo da biblioteca cryptography
    cert = x509.load_pem_x509_certificate(res.cert_pem.encode("utf-8"))
    assert cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value == "api.local"

    # Valida presença da extensão SAN
    san_ext = cert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
    assert san_ext is not None


def test_export_pkcs12_pfx(tmp_path: Path):
    """Testa exportação física para pacote PFX / PKCS#12 protegido por senha."""
    res = generate_self_signed_cert(common_name="pfx_test.local")
    pfx_file = tmp_path / "cert.pfx"

    out = export_pkcs12_pfx(
        cert_pem=res.cert_pem,
        key_pem=res.key_pem,
        output_path=pfx_file,
        password="SenhaForte123!",
        name="pfx_test"
    )

    assert out == pfx_file
    assert pfx_file.is_file()
    assert pfx_file.stat().st_size > 0


def test_generate_self_signed_cert_validation_errors():
    """Valida tratamento de erros para parâmetros incorretos."""
    with pytest.raises(ValueError):
        generate_self_signed_cert(common_name="   ")

    with pytest.raises(ValueError):
        generate_self_signed_cert(common_name="valido.local", validity_days=0)
