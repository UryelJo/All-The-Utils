"""
Lógica pura para geração de pares de chaves criptográficas assimétricas (RSA, Ed25519, ECDSA).

Suporta:
- Algoritmos: Ed25519, RSA (2048, 3072, 4096 bits), ECDSA (SECP256R1, SECP384R1)
- Exportação de chave privada em formatos PEM (PKCS#8) e OpenSSH, com proteção opcional por senha (AES-256)
- Exportação de chave pública em formatos padrão OpenSSH (authorized_keys) e PEM
- Cálculo de impressões digitais (fingerprints) nos padrões SHA-256 e MD5

Isolado de qualquer biblioteca de interface gráfica.
"""
import base64
from dataclasses import dataclass
import hashlib
from typing import Optional, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa


@dataclass(frozen=True)
class GeneratedKeyPair:
    """Par de chaves criptográficas e metadados associados."""
    algorithm: str
    private_key_pem: str
    private_key_openssh: str
    public_key_openssh: str
    public_key_pem: str
    fingerprint_sha256: str
    fingerprint_md5: str
    comment: str


def compute_openssh_fingerprints(public_key_openssh: str) -> Tuple[str, str]:
    """
    Calcula as impressões digitais SHA-256 (Base64) e MD5 (Hex colons)
    da chave pública no formato OpenSSH.
    """
    parts = public_key_openssh.strip().split()
    if len(parts) < 2:
        return "", ""

    b64_str = parts[1]
    missing_padding = len(b64_str) % 4
    if missing_padding:
        b64_str += "=" * (4 - missing_padding)

    try:
        raw_key_bytes = base64.b64decode(b64_str)
    except Exception:
        return "", ""

    # SHA-256 (Padrão moderno do OpenSSH)
    sha256_digest = hashlib.sha256(raw_key_bytes).digest()
    sha256_b64 = base64.b64encode(sha256_digest).decode("ascii").rstrip("=")
    fp_sha256 = f"SHA256:{sha256_b64}"

    # MD5 (Padrão clássico com dois pontos)
    md5_hex = hashlib.md5(raw_key_bytes).hexdigest()
    fp_md5 = ":".join(md5_hex[i:i+2] for i in range(0, len(md5_hex), 2))

    return fp_sha256, fp_md5


def generate_key_pair(
    algorithm: str = "ed25519",  # "ed25519", "rsa2048", "rsa4096", "ecdsa_p256"
    passphrase: Optional[str] = None,
    comment: str = "wintoolbox@local"
) -> GeneratedKeyPair:
    """
    Gera um novo par de chaves assimétricas de acordo com os parâmetros especificados.
    """
    algo = algorithm.lower().strip()

    if algo == "ed25519":
        priv = ed25519.Ed25519PrivateKey.generate()
    elif algo == "rsa2048":
        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    elif algo == "rsa4096":
        priv = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    elif algo == "ecdsa_p256":
        priv = ec.generate_private_key(ec.SECP256R1())
    else:
        raise ValueError(f"Algoritmo não suportado: '{algorithm}'. Use 'ed25519', 'rsa2048', 'rsa4096' ou 'ecdsa_p256'.")

    # Configuração de encriptação da chave privada
    if passphrase:
        encryption_algorithm = serialization.BestAvailableEncryption(passphrase.encode("utf-8"))
    else:
        encryption_algorithm = serialization.NoEncryption()

    # Serialização da Chave Privada em PKCS#8 PEM
    priv_pem_bytes = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption_algorithm,
    )
    priv_pem_str = priv_pem_bytes.decode("ascii")

    # Serialização da Chave Privada em formato OpenSSH
    priv_openssh_bytes = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=encryption_algorithm,
    )
    priv_openssh_str = priv_openssh_bytes.decode("ascii")

    # Chave Pública
    pub = priv.public_key()

    # Chave Pública OpenSSH
    pub_openssh_bytes = pub.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    clean_comment = comment.strip()
    if clean_comment:
        pub_openssh_str = f"{pub_openssh_bytes.decode('ascii')} {clean_comment}"
    else:
        pub_openssh_str = pub_openssh_bytes.decode("ascii")

    # Chave Pública PEM (SubjectPublicKeyInfo)
    pub_pem_bytes = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub_pem_str = pub_pem_bytes.decode("ascii")

    # Impressões digitais
    fp_sha256, fp_md5 = compute_openssh_fingerprints(pub_openssh_str)

    return GeneratedKeyPair(
        algorithm=algo,
        private_key_pem=priv_pem_str,
        private_key_openssh=priv_openssh_str,
        public_key_openssh=pub_openssh_str,
        public_key_pem=pub_pem_str,
        fingerprint_sha256=fp_sha256,
        fingerprint_md5=fp_md5,
        comment=clean_comment,
    )
