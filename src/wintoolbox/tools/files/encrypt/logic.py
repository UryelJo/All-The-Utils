"""
Lógica pura de Criptografia e Descriptografia de Arquivos com AES-256-GCM.

Formato v2 (atual, "WTBX_AE2"):
  - chave derivada com scrypt (N=2^17, r=8, p=1: recomendação OWASP; ~128 MB de RAM por derivação),
    o que torna ataques de força bruta com GPU muito mais caros que o PBKDF2 do formato v1;
  - criptografia em blocos de 1 MiB (construção STREAM: nonce = prefixo aleatório + contador +
    marca de último bloco), sem carregar o arquivo inteiro na memória e detectando
    reordenação, remoção ou truncamento de blocos;
  - o cabeçalho inteiro é autenticado (dado associado do AES-GCM).
Formato v1 ("WTBX_AES", PBKDF2 100k + um único bloco) continua sendo descriptografado.
"""
import os
import struct
from pathlib import Path
from typing import BinaryIO, Callable, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

ProgressCb = Optional[Callable[[int, int, str], None]]

# --- Formato v1 (legado: somente leitura) ---
MAGIC_HEADER = b"WTBX_AES"  # 8 bytes
SALT_SIZE = 16              # 16 bytes
NONCE_SIZE = 12             # 12 bytes para AESGCM

# --- Formato v2 ---
MAGIC_V2 = b"WTBX_AE2"
SCRYPT_LOG2_N = 17
SCRYPT_R = 8
SCRYPT_P = 1
NONCE_PREFIX_SIZE = 7       # + contador (4) + marca de último bloco (1) = 12 bytes
CHUNK_SIZE = 1024 * 1024
TAG_SIZE = 16
# magic(8) | log2N(1) r(1) p(1) | salt(16) | prefixo do nonce(7) | tamanho do bloco(4, big-endian)
_V2_HEADER = struct.Struct(">8sBBB16s7sI")


def derive_key(password: str, salt: bytes) -> bytes:
    """Derivação do formato v1 (PBKDF2-HMAC-SHA256, 100.000 iterações)."""
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    return kdf.derive(password.encode("utf-8"))


def derive_key_scrypt(password: str, salt: bytes, log2_n: int = SCRYPT_LOG2_N, r: int = SCRYPT_R,
                      p: int = SCRYPT_P) -> bytes:
    """Derivação do formato v2 (scrypt)."""
    return Scrypt(salt=salt, length=32, n=2 ** log2_n, r=r, p=p).derive(password.encode("utf-8"))


def is_wintoolbox_encrypted(path: Path) -> bool:
    """Verifica se o arquivo contém o cabeçalho de criptografia do All the Utils (v1 ou v2)."""
    try:
        with open(path, "rb") as f:
            return f.read(8) in (MAGIC_HEADER, MAGIC_V2)
    except Exception:
        return False


def _chunk_nonce(prefix: bytes, counter: int, last: bool) -> bytes:
    return prefix + struct.pack(">I", counter) + (b"\x01" if last else b"\x00")


def _write_atomic(dst_path: Path, writer: Callable[[BinaryIO], None]) -> None:
    """Grava em arquivo temporário e só o promove ao final (nada parcial em caso de erro)."""
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst_path.with_name(dst_path.name + ".partial")
    try:
        with open(tmp, "wb") as f_out:
            writer(f_out)
        os.replace(tmp, dst_path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def encrypt_file(
    src_path: Path,
    dst_path: Path,
    password: str,
    delete_original: bool = False,
    progress_cb: ProgressCb = None,
) -> Path:
    """Criptografa um arquivo no formato v2 (scrypt + AES-256-GCM em blocos)."""
    src_path = Path(src_path).resolve()
    dst_path = Path(dst_path).resolve()

    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {src_path}")
    if not password:
        raise ValueError("A senha de criptografia não pode ser vazia.")

    total_bytes = src_path.stat().st_size
    salt = os.urandom(SALT_SIZE)
    prefix = os.urandom(NONCE_PREFIX_SIZE)
    header = _V2_HEADER.pack(MAGIC_V2, SCRYPT_LOG2_N, SCRYPT_R, SCRYPT_P, salt, prefix, CHUNK_SIZE)
    if progress_cb:
        progress_cb(0, total_bytes, "Derivando chave (scrypt)...")
    aesgcm = AESGCM(derive_key_scrypt(password, salt))

    def write(f_out: BinaryIO) -> None:
        f_out.write(header)
        done = 0
        with open(src_path, "rb") as f_in:
            chunk = f_in.read(CHUNK_SIZE)
            counter = 0
            while True:
                nxt = f_in.read(CHUNK_SIZE)
                last = not nxt  # leitura antecipada: sabe se este é o último bloco
                f_out.write(aesgcm.encrypt(_chunk_nonce(prefix, counter, last), chunk, header))
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total_bytes, "Criptografando dados...")
                if last:
                    break
                chunk, counter = nxt, counter + 1

    _write_atomic(dst_path, write)

    if progress_cb:
        progress_cb(total_bytes, total_bytes, "Criptografia concluída com sucesso.")
    if delete_original and src_path.exists() and src_path != dst_path:
        src_path.unlink()
    return dst_path


