"""
Testes unitários rigorosos para a formatação e capitalização gramatical de nomes próprios e ABNT.
Seguindo as Diretrizes de Qualidade Anti-Gambiarra.
"""
import pytest
from wintoolbox.tools.text.name_formatter.logic import (
    format_abnt,
    format_name_pt,
    get_initials,
    get_short_name,
    process_names_batch,
)


def test_particles_and_capitalization_pt():
    """Valida preservação em minúsculas de preposições e partículas conformativas brasileiras."""
    assert format_name_pt("JOÃO DA SILVA") == "João da Silva"
    assert format_name_pt("JOAO DA SILVA") == "Joao da Silva"
    assert format_name_pt("maria de fatima dos santos") == "Maria de Fatima dos Santos"
    assert format_name_pt("PEDRO E PAULO DO AMARAL") == "Pedro e Paulo do Amaral"
    assert format_name_pt("LUIZ INACIO LULA DA SILVA") == "Luiz Inacio Lula da Silva"

    # Partículas no início ou fim não ficam minúsculas
    assert format_name_pt("DE SOUZA") == "De Souza"


def test_roman_numerals_and_apostrophes():
    """Valida numerais romanos e nomes com apóstrofo e hífen."""
    assert format_name_pt("dom pedro ii") == "Dom Pedro II"
    assert format_name_pt("henrique viii") == "Henrique VIII"
    assert format_name_pt("carlos eduardo d'avila") == "Carlos Eduardo D'Avila"
    assert format_name_pt("jean-luc godard") == "Jean-Luc Godard"


def test_abnt_citation():
    """Valida geração de citações no padrão bibliográfico ABNT."""
    assert format_abnt("João Carlos da Silva") == "SILVA, João Carlos da"
    assert format_abnt("Ana Paula de Souza") == "SOUZA, Ana Paula de"

    # Sufixos de parentesco: o sobrenome na ABNT agrega o sufixo (ex: CABRAL NETO)
    assert format_abnt("Pedro Álvares Cabral Neto") == "CABRAL NETO, Pedro Álvares"
    assert format_abnt("Carlos Eduardo Pereira Filho") == "PEREIRA FILHO, Carlos Eduardo"

    # Nome simples (apenas 1 palavra)
    assert format_abnt("Aristóteles") == "ARISTÓTELES"


def test_short_name_and_initials():
    """Valida extração de primeiro/último nome e iniciais limpas."""
    assert get_short_name("João Carlos da Silva") == "João Silva"
    assert get_short_name("Pedro Álvares Cabral Neto") == "Pedro Cabral Neto"

    assert get_initials("João Carlos da Silva") == "J. C. S."
    assert get_initials("Maria de Fátima dos Santos") == "M. F. S."


def test_batch_processing_and_whitespace():
    """Valida higienização de múltiplos espaços em branco e processamento em lote."""
    raw = "   joao    da    silva   \n\n  MARIA   SOUZA  \n"
    res = process_names_batch(raw)
    assert len(res) == 2
    assert res[0].capitalized == "Joao da Silva"
    assert res[1].capitalized == "Maria Souza"
