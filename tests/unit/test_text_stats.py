"""
Testes unitários rigorosos para a lógica de estatísticas textuais e legibilidade.
Seguindo as Diretrizes de Qualidade Anti-Gambiarra (testes determinísticos e exatos).
"""
import pytest
from wintoolbox.tools.text.stats.logic import (
    analyze_text,
    count_syllables_pt,
    format_duration,
    TextStatsResult,
)


def test_stats_empty_and_whitespace():
    """Valida comportamento determinístico para strings vazias e com apenas espaços."""
    res_empty = analyze_text("")
    assert res_empty.char_count == 0
    assert res_empty.char_count_no_spaces == 0
    assert res_empty.word_count == 0
    assert res_empty.line_count == 0
    assert res_empty.non_empty_lines == 0
    assert res_empty.sentence_count == 0
    assert res_empty.paragraph_count == 0
    assert res_empty.syllable_count == 0
    assert res_empty.reading_time_seconds == 0
    assert res_empty.speaking_time_seconds == 0
    assert res_empty.flesch_bras == 100.0
    assert res_empty.top_words == []

    res_spaces = analyze_text("   \n\n\t  ")
    assert res_spaces.char_count == 8
    assert res_spaces.char_count_no_spaces == 0
    assert res_spaces.word_count == 0
    assert res_spaces.non_empty_lines == 0
    assert res_spaces.paragraph_count == 0


def test_stats_exact_counts_happy_path():
    """Valida contagens exatas de palavras, caracteres, linhas e frases."""
    sample = "O rato roeu a roupa do rei de Roma.\nO gato pegou o rato!"
    res = analyze_text(sample, words_per_minute_reading=200, words_per_minute_speaking=100)

    # Contagem exata de caracteres
    assert res.char_count == len(sample)
    assert res.char_count_no_spaces == len("OratoroeuaroupadoreideRoma.Ogatopegouorato!")
    assert res.word_count == 14  # O(1) rato(2) roeu(3) a(4) roupa(5) do(6) rei(7) de(8) Roma(9) O(10) gato(11) pegou(12) o(13) rato(14)
    assert res.line_count == 2
    assert res.non_empty_lines == 2
    assert res.sentence_count == 2
    assert res.paragraph_count == 1

    # Validação de stopwords e top_words
    # "rato" aparece 2 vezes; stopwords como "o", "a", "do", "de" são ignoradas
    top_dict = dict(res.top_words)
    assert top_dict.get("rato") == 2
    assert "de" not in top_dict


def test_stats_flesch_and_syllables():
    """Valida contagem de sílabas e cálculo do Flesch-Brás."""
    # "computador": com-pu-ta-dor -> 4 sílabas
    assert count_syllables_pt("computador") == 4
    # "paralelepípedo": pa-ra-le-le-pí-pe-do -> 7 sílabas
    assert count_syllables_pt("paralelepípedo") == 7
    # "sol": 1 sílaba
    assert count_syllables_pt("sol") == 1

    text = "O sol brilha no céu azul da manhã."
    res = analyze_text(text)
    assert res.word_count == 8
    assert res.sentence_count == 1
    assert res.syllable_count > 0
    assert isinstance(res.flesch_bras, float)
    assert res.flesch_bras <= 248.835


def test_format_duration():
    """Valida formatação amigável de durações."""
    assert format_duration(0) == "0 s"
    assert format_duration(45) == "45 s"
    assert format_duration(60) == "1 min"
    assert format_duration(125) == "2 min 5 s"