def _decrypt_v1(src_path: Path, password: str) -> bytes:
    with open(src_path, "rb") as f_in:
        f_in.read(len(MAGIC_HEADER))
        salt = f_in.read(SALT_SIZE)
        nonce = f_in.read(NONCE_SIZE)
        ciphertext = f_in.read()
    try:
        return AESGCM(derive_key(password, salt)).decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError("Falha na descriptografia: Senha incorreta ou arquivo adulterado/corrompido.")


def decrypt_file(
    src_path: Path,
    dst_path: Path,
    password: str,
    delete_encrypted: bool = False,
    progress_cb: ProgressCb = None,
) -> Path:
    """
    Descriptografa um arquivo do All the Utils (v2 ou v1 legado).
    Valida autenticidade e integridade; levanta ValueError se a senha for incorreta.
    """
    src_path = Path(src_path).resolve()
    dst_path = Path(dst_path).resolve()

    if not src_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {src_path}")
    if not password:
        raise ValueError("A senha não pode ser vazia.")

    total_bytes = src_path.stat().st_size
    with open(src_path, "rb") as f:
        magic = f.read(8)

    if magic == MAGIC_HEADER:
        if total_bytes < len(MAGIC_HEADER) + SALT_SIZE + NONCE_SIZE + TAG_SIZE:
            raise ValueError("Arquivo corrompido ou formato incompatível com All the Utils.")
        plaintext = _decrypt_v1(src_path, password)
        _write_atomic(dst_path, lambda f_out: f_out.write(plaintext))
    elif magic == MAGIC_V2:
        if total_bytes < _V2_HEADER.size + TAG_SIZE:
            raise ValueError("Arquivo corrompido ou formato incompatível com All the Utils.")
        with open(src_path, "rb") as f_in:
            header = f_in.read(_V2_HEADER.size)
            _, log2_n, r, p, salt, prefix, chunk_size = _V2_HEADER.unpack(header)
            if not (10 <= log2_n <= 22 and 1 <= r <= 32 and 1 <= p <= 16 and 1 <= chunk_size <= 64 * 1024 * 1024):
                raise ValueError("Cabeçalho de criptografia inválido ou corrompido.")
            if progress_cb:
                progress_cb(0, total_bytes, "Derivando chave (scrypt)...")
            aesgcm = AESGCM(derive_key_scrypt(password, salt, log2_n, r, p))

            def write(f_out: BinaryIO) -> None:
                remaining = total_bytes - _V2_HEADER.size
                counter = 0
                while remaining > 0:
                    size = min(remaining, chunk_size + TAG_SIZE)
                    block = f_in.read(size)
                    remaining -= len(block)
                    last = remaining == 0
                    try:
                        f_out.write(aesgcm.decrypt(_chunk_nonce(prefix, counter, last), block, header))
                    except Exception:
                        raise ValueError("Falha na descriptografia: Senha incorreta ou arquivo "
                                         "adulterado/corrompido.") from None
                    counter += 1
                    if progress_cb:
                        progress_cb(total_bytes - remaining, total_bytes, "Descriptografando dados...")

            _write_atomic(dst_path, write)
    else:
        raise ValueError("O arquivo não possui o formato de criptografia do WinToolbox / All the Utils.")

    if progress_cb:
        progress_cb(total_bytes, total_bytes, "Descriptografia concluída com sucesso.")
    if delete_encrypted and src_path.exists() and src_path != dst_path:
        src_path.unlink()
    return dst_path
