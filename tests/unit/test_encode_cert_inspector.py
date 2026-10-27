"""
Testes unitários rigorosos para inspeção e conversão de certificados digitais.
Princípio da Validação do Efeito Real (Black-Box Testing com arquivos físicos X.509).
"""
from datetime import datetime, timedelta, timezone
import ipaddress
from pathlib import Path
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from wintoolbox.core.registry import TaskContext
from wintoolbox.tools.encode.cert_inspector.logic import (
    convert_cert_to_pem,
    parse_certificate_bytes,
    parse_certificate_file,
)
from wintoolbox.tools.encode.cert_inspector.tool import CertInspectorTool


def _create_sample_x509_cert(output_path: Path) -> Path:
    """Gera um certificado X.509 real em disco para testes de conformidade."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "servidor.local"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "WinToolbox Seguros"),
    ])
    issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Autoridade Certificadora Root"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "WinToolbox CA"),
    ])

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("servidor.local"),
                x509.DNSName("api.servidor.local"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    output_path.write_bytes(cert_pem)
    return output_path


def test_parse_certificate_real_disk_effect(tmp_path: Path):
    """Valida leitura e extração exata de metadados de certificado X.509 físico."""
    cert_path = tmp_path / "teste_cert.crt"
    _create_sample_x509_cert(cert_path)

    info = parse_certificate_file(cert_path)

    assert info.is_valid_format is True
    assert info.subject_cn == "servidor.local"
    assert info.subject_org == "WinToolbox Seguros"
    assert info.issuer_cn == "Autoridade Certificadora Root"
    assert info.issuer_org == "WinToolbox CA"
    assert info.is_expired is False
    assert info.days_remaining >= 364
    assert info.public_key_type == "RSA"
    assert info.public_key_bits == 2048
    assert "servidor.local" in info.subject_alt_names
    assert "api.servidor.local" in info.subject_alt_names
    assert "127.0.0.1" in info.subject_alt_names
    assert len(info.sha256_thumbprint) == 64
    assert len(info.sha1_thumbprint) == 40


def test_convert_cert_to_pem_and_tool_process(tmp_path: Path):
    """Valida conversão e o contrato FileTool.process gravando relatório no disco."""
    cert_path = tmp_path / "cert_source.cer"
    _create_sample_x509_cert(cert_path)

    # Conversão para PEM
    pem_out = tmp_path / "cert_converted.pem"
    assert convert_cert_to_pem(cert_path, pem_out) is True
    assert pem_out.exists()
    pem_content = pem_out.read_text(encoding="utf-8")
    assert pem_content.startswith("-----BEGIN CERTIFICATE-----")

    # Contrato FileTool.process gerando relatório .txt
    tool = CertInspectorTool()
    report_out = tmp_path / "relatorio.txt"
    ctx = TaskContext(
        on_progress=lambda c, t, m: None,
        on_log=lambda l, m: None,
        is_cancelled=lambda: False,
    )

    success = tool.process(
        source_path=cert_path,
        output_path=report_out,
        options={"mode": "report"},
        context=ctx,
    )
    assert success is True
    assert report_out.exists()
    report_text = report_out.read_text(encoding="utf-8")
    assert "servidor.local" in report_text
    assert "WinToolbox Seguros" in report_text
    assert "SHA-256:" in report_text


def test_parse_invalid_file(tmp_path: Path):
    """Valida rejeição elegante de arquivo corrompido ou inválido."""
    bad_file = tmp_path / "fake.crt"
    bad_file.write_text("isto nao e um certificado valido", encoding="utf-8")

    info = parse_certificate_file(bad_file)
    assert info.is_valid_format is False
    assert "Não foi possível decodificar" in info.error_message
