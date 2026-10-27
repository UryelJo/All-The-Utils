"""
Lógica pura para inspeção, decodificação e conversão de certificados digitais X.509 e PKCS#12.

Suporta:
- Formatos: PEM, DER (.crt, .cer), PKCS#12 (.pfx, .p12)
- Extração de Titular (Subject), Emissor (Issuer), Validade (Not Before / Not After),
  Número de Série, Algoritmo de Assinatura, Chave Pública, SANs (Subject Alternative Names)
- Cálculo de Thumbprints / Impressões Digitais (SHA-256 e SHA-1)
- Conversão para formato PEM padronizado

Isolado de qualquer biblioteca de interface gráfica.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import List, Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtensionOID, NameOID


@dataclass(frozen=True)
class CertificateInfo:
    """Metadados estruturados extraídos de um certificado digital."""
    is_valid_format: bool
    subject_cn: str
    subject_org: str
    issuer_cn: str
    issuer_org: str
    serial_number_hex: str
    not_before: Optional[datetime]
    not_after: Optional[datetime]
    is_expired: bool
    days_remaining: int
    signature_algorithm: str
    public_key_type: str
    public_key_bits: int
    subject_alt_names: List[str] = field(default_factory=list)
    sha256_thumbprint: str = ""
    sha1_thumbprint: str = ""
    error_message: str = ""


def _extract_x509_info(cert: x509.Certificate) -> CertificateInfo:
    """Extrai informações estruturadas de uma instância x509.Certificate."""
    now = datetime.now(timezone.utc)
    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc

    is_expired = now > not_after
    days_rem = (not_after - now).days if not is_expired else 0

    # Subject
    try:
        cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        subject_cn = cn_attrs[0].value if cn_attrs else ""
    except Exception:
        subject_cn = ""

    try:
        org_attrs = cert.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
        subject_org = org_attrs[0].value if org_attrs else ""
    except Exception:
        subject_org = ""

    # Issuer
    try:
        icn_attrs = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        issuer_cn = icn_attrs[0].value if icn_attrs else ""
    except Exception:
        issuer_cn = ""

    try:
        iorg_attrs = cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
        issuer_org = iorg_attrs[0].value if iorg_attrs else ""
    except Exception:
        issuer_org = ""

    # Serial Number
    serial_hex = f"{cert.serial_number:X}"

    # Algoritmo de Assinatura
    sig_algo = cert.signature_algorithm_oid._name if hasattr(cert.signature_algorithm_oid, "_name") else str(cert.signature_algorithm_oid.dotted_string)

    # Chave Pública
    pub = cert.public_key()
    if isinstance(pub, rsa.RSAPublicKey):
        pub_type = "RSA"
        pub_bits = pub.key_size
    elif isinstance(pub, ec.EllipticCurvePublicKey):
        pub_type = f"ECDSA ({pub.curve.name})"
        pub_bits = pub.key_size
    elif isinstance(pub, ed25519.Ed25519PublicKey):
        pub_type = "Ed25519"
        pub_bits = 256
    else:
        pub_type = pub.__class__.__name__
        pub_bits = getattr(pub, "key_size", 0)

    # SANs (Subject Alternative Names)
    sans: List[str] = []
    try:
        san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        san_value = san_ext.value
        if isinstance(san_value, x509.SubjectAlternativeName):
            sans = [str(name.value) for name in san_value]
    except Exception:
        pass

    # Thumbprints
    raw_der = cert.public_bytes(serialization.Encoding.DER)
    sha256_thumb = hashlib.sha256(raw_der).hexdigest().upper()
    sha1_thumb = hashlib.sha1(raw_der).hexdigest().upper()

    return CertificateInfo(
        is_valid_format=True,
        subject_cn=str(subject_cn),
        subject_org=str(subject_org),
        issuer_cn=str(issuer_cn),
        issuer_org=str(issuer_org),
        serial_number_hex=serial_hex,
        not_before=not_before,
        not_after=not_after,
        is_expired=is_expired,
        days_remaining=days_rem,
        signature_algorithm=sig_algo,
        public_key_type=pub_type,
        public_key_bits=pub_bits,
        subject_alt_names=sans,
        sha256_thumbprint=sha256_thumb,
        sha1_thumbprint=sha1_thumb,
        error_message="",
    )


def parse_certificate_bytes(data: bytes, password: Optional[str] = None) -> CertificateInfo:
    """
    Tenta decodificar dados binários ou de texto nos formatos PEM, DER ou PKCS#12.
    """
    if not data:
        return CertificateInfo(
            is_valid_format=False,
            subject_cn="",
            subject_org="",
            issuer_cn="",
            issuer_org="",
            serial_number_hex="",
            not_before=None,
            not_after=None,
            is_expired=False,
            days_remaining=0,
            signature_algorithm="",
            public_key_type="",
            public_key_bits=0,
            error_message="Arquivo vazio.",
        )

    # 1. Tentativa PEM
    try:
        cert = x509.load_pem_x509_certificate(data)
        return _extract_x509_info(cert)
    except Exception:
        pass

    # 2. Tentativa DER
    try:
        cert = x509.load_der_x509_certificate(data)
        return _extract_x509_info(cert)
    except Exception:
        pass

    # 3. Tentativa PKCS#12 (.pfx / .p12)
    pwd_bytes = password.encode("utf-8") if password else None
    try:
        p12_res = pkcs12.load_key_and_certificates(data, pwd_bytes)
        cert = p12_res[1]
        if cert:
            return _extract_x509_info(cert)
    except Exception as e:
        if "password" in str(e).lower() or "mac" in str(e).lower():
            return CertificateInfo(
                is_valid_format=False,
                subject_cn="",
                subject_org="",
                issuer_cn="",
                issuer_org="",
                serial_number_hex="",
                not_before=None,
                not_after=None,
                is_expired=False,
                days_remaining=0,
                signature_algorithm="",
                public_key_type="",
                public_key_bits=0,
                error_message="Certificado PKCS#12 protegido por senha incorreta ou ausente.",
            )

    return CertificateInfo(
        is_valid_format=False,
        subject_cn="",
        subject_org="",
        issuer_cn="",
        issuer_org="",
        serial_number_hex="",
        not_before=None,
        not_after=None,
        is_expired=False,
        days_remaining=0,
        signature_algorithm="",
        public_key_type="",
        public_key_bits=0,
        error_message="Não foi possível decodificar o certificado (formato desconhecido ou corrompido).",
    )


def parse_certificate_file(file_path: Path, password: Optional[str] = None) -> CertificateInfo:
    """Lê um arquivo do sistema de arquivos e decodifica seus metadados."""
    try:
        data = file_path.read_bytes()
        return parse_certificate_bytes(data, password=password)
    except Exception as e:
        return CertificateInfo(
            is_valid_format=False,
            subject_cn="",
            subject_org="",
            issuer_cn="",
            issuer_org="",
            serial_number_hex="",
            not_before=None,
            not_after=None,
            is_expired=False,
            days_remaining=0,
            signature_algorithm="",
            public_key_type="",
            public_key_bits=0,
            error_message=f"Falha ao ler arquivo: {e}",
        )


def convert_cert_to_pem(input_path: Path, output_path: Path, password: Optional[str] = None) -> bool:
    """Converte qualquer certificado suportado para formato PEM legível."""
    data = input_path.read_bytes()
    cert: Optional[x509.Certificate] = None

    try:
        cert = x509.load_pem_x509_certificate(data)
    except Exception:
        try:
            cert = x509.load_der_x509_certificate(data)
        except Exception:
            pwd_bytes = password.encode("utf-8") if password else None
            p12 = pkcs12.load_key_and_certificates(data, pwd_bytes)
            cert = p12[1]

    if not cert:
        return False

    pem_bytes = cert.public_bytes(serialization.Encoding.PEM)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pem_bytes)
    return True
