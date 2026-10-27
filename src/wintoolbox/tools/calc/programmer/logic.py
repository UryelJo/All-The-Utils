"""
Lógica pura da Calculadora do Programador (bases, operações bitwise e manipulação de bits).
Zero acoplamento com bibliotecas gráficas.
"""
from typing import Any, Dict, List

WORD_SIZES: Dict[str, int] = {
    "BYTE": 8,
    "WORD": 16,
    "DWORD": 32,
    "QWORD": 64
}


def get_mask(word_size: str = "DWORD") -> int:
    """Retorna a máscara de bits para o tamanho de palavra selecionado."""
    bits = WORD_SIZES.get(word_size.upper(), 32)
    return (1 << bits) - 1


def clamp_to_word(value: int, word_size: str = "DWORD") -> int:
    """Trunca o valor para os limites de bits do word_size (unsigned)."""
    mask = get_mask(word_size)
    return int(value) & mask


def to_signed(value: int, word_size: str = "DWORD") -> int:
    """Converte um valor unsigned para signed (complemento de dois)."""
    bits = WORD_SIZES.get(word_size.upper(), 32)
    unsigned = clamp_to_word(value, word_size)
    sign_bit = 1 << (bits - 1)
    if unsigned & sign_bit:
        return unsigned - (1 << bits)
    return unsigned


def to_unsigned(signed_value: int, word_size: str = "DWORD") -> int:
    """Converte um inteiro com sinal para representação unsigned truncada."""
    return clamp_to_word(signed_value, word_size)


def parse_programmer_value(text: str, default_base: int = 10, word_size: str = "DWORD") -> int:
    """
    Interpreta uma string de entrada numérica com suporte a prefixos 0x, 0b, 0o
    ou base explícita.
    """
    clean = text.strip().replace(" ", "").replace("_", "")
    if not clean:
        return 0

    if clean.startswith("0x") or clean.startswith("0X"):
        val = int(clean, 16)
    elif clean.startswith("0b") or clean.startswith("0B"):
        val = int(clean, 2)
    elif clean.startswith("0o") or clean.startswith("0O"):
        val = int(clean, 8)
    else:
        val = int(clean, default_base)

    return clamp_to_word(val, word_size)


def format_binary(value: int, word_size: str = "DWORD") -> str:
    """Formata representação binária dividida em nibbles de 4 bits."""
    bits = WORD_SIZES.get(word_size.upper(), 32)
    unsigned = clamp_to_word(value, word_size)
    bin_str = bin(unsigned)[2:].zfill(bits)
    # Agrupa de 4 em 4 bits da esquerda para a direita
    nibbles = [bin_str[i:i + 4] for i in range(0, bits, 4)]
    return " ".join(nibbles)


def format_all_bases(value: int, word_size: str = "DWORD") -> Dict[str, Any]:
    """Retorna representação em todas as bases e metadados."""
    bits = WORD_SIZES.get(word_size.upper(), 32)
    unsigned = clamp_to_word(value, word_size)
    signed = to_signed(unsigned, word_size)

    hex_digits = bits // 4
    oct_digits = (bits + 2) // 3

    return {
        "hex": hex(unsigned)[2:].upper().zfill(hex_digits),
        "dec_unsigned": str(unsigned),
        "dec_signed": str(signed),
        "oct": oct(unsigned)[2:].zfill(oct_digits),
        "bin": format_binary(unsigned, word_size),
        "bits": bits,
        "word_size": word_size.upper(),
        "raw_unsigned": unsigned,
        "raw_signed": signed
    }


def bitwise_and(a: int, b: int, word_size: str = "DWORD") -> int:
    """Operação Bitwise AND mascarada."""
    return clamp_to_word(a & b, word_size)


def bitwise_or(a: int, b: int, word_size: str = "DWORD") -> int:
    """Operação Bitwise OR mascarada."""
    return clamp_to_word(a | b, word_size)


def bitwise_xor(a: int, b: int, word_size: str = "DWORD") -> int:
    """Operação Bitwise XOR mascarada."""
    return clamp_to_word(a ^ b, word_size)


def bitwise_not(a: int, word_size: str = "DWORD") -> int:
    """Operação Bitwise NOT (inversão de bits) mascarada."""
    mask = get_mask(word_size)
    return clamp_to_word(~a, word_size)


def bitwise_shl(a: int, shift: int, word_size: str = "DWORD") -> int:
    """Shift Left lógico."""
    if shift < 0:
        return bitwise_shr(a, -shift, word_size)
    return clamp_to_word(a << shift, word_size)


def bitwise_shr(a: int, shift: int, word_size: str = "DWORD") -> int:
    """Shift Right lógico (zero-fill)."""
    if shift < 0:
        return bitwise_shl(a, -shift, word_size)
    val = clamp_to_word(a, word_size)
    return clamp_to_word(val >> shift, word_size)


def bitwise_sar(a: int, shift: int, word_size: str = "DWORD") -> int:
    """Shift Right aritmético (preserva bit de sinal)."""
    bits = WORD_SIZES.get(word_size.upper(), 32)
    signed = to_signed(a, word_size)
    if shift < 0:
        return bitwise_shl(a, -shift, word_size)
    res = signed >> shift
    return clamp_to_word(res, word_size)


def bitwise_rol(a: int, shift: int, word_size: str = "DWORD") -> int:
    """Rotação circular à esquerda (Rotate Left)."""
    bits = WORD_SIZES.get(word_size.upper(), 32)
    val = clamp_to_word(a, word_size)
    s = shift % bits
    if s == 0:
        return val
    res = ((val << s) | (val >> (bits - s)))
    return clamp_to_word(res, word_size)


def bitwise_ror(a: int, shift: int, word_size: str = "DWORD") -> int:
    """Rotação circular à direita (Rotate Right)."""
    bits = WORD_SIZES.get(word_size.upper(), 32)
    val = clamp_to_word(a, word_size)
    s = shift % bits
    if s == 0:
        return val
    res = ((val >> s) | (val << (bits - s)))
    return clamp_to_word(res, word_size)


def get_bit(value: int, bit_index: int) -> int:
    """Retorna o valor do bit (0 ou 1) na posição informada (0-indexado)."""
    if bit_index < 0:
        return 0
    return (int(value) >> bit_index) & 1


def set_bit(value: int, bit_index: int, bit_val: int, word_size: str = "DWORD") -> int:
    """Define o bit da posição informada para 0 ou 1."""
    bits = WORD_SIZES.get(word_size.upper(), 32)
    if bit_index < 0 or bit_index >= bits:
        return clamp_to_word(value, word_size)

    val = clamp_to_word(value, word_size)
    if bit_val:
        res = val | (1 << bit_index)
    else:
        res = val & ~(1 << bit_index)
    return clamp_to_word(res, word_size)


def toggle_bit(value: int, bit_index: int, word_size: str = "DWORD") -> int:
    """Inverte o bit na posição indicada (0 vira 1, 1 vira 0)."""
    bits = WORD_SIZES.get(word_size.upper(), 32)
    if bit_index < 0 or bit_index >= bits:
        return clamp_to_word(value, word_size)

    val = clamp_to_word(value, word_size)
    return clamp_to_word(val ^ (1 << bit_index), word_size)


def get_all_bits(value: int, word_size: str = "DWORD") -> List[int]:
    """Retorna lista de bits [b0, b1, ..., bN] do bit menos significativo para o mais significativo."""
    bits = WORD_SIZES.get(word_size.upper(), 32)
    val = clamp_to_word(value, word_size)
    return [(val >> i) & 1 for i in range(bits)]
