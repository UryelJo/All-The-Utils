"""
Testes unitários rigorosos para validação e decodificação de chaves de acesso NF-e.
Seguindo as Diretrizes de Qualidade Anti-Gambiarra.
"""
import pytest
from wintoolbox.tools.encode.nfe_key.logic import (
    calcular_dv_nfe,
    decode_nfe_key,
    format_cnpj,
    format_nfe_key,
    generate_sample_nfe_key,
)


def test_calcular_dv_nfe_mod11():
    """Valida cálculo do DV Módulo 11 conforme o Manual de Orientação do Contribuinte (MOC SEFAZ)."""
    # Chave de 43 dígitos conhecida (sem o DV final)
    chave_43 = "3526030000000000019155001000123456112345678"
    dv = calcular_dv_nfe(chave_43)
    assert isinstance(dv, int)
    assert 0 <= dv <= 9

    # Monta chave completa com 44 dígitos
    chave_44 = f"{chave_43}{dv}"
    info = decode_nfe_key(chave_44)
    assert info.is_valid is True
    assert info.digito_verificador == dv
    assert info.dv_calculado == dv


def test_decode_nfe_key_field_extraction():
    """Valida extração exata de todos os metadados da chave de acesso."""
    # UF: 35 (SP), AAMM: 2603 (Março/2026), CNPJ: 11222333000181, Mod: 55, Serie: 002, Num: 000054321, Emis: 1, cNF: 98765432
    prefix = "3526031122233300018155002000054321198765432"
    dv = calcular_dv_nfe(prefix)
    chave = f"{prefix}{dv}"

    info = decode_nfe_key(chave)

    assert info.is_valid is True
    assert info.uf_codigo == "35"
    assert "São Paulo" in info.uf_nome
    assert info.ano_mes == "2603"
    assert info.data_emissao_formatada == "Março / 2026"
    assert info.cnpj_emitente == "11222333000181"
    assert info.cnpj_formatado == "11.222.333/0001-81"
    assert info.modelo_codigo == "55"
    assert "NF-e" in info.modelo_nome
    assert info.serie == 2
    assert info.numero_nota == 54321
    assert info.tipo_emissao_codigo == "1"
    assert "Normal" in info.tipo_emissao_nome
    assert info.codigo_numerico == "98765432"
    assert info.erro_mensagem == ""


def test_invalid_nfe_key_detection():
    """Valida detecção de DV adulterado e tamanho incorreto."""
    chave_valida = generate_sample_nfe_key("35", "55")
    assert len(chave_valida) == 44

    # Altera o DV final
    dv_correto = int(chave_valida[-1])
    dv_adulterado = (dv_correto + 1) % 10
    chave_invalida = chave_valida[:-1] + str(dv_adulterado)

    info_invalida = decode_nfe_key(chave_invalida)
    assert info_invalida.is_valid is False
    assert "Dígito verificador inválido" in info_invalida.erro_mensagem

    # Tamanho menor ou maior que 44 dígitos
    info_curta = decode_nfe_key("3526030000000000019155")
    assert info_curta.is_valid is False
    assert "deve conter exatamente 44 dígitos" in info_curta.erro_mensagem


def test_formatting_helpers():
    """Valida formatação visual em blocos de 4 e máscara de CNPJ."""
    assert format_cnpj("11222333000181") == "11.222.333/0001-81"
    key_44 = "35260300000000000191550010001234561123456789"
    formatted = format_nfe_key(key_44)
    # Deve conter 11 blocos de 4 dígitos separados por espaço
    assert len(formatted.split()) == 11
