"""
Testes unitários rigorosos para conversão de números e valores em reais para extenso.
Seguindo as Diretrizes de Qualidade Anti-Gambiarra.
"""
from decimal import Decimal
import pytest
from wintoolbox.tools.text.number_words.logic import (
    currency_to_words,
    number_to_words,
    ordinal_to_words,
)


def test_cardinal_numbers_exact():
    """Valida conversão exata de números inteiros para palavras."""
    assert number_to_words(0) == "zero"
    assert number_to_words(1) == "um"
    assert number_to_words(14) == "quatorze"
    assert number_to_words(21) == "vinte e um"
    assert number_to_words(100) == "cem"
    assert number_to_words(101) == "cento e um"
    assert number_to_words(250) == "duzentos e cinquenta"
    assert number_to_words(1000) == "mil"
    assert number_to_words(1005) == "mil e cinco"
    assert number_to_words(1234) == "mil, duzentos e trinta e quatro"
    assert number_to_words(1000000) == "um milhão"
    assert number_to_words(2500000) == "dois milhões e quinhentos mil"
    assert number_to_words(-42) == "menos quarenta e dois"


def test_currency_brl_exact():
    """Valida conversão monetária em Reais e Centavos."""
    # Valores elementares
    assert currency_to_words(0) == "zero real"
    assert currency_to_words("0,01") == "um centavo"
    assert currency_to_words("0,50") == "cinquenta centavos"
    assert currency_to_words(1) == "um real"
    assert currency_to_words("1,00") == "um real"
    assert currency_to_words("1,01") == "um real e um centavo"
    assert currency_to_words("2,00") == "dois reais"
    assert currency_to_words("2,50") == "dois reais e cinquenta centavos"

    # Valores compostos comuns
    assert currency_to_words("1234,50") == "mil, duzentos e trinta e quatro reais e cinquenta centavos"
    assert currency_to_words("R$ 1.250,00") == "mil, duzentos e cinquenta reais"
    assert currency_to_words("R$ 1.200,00") == "mil e duzentos reais"

    # Regra do "de reais" para milhões e bilhões redondos
    assert currency_to_words(1_000_000) == "um milhão de reais"
    assert currency_to_words(2_000_000) == "dois milhões de reais"
    # Quando não é redondo, não usa "de reais"
    assert currency_to_words("1000001") == "um milhão e um reais"

    # Formato de Cheque
    cheque = currency_to_words("150,25", cheque_format=True)
    assert cheque == "# CENTO E CINQUENTA REAIS E VINTE E CINCO CENTAVOS #"

    # Negativos
    assert currency_to_words("-10,00") == "menos dez reais"


def test_ordinal_numbers():
    """Valida conversão de ordinais masculinos e femininos."""
    assert ordinal_to_words(1) == "primeiro"
    assert ordinal_to_words(1, feminine=True) == "primeira"
    assert ordinal_to_words(2) == "segundo"
    assert ordinal_to_words(2, feminine=True) == "segunda"
    assert ordinal_to_words(23) == "vigésimo terceiro"
    assert ordinal_to_words(23, feminine=True) == "vigésima terceira"
    assert ordinal_to_words(100) == "centésimo"
    assert ordinal_to_words(154) == "centésimo quinquagésimo quarto"
    assert ordinal_to_words(0) == "0"
    assert ordinal_to_words(1000) == "1000"


def test_currency_invalid_input():
    """Valida que entradas malformadas não quebram o sistema."""
    assert currency_to_words("texto_invalido") == ""
    assert currency_to_words("") == ""
