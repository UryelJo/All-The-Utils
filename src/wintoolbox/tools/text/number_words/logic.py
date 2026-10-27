"""
Lógica pura para conversão de números cardinais, ordinais e valores monetários (BRL)
para extenso em Português do Brasil.

Suporta:
- Números inteiros até quatrilhões
- Valores monetários em Real (singular/plural, centavos, conectivo 'de' em milhões/bilhões)
- Formato especial para cheques e contratos (# CEM REAIS #)
- Números ordinais masculinos e femininos (1º -> primeiro, 2ª -> segunda)

Isolado de qualquer biblioteca de interface gráfica.
"""
from decimal import Decimal, InvalidOperation
import math
import re
from typing import Tuple


UNIDADES = [
    "zero", "um", "dois", "três", "quatro", "cinco",
    "seis", "sete", "oito", "nove", "dez",
    "onze", "doze", "treze", "quatorze", "quinze",
    "dezesseis", "dezessete", "dezoito", "dezenove"
]

DEZENAS = [
    "", "", "vinte", "trinta", "quarenta", "cinquenta",
    "sessenta", "setenta", "oitenta", "noventa"
]

CENTENAS = [
    "", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos",
    "seiscentos", "setecentos", "oitocentos", "novecentos"
]

ESCALAS_CARDINAIS = [
    ("", ""),
    ("mil", "mil"),
    ("milhão", "milhões"),
    ("bilhão", "bilhões"),
    ("trilhão", "trilhões"),
    ("quatrilhão", "quatrilhões"),
]

ORDINAIS_UNIDADES_MASC = [
    "", "primeiro", "segundo", "terceiro", "quarto", "quinto",
    "sexto", "sétimo", "oitavo", "nono"
]

ORDINAIS_DEZENAS_MASC = [
    "", "décimo", "vigésimo", "trigésimo", "quadragésimo", "quinquagésimo",
    "sexagésimo", "septuagésimo", "octogésimo", "nonagésimo"
]

ORDINAIS_CENTENAS_MASC = [
    "", "centésimo", "ducentésimo", "trecentésimo", "quadringentésimo", "quingentésimo",
    "seiscentésimo", "septingentésimo", "octingentésimo", "nongentésimo"
]


def _triplet_to_words(n: int) -> str:
    """Converte um número de 0 a 999 em palavras."""
    if n == 0:
        return ""
    if n == 100:
        return "cem"

    parts = []
    c = n // 100
    d = (n % 100) // 10
    u = n % 10

    if c > 0:
        parts.append(CENTENAS[c])

    remainder = n % 100
    if remainder > 0:
        if remainder < 20:
            parts.append(UNIDADES[remainder])
        else:
            if d > 0:
                parts.append(DEZENAS[d])
            if u > 0:
                parts.append(UNIDADES[u])

    return " e ".join(parts)


def number_to_words(n: int) -> str:
    """
    Converte um número inteiro (positivo ou negativo) para extenso em português.
    """
    if n == 0:
        return "zero"

    if n < 0:
        return f"menos {number_to_words(abs(n))}"

    chunks = []
    temp = n
    scale_idx = 0

    while temp > 0:
        triplet = temp % 1000
        if triplet > 0:
            words = _triplet_to_words(triplet)
            sing, plur = ESCALAS_CARDINAIS[scale_idx]
            if scale_idx == 0:
                chunk_str = words
            elif scale_idx == 1:
                # Caso de "mil" (não dizemos "um mil", dizemos apenas "mil")
                chunk_str = "mil" if triplet == 1 else f"{words} mil"
            else:
                scale_word = sing if triplet == 1 else plur
                chunk_str = f"{words} {scale_word}"
            chunks.append(chunk_str)

        temp //= 1000
        scale_idx += 1

    chunks.reverse()

    if len(chunks) == 1:
        return chunks[0]

    # Regra gramatical de junção com "e":
    # Se o último grupo não-nulo for menor que 100 ou centena redonda (ex: 2.500.000 -> dois milhões e quinhentos mil),
    # ou se forem apenas 2 grupos e o último for menor que 100, une com "e"
    # Identifica o último triplet não-nulo
    temp_n = n
    last_non_zero_triplet = 0
    while temp_n > 0:
        t = temp_n % 1000
        if t > 0:
            last_non_zero_triplet = t
            break
        temp_n //= 1000

    if last_non_zero_triplet < 100 or (last_non_zero_triplet % 100 == 0):
        return ", ".join(chunks[:-1]) + " e " + chunks[-1]
    
    return ", ".join(chunks)


def currency_to_words(val: Decimal | float | int | str, cheque_format: bool = False) -> str:
    """
    Converte um valor monetário em reais brasileiros (BRL) por extenso.
    Ex: 1234.50 -> 'mil duzentos e trinta e quatro reais e cinquenta centavos'
    """
    try:
        if isinstance(val, str):
            # Limpa R$, espaços e converte pontuação brasileira para decimal standard
            clean_str = re.sub(r"[^\d,\.-]", "", val).strip()
            if "," in clean_str and "." in clean_str:
                clean_str = clean_str.replace(".", "").replace(",", ".")
            elif "," in clean_str:
                clean_str = clean_str.replace(",", ".")
            dec = Decimal(clean_str)
        else:
            dec = Decimal(str(val))
    except (InvalidOperation, ValueError):
        return ""

    if dec < 0:
        return f"menos {currency_to_words(abs(dec), cheque_format=cheque_format)}"

    # Arredonda para 2 casas decimais
    dec = dec.quantize(Decimal("0.01"))
    inteiro = int(dec)
    centavos = int((dec - Decimal(inteiro)) * 100)

    parts = []

    if inteiro > 0:
        words_int = number_to_words(inteiro)
        # Regra do "de reais": números terminados em milhão, bilhões sem centenas (ex: 2.000.000 -> dois milhões de reais)
        ends_with_million = inteiro >= 1_000_000 and (inteiro % 1_000_000 == 0)
        
        if inteiro == 1:
            currency_word = "real"
        elif ends_with_million:
            currency_word = "de reais"
        else:
            currency_word = "reais"

        parts.append(f"{words_int} {currency_word}")
    elif centavos == 0:
        return "# ZERO REAIS #" if cheque_format else "zero real"

    if centavos > 0:
        cent_words = number_to_words(centavos)
        cent_unit = "centavo" if centavos == 1 else "centavos"
        parts.append(f"{cent_words} {cent_unit}")

    result = " e ".join(parts)

    if cheque_format:
        return f"# {result.upper()} #"

    return result


def ordinal_to_words(n: int, feminine: bool = False) -> str:
    """
    Converte um número inteiro de 1 a 999 para numeral ordinal.
    Ex: 1 -> primeiro / primeira; 23 -> vigésimo terceiro / vigésima terceira.
    """
    if n <= 0 or n > 999:
        return str(n)

    c = n // 100
    d = (n % 100) // 10
    u = n % 10

    words = []
    if c > 0:
        words.append(ORDINAIS_CENTENAS_MASC[c])
    if d > 0:
        words.append(ORDINAIS_DEZENAS_MASC[d])
    if u > 0:
        words.append(ORDINAIS_UNIDADES_MASC[u])

    res = " ".join(words)
    if feminine:
        # Substitui a terminação 'o' por 'a' em ordinais regulares
        res = re.sub(r"o\b", "a", res)
    return res
