"""
Lógica pura para geração de certificados SSL/TLS autoassinados e CAs locais.
Utiliza a biblioteca cryptography com suporte a RSA, ECDSA e múltiplos SANs (DNS e IP).
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
import datetime
import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


@dataclass
class CertificateResult:
    """Contém os artefatos gerados da chave e do certificado."""
    cert_pem: str
    key_pem: str
    fingerprint_sha256: str
    subject_cn: str
    valid_from: datetime.datetime
    valid_to: datetime.datetime
    san_list: List[str]


def parse_san_entries(sans: List[str]) -> List[x509.GeneralName]:
    """Converte uma lista de strings de nomes em entradas DNSName ou IPAddress do x509."""
    entries: List[x509.GeneralName] = []
    for s in sans:
        s_clean = s.strip()
        if not s_clean:
            continue
        try:
            ip = ipaddress.ip_address(s_clean)
            entries.append(x509.IPAddress(ip))
        except ValueError:
            entries.append(x509.DNSName(s_clean))
    return entries


def generate_self_signed_cert(
    common_name: str = "localhost",
    organization: str = "WinToolbox Dev",
    san_list: Optional[List[str]] = None,
    validity_days: int = 365,
    key_type: str = "RSA_2048",
    is_ca: bool = False
) -> CertificateResult:
    """
    Gera um par de certificado X.509 autoassinado e chave privada.
    """
    if not common_name.strip():
        raise ValueError("O Common Name (CN) é obrigatório.")

    if validity_days < 1:
        raise ValueError("A validade deve ser de pelo menos 1 dia.")

    # 1. Geração da Chave Privada
    key: Union[rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey]
    if key_type == "RSA_4096":
        key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    elif key_type == "ECDSA_P256":
        key = ec.generate_private_key(ec.SECP256R1())
    elif key_type == "ECDSA_P384":
        key = ec.generate_private_key(ec.SECP384R1())
    else:  # Padrão RSA 2048
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # 2. Definição do Subject e Issuer
    subject_names = [
        x509.NameAttribute(NameOID.COMMON_NAME, common_name.strip()),
    ]
    if organization.strip():
        subject_names.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization.strip()))

    subject = x509.Name(subject_names)
    issuer = subject  # Autoassinado

    now = datetime.datetime.now(datetime.timezone.utc)
    valid_until = now + datetime.timedelta(days=validity_days)

    builder = x509.CertificateBuilder()
    builder = builder.subject_name(subject)
    builder = builder.issuer_name(issuer)
    builder = builder.public_key(key.public_key())
    builder = builder.serial_number(x509.random_serial_number())
    builder = builder.not_valid_before(now)
    builder = builder.not_valid_after(valid_until)

    # 3. Extensões
    if is_ca:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    else:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=False,
        )
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
                ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=False,
        )

    # Subject Alternative Names (SAN)
    all_sans: List[str] = []
    if san_list:
        all_sans.extend(san_list)
    if common_name not in all_sans:
        all_sans.append(common_name)

    san_entries = parse_san_entries(all_sans)
    if san_entries:
        builder = builder.add_extension(
            x509.SubjectAlternativeName(san_entries),
            critical=False,
        )

    # Subject Key Identifier
    builder = builder.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
        critical=False,
    )

    # 4. Assinatura do Certificado
    cert = builder.sign(private_key=key, algorithm=hashes.SHA256())

    # 5. Serialização em PEM
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    fingerprint = cert.fingerprint(hashes.SHA256()).hex().upper()
    fingerprint_formatted = ":".join(fingerprint[i:i+2] for i in range(0, len(fingerprint), 2))

    return CertificateResult(
        cert_pem=cert_pem,
        key_pem=key_pem,
        fingerprint_sha256=fingerprint_formatted,
        subject_cn=common_name,
        valid_from=now,
        valid_to=valid_until,
        san_list=all_sans
    )


def export_pkcs12_pfx(
    cert_pem: str,
    key_pem: str,
    output_path: Path,
    password: Optional[str] = None,
    name: str = "certificate"
) -> Path:
    """Exporta o certificado e chave privada combinados no formato PKCS#12 (.pfx / .p12)."""
    cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
    key = serialization.load_pem_private_key(key_pem.encode("utf-8"), password=None)

    enc_algo: serialization.KeySerializationEncryption
    if password:
        enc_algo = serialization.BestAvailableEncryption(password.encode("utf-8"))
    else:
        enc_algo = serialization.NoEncryption()

    p12_data = pkcs12.serialize_key_and_certificates(
        name=name.encode("utf-8"),
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=enc_algo
    )

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(p12_data)
    return output_path
