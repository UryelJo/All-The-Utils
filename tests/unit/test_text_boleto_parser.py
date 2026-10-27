"""
Testes unitários rigorosos para validação e decodificação de boletos bancários (FEBRABAN).
Seguindo as Diretrizes de Qualidade Anti-Gambiarra.
"""
from datetime import date
from decimal import Decimal
import pytest
from wintoolbox.tools.text.boleto_parser.logic import (
    barras_to_linha_cobranca,
    calcular_mod10,
    calcular_mod11_bancario,
    decode_boleto,
    format_linha_digitavel,
    linha_to_barras_cobranca,
)


def test_mod10_and_mod11():
    """Valida algoritmos matemáticos dos módulos 10 e 11 FEBRABAN."""
    # Exemplo de mod10: bloco 341910900 -> cálculo de DV
    dv_mod10 = calcular_mod10("341910900")
    assert dv_mod10 == 8

    # Exemplo de mod11
    assert calcular_mod11_bancario("3419999900000150251090000000282110055774000") == 6


def test_decode_boleto_bancario_itau():
    """Valida decodificação exata de boleto bancário do Itaú."""
    # Linha digitável válida de 47 dígitos
    linha = "34191.09008 00000.282111 00557.740008 6 99990000015025"
    info = decode_boleto(linha)

    assert info.is_valid is True
    assert info.tipo == "COBRANCA"
    assert info.banco_codigo == "341"
    assert "Itaú" in info.banco_nome
    assert info.valor == Decimal("150.25")
    assert info.fator_vencimento == 9999
    assert isinstance(info.data_vencimento, date)
    assert len(info.codigo_barras) == 44
    assert info.erro_mensagem == ""


def test_bidirectional_conversion_cobranca():
    """Valida conversão bidirecional sem perda entre linha digitável e código de barras."""
    linha_orig = "34191090080000028211100557740008699990000015025"
    valid, barras, err = linha_to_barras_cobranca(linha_orig)
    assert valid is True
    assert len(barras) == 44

    # Reverte de barras para linha
    valid_rev, linha_revertida, err_rev = barras_to_linha_cobranca(barras)
    assert valid_rev is True
    assert linha_revertida == linha_orig


def test_invalid_dv_detection():
    """Valida que boletos com DVs adulterados são detectados e rejeitados."""
    # Altera o DV do primeiro campo de '8' para '7'
    linha_adulterada = "34191.09007 00000.282111 00557.740008 6 99990000015025"
    info = decode_boleto(linha_adulterada)
    assert info.is_valid is False
    assert "Dígito verificador do Campo 1 inválido" in info.erro_mensagem


def test_concessionaria_parser():
    """Valida decodificação de boletos de concessionárias e tributos (iniciados em 8)."""
    # 48 dígitos (Água / Saneamento: segmento 2)
    linha_concess = "826200000011 050001380004 000000000001 000000000002"
    info = decode_boleto(linha_concess)
    assert info.tipo == "CONCESSIONARIA"
    assert info.banco_codigo == "2"
    assert "Saneamento" in info.banco_nome


def test_format_linha_digitavel():
    """Valida formatação visual com pontos e blocos de espaços."""
    raw_47 = "34191090080000028211600557740004199990000015025"
    formatted = format_linha_digitavel(raw_47)
    assert formatted == "34191.09008 00000.282116 00557.740004 1 99990000015025"
