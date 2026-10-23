"""
Lógica pura da ferramenta Validador e Gerador de Documentos Brasileiros (CPF, CNPJ).
Implementa regras oficiais de módulo 11 da Receita Federal sem acoplamento a UI.
"""
import random
import re
from typing import Tuple


def validate_cpf(cpf: str) -> Tuple[bool, str]:
    """Valida o número de CPF utilizando o cálculo oficial dos dois dígitos verificadores."""
    digits = [int(c) for c in cpf if c.isdigit()]
    if len(digits) != 11:
        return False, "O CPF deve conter exatamente 11 dígitos numéricos."
    if len(set(digits)) == 1:
        return False, "CPF com todos os dígitos repetidos é inválido."

    # Primeiro dígito
    s = sum(d * w for d, w in zip(digits[:9], range(10, 1, -1)))
    d1 = (s * 10) % 11
    if d1 == 10:
        d1 = 0
    if d1 != digits[9]:
        return False, "Primeiro dígito verificador incorreto."

    # Segundo dígito
    s = sum(d * w for d, w in zip(digits[:10], range(11, 1, -1)))
    d2 = (s * 10) % 11
    if d2 == 10:
        d2 = 0
    if d2 != digits[10]:
        return False, "Segundo dígito verificador incorreto."

    return True, "CPF válido e verificado com sucesso!"


def validate_cnpj(cnpj: str) -> Tuple[bool, str]:
    """Valida o número de CNPJ utilizando os cálculos de módulo 11."""
    digits = [int(c) for c in cnpj if c.isdigit()]
    if len(digits) != 14:
        return False, "O CNPJ deve conter exatamente 14 dígitos numéricos."
    if len(set(digits)) == 1:
        return False, "CNPJ com todos os dígitos repetidos é inválido."

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s1 = sum(d * w for d, w in zip(digits[:12], w1))
    rem1 = s1 % 11
    d1 = 0 if rem1 < 2 else 11 - rem1
    if d1 != digits[12]:
        return False, "Primeiro dígito verificador incorreto."

    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s2 = sum(d * w for d, w in zip(digits[:13], w2))
    rem2 = s2 % 11
    d2 = 0 if rem2 < 2 else 11 - rem2
    if d2 != digits[13]:
        return False, "Segundo dígito verificador incorreto."

    return True, "CNPJ válido e verificado com sucesso!"


def generate_valid_cpf(formatted: bool = True) -> str:
    """Gera um CPF válido aleatório para fins de teste."""
    digits = [random.randint(0, 9) for _ in range(9)]
    s = sum(d * w for d, w in zip(digits, range(10, 1, -1)))
    d1 = (s * 10) % 11
    d1 = 0 if d1 == 10 else d1
    digits.append(d1)

    s = sum(d * w for d, w in zip(digits, range(11, 1, -1)))
    d2 = (s * 10) % 11
    d2 = 0 if d2 == 10 else d2
    digits.append(d2)

    raw = "".join(str(d) for d in digits)
    if formatted:
        return f"{raw[:3]}.{raw[3:6]}.{raw[6:9]}-{raw[9:]}"
    return raw


def generate_valid_cnpj(formatted: bool = True) -> str:
    """Gera um CNPJ válido aleatório com sufixo matriz 0001."""
    digits = [random.randint(0, 9) for _ in range(8)] + [0, 0, 0, 1]

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s1 = sum(d * w for d, w in zip(digits, w1))
    rem1 = s1 % 11
    d1 = 0 if rem1 < 2 else 11 - rem1
    digits.append(d1)

    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s2 = sum(d * w for d, w in zip(digits, w2))
    rem2 = s2 % 11
    d2 = 0 if rem2 < 2 else 11 - rem2
    digits.append(d2)

    raw = "".join(str(d) for d in digits)
    if formatted:
        return f"{raw[:2]}.{raw[2:5]}.{raw[5:8]}/{raw[8:12]}-{raw[12:]}"
    return raw


def format_document(text: str, doc_type: str) -> str:
    """Aplica a máscara padrão para CPF ou CNPJ."""
    nums = unformat_document(text)
    if doc_type.upper() == "CPF" and len(nums) == 11:
        return f"{nums[:3]}.{nums[3:6]}.{nums[6:9]}-{nums[9:]}"
    if doc_type.upper() == "CNPJ" and len(nums) == 14:
        return f"{nums[:2]}.{nums[2:5]}.{nums[5:8]}/{nums[8:12]}-{nums[12:]}"
    return text


def unformat_document(text: str) -> str:
    """Extrai somente os caracteres numéricos do documento."""
    return "".join(c for c in text if c.isdigit())
