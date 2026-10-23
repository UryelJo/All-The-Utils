"""
Lógica pura de Criptografia e Descriptografia de Arquivos com AES-256-GCM.
Utiliza derivação de chave segura PBKDF2 com 100.000 iterações de HMAC-SHA256 e verificação de integridade AEAD.
"""
import os
from pathlib import Path
from typing import Callable, Optional
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC_HEADER = b"WTBX_AES"  # 8 bytes
SALT_SIZE = 16              # 16 bytes
NONCE_SIZE = 12             # 12 bytes para AESGCM


def derive_key(password: str, salt: bytes) -> bytes:
    """Deriva uma chave AES-256 de 32 bytes usando PBKDF2 com 100.000 iterações."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return kdf.derive(password.encode("utf-8"))


def is_wintoolbox_encrypted(path: Path) -> bool:
    """Verifica se o arquivo contém o cabeçalho mágico de criptografia do All the Utils."""
    try:
        with open(path, "rb") as f:
            header = f.read(len(MAGIC_HEADER))
            return header == MAGIC_HEADER
    except Exception:
        return False


def encrypt_file(
    src_path: Path,
    dst_path: Path,
    password: str,
    delete_original: bool = False,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> Path:
    """
    Criptografa um arquivo local usando AES-256-GCM.
    Gera arquivo contendo: MAGIC_HEADER (8B) + SALT (16B) + NONCE (12B) + CIPHERTEXT_WITH_TAG.
    """
    src_path = Path(src_path).resolve()
    dst_path = Path(dst_path).resolve()

    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {src_path}")
    if not password:
        raise ValueError("A senha de criptografia não pode ser vazia.")

    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)

    total_bytes = src_path.stat().st_size
    if progress_cb:
        progress_cb(0, total_bytes, "Lendo e criptografando dados...")

    with open(src_path, "rb") as f_in:
        plaintext = f_in.read()

    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dst_path, "wb") as f_out:
        f_out.write(MAGIC_HEADER)
        f_out.write(salt)
        f_out.write(nonce)
        f_out.write(ciphertext)

    if progress_cb:
        progress_cb(total_bytes, total_bytes, "Criptografia concluída com sucesso.")

    if delete_original and src_path.exists() and src_path != dst_path:
        src_path.unlink()

    return dst_path


def decrypt_file(
    src_path: Path,
    dst_path: Path,
    password: str,
    delete_encrypted: bool = False,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> Path:
    """
    Descriptografa um arquivo criptografado com AES-256-GCM.
    Valida autenticidade e integridade; levanta ValueError se a senha for incorreta.
    """
    src_path = Path(src_path).resolve()
    dst_path = Path(dst_path).resolve()

    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {src_path}")
    if not password:
        raise ValueError("A senha não pode ser vazia.")

    total_bytes = src_path.stat().st_size
    min_size = len(MAGIC_HEADER) + SALT_SIZE + NONCE_SIZE + 16  # 16 bytes tag mínima
    if total_bytes < min_size:
        raise ValueError("Arquivo corrompido ou formato incompatível com All the Utils.")

    with open(src_path, "rb") as f_in:
        header = f_in.read(len(MAGIC_HEADER))
        if header != MAGIC_HEADER:
            raise ValueError("O arquivo não possui o formato de criptografia do WinToolbox / All the Utils.")

        salt = f_in.read(SALT_SIZE)
        nonce = f_in.read(NONCE_SIZE)
        ciphertext = f_in.read()

    key = derive_key(password, salt)
    aesgcm = AESGCM(key)

    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError("Falha na descriptografia: Senha incorreta ou arquivo adulterado/corrompido.")

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dst_path, "wb") as f_out:
        f_out.write(plaintext)

    if progress_cb:
        progress_cb(total_bytes, total_bytes, "Descriptografia concluída com sucesso.")

    if delete_encrypted and src_path.exists() and src_path != dst_path:
        src_path.unlink()

    return dst_path
