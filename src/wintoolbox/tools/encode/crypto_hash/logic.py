"""
Lógica pura da ferramenta Gerador de Hash e Checksum.
Calcula MD5, SHA-1, SHA-256, SHA-512, SHA3-256, CRC32 e HMAC sem dependência de UI.
"""
import hashlib
import hmac
from pathlib import Path
from typing import Callable, Dict, Optional
import zlib


def compute_text_hashes(text: str, secret_key: str = "") -> Dict[str, str]:
    """Calcula os hashes principais de uma string."""
    data = text.encode("utf-8")
    key_bytes = secret_key.encode("utf-8")

    res = {
        "MD5": hashlib.md5(data).hexdigest(),
        "SHA-1": hashlib.sha1(data).hexdigest(),
        "SHA-256": hashlib.sha256(data).hexdigest(),
        "SHA-512": hashlib.sha512(data).hexdigest(),
        "SHA3-256": hashlib.sha3_256(data).hexdigest(),
        "CRC32": f"{zlib.crc32(data) & 0xffffffff:08x}",
    }

    if secret_key:
        res["HMAC-SHA256"] = hmac.new(key_bytes, data, hashlib.sha256).hexdigest()
        res["HMAC-SHA512"] = hmac.new(key_bytes, data, hashlib.sha512).hexdigest()

    return res


def compute_file_hash(
    file_path: Path,
    algorithm: str = "SHA-256",
    progress_cb: Optional[Callable[[int], None]] = None,
) -> str:
    """Calcula o hash de um arquivo em streaming com suporte a arquivos grandes."""
    alg = algorithm.upper()
    total_size = file_path.stat().st_size
    read_bytes = 0

    if alg == "MD5":
        hasher = hashlib.md5()
    elif alg == "SHA-1":
        hasher = hashlib.sha1()
    elif alg == "SHA-512":
        hasher = hashlib.sha512()
    elif alg == "CRC32":
        crc = 0
        with open(file_path, "rb") as f:
            while chunk := f.read(1048576):
                crc = zlib.crc32(chunk, crc)
                read_bytes += len(chunk)
                if progress_cb and total_size > 0:
                    progress_cb(int((read_bytes / total_size) * 100))
        return f"{crc & 0xffffffff:08x}"
    else:
        hasher = hashlib.sha256()

    with open(file_path, "rb") as f:
        while chunk := f.read(1048576):
            hasher.update(chunk)
            read_bytes += len(chunk)
            if progress_cb and total_size > 0:
                progress_cb(int((read_bytes / total_size) * 100))

    return hasher.hexdigest()


def compare_hashes(hash_a: str, hash_b: str) -> bool:
    """Compara dois hashes de forma case-insensitive e sem espaços."""
    return hash_a.strip().lower() == hash_b.strip().lower()
