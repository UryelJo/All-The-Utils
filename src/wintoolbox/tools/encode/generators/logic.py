"""
Lógica pura da ferramenta Gerador de Identificadores (UUID, ULID) e Senhas Seguras.
Sem acoplamento com interface gráfica.
"""
from typing import List
import secrets
import string
import time
import uuid

CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_ulid() -> str:
    """Gera um ULID compatível de 26 caracteres (timestamp 48-bit + 80-bit aleatório)."""
    ms = int(time.time() * 1000)
    t_chars = []
    for _ in range(10):
        t_chars.append(CROCKFORD_BASE32[ms % 32])
        ms //= 32
    time_part = "".join(reversed(t_chars))
    rand_part = "".join(secrets.choice(CROCKFORD_BASE32) for _ in range(16))
    return f"{time_part}{rand_part}"


def generate_secure_password(
    length: int = 16,
    use_upper: bool = True,
    use_lower: bool = True,
    use_digits: bool = True,
    use_special: bool = True,
) -> str:
    """Gera uma senha segura com entropia criptográfica."""
    chars = ""
    if use_upper:
        chars += string.ascii_uppercase
    if use_lower:
        chars += string.ascii_lowercase
    if use_digits:
        chars += string.digits
    if use_special:
        chars += "!@#$%&*-_=+?"

    if not chars:
        chars = string.ascii_letters + string.digits

    return "".join(secrets.choice(chars) for _ in range(length))


def generate_uuid_v4(uppercase: bool = False, hyphens: bool = True) -> str:
    """Gera um UUID versão 4 (completamente pseudoaleatório)."""
    u = uuid.uuid4()
    val = str(u) if hyphens else u.hex
    return val.upper() if uppercase else val.lower()


def generate_uuid_v1(uppercase: bool = False, hyphens: bool = True) -> str:
    """Gera um UUID versão 1 (baseado em tempo e nó)."""
    u = uuid.uuid1()
    val = str(u) if hyphens else u.hex
    return val.upper() if uppercase else val.lower()


def generate_batch(
    mode: str,
    count: int = 1,
    uppercase: bool = False,
    hyphens: bool = True,
    pwd_length: int = 16,
    pwd_upper: bool = True,
    pwd_lower: bool = True,
    pwd_digits: bool = True,
    pwd_special: bool = True,
) -> List[str]:
    """Gera uma lista de identificadores ou senhas em lote."""
    items: List[str] = []
    for _ in range(count):
        if mode == "UUID v4 (Aleatório)":
            items.append(generate_uuid_v4(uppercase=uppercase, hyphens=hyphens))
        elif mode == "UUID v1 (Baseado em Tempo)":
            items.append(generate_uuid_v1(uppercase=uppercase, hyphens=hyphens))
        elif mode == "ULID (Ordenável)":
            val = generate_ulid()
            items.append(val.upper() if uppercase else val.lower())
        elif mode == "Senha Segura":
            items.append(
                generate_secure_password(
                    length=pwd_length,
                    use_upper=pwd_upper,
                    use_lower=pwd_lower,
                    use_digits=pwd_digits,
                    use_special=pwd_special,
                )
            )
    return items
