"""
Lógica pura para análise estatística e métricas de legibilidade de textos.

Fornece:
- Contagem de caracteres (com e sem espaços)
- Contagem de palavras, linhas e parágrafos
- Contagem de frases e sílabas estimadas para português
- Tempo estimado de leitura silenciosa e oratória
- Métricas médias (tamanho de palavras, palavras por frase)
- Frequência de palavras com suporte a stopwords em português
- Índice de Facilidade de Leitura Flesch e Flesch-Brás (Martins et al.)

Isolado de qualquer biblioteca de interface gráfica.
"""
from dataclasses import dataclass, field
import math
import re
import unicodedata
from typing import Dict, List, Tuple


# Stopwords comuns em Língua Portuguesa
PORTUGUESE_STOPWORDS = {
    "a", "ao", "aos", "aquela", "aquelas", "aquele", "aqueles", "aquilo", "as", "à", "às",
    "até", "com", "como", "da", "das", "de", "dela", "delas", "dele", "deles", "depois",
    "do", "dos", "e", "é", "ela", "elas", "ele", "eles", "em", "entre", "era", "eram",
    "essa", "essas", "esse", "esses", "esta", "estas", "este", "estes", "eu", "foi",
    "fomos", "foram", "isso", "isto", "já", "lhe", "lhes", "mais", "mas", "me", "mesmo",
    "meu", "meus", "minha", "minhas", "muito", "na", "nas", "não", "nas", "no", "nos",
    "nós", "nossa", "nossas", "nosso", "nossos", "num", "numa", "o", "os", "ou", "para",
    "pela", "pelas", "pelo", "pelos", "por", "qual", "quando", "que", "quem", "se", "sem",
    "seu", "seus", "só", "sua", "suas", "também", "te", "tem", "temos", "têm", "teu",
    "teus", "tua", "tuas", "um", "uma", "você", "vocês", "vos"
}


@dataclass(frozen=True)
class TextStatsResult:
    """Resultado imutável da análise estatística textual."""
    char_count: int
    char_count_no_spaces: int
    word_count: int
    line_count: int
    non_empty_lines: int
    sentence_count: int
    paragraph_count: int
    syllable_count: int
    avg_word_length: float
    avg_sentence_length: float
    reading_time_seconds: int
    speaking_time_seconds: int
    flesch_reading_ease: float
    flesch_bras: float
    flesch_classification: str
    top_words: List[Tuple[str, int]] = field(default_factory=list)


def count_syllables_pt(word: str) -> int:
    """
    Estima a quantidade de sílabas em uma palavra em português através
    de agrupamentos de núcleos vocálicos e ditongos/tritongos.
    """
    w = word.lower().strip()
    if not w:
        return 0

    # Remove pontuações
    w = re.sub(r"[^a-zà-úâ-ûã-õä-ü]", "", w)
    if not w:
        return 0

    # Expressão que agrupa núcleos vocálicos (vogais e semivogais acentuadas ou não)
    # Ex: ditongos como 'ai', 'ou', 'ão', 'ei' etc. são contados como 1 núcleo silábico básico
    matches = re.findall(r"[a-zà-úâ-ûã-õä-ü]*?[aeiouyà-úâ-ûã-õä-ü]+", w)
    
    # Contagem básica por grupos vocálicos
    vowel_groups = re.findall(r"[aeiouyà-úâ-ûã-õä-ü]+", w)
    count = len(vowel_groups)
    
    return max(1, count)


def analyze_text(
    text: str,
    words_per_minute_reading: int = 200,
    words_per_minute_speaking: int = 130,
    top_n_words: int = 10,
    ignore_stopwords: bool = True
) -> TextStatsResult:
    """
    Executa a análise estatística completa sobre a string fornecida.
    """
    if not text:
        return TextStatsResult(
            char_count=0,
            char_count_no_spaces=0,
            word_count=0,
            line_count=0,
            non_empty_lines=0,
            sentence_count=0,
            paragraph_count=0,
            syllable_count=0,
            avg_word_length=0.0,
            avg_sentence_length=0.0,
            reading_time_seconds=0,
            speaking_time_seconds=0,
            flesch_reading_ease=100.0,
            flesch_bras=100.0,
            flesch_classification="Muito Fácil",
            top_words=[]
        )

    char_count = len(text)
    char_count_no_spaces = len(re.sub(r"\s+", "", text))

    # Linhas
    lines = text.splitlines()
    line_count = len(lines) if text else 0
    non_empty_lines = len([l for l in lines if l.strip()])

    # Parágrafos (blocos separados por quebras duplas ou linhas em branco)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    paragraph_count = max(1 if text.strip() else 0, len(paragraphs))

    # Palavras
    words = re.findall(r"\b[A-Za-z0-9À-ÖØ-öø-ÿ_-]+\b", text)
    word_count = len(words)

    # Frases (delimitadas por pontuação terminal . ! ? ou quebras de parágrafo)
    raw_sentences = re.split(r"[.!?]+(?:\s+|$)", text.strip())
    sentences = [s.strip() for s in raw_sentences if s.strip()]
    sentence_count = max(1 if word_count > 0 else 0, len(sentences))

    # Sílabas
    total_syllables = sum(count_syllables_pt(w) for w in words)

    # Médias
    if word_count > 0:
        total_letters = sum(len(w) for w in words)
        avg_word_length = round(total_letters / word_count, 2)
        avg_sentence_length = round(word_count / sentence_count, 2)
    else:
        avg_word_length = 0.0
        avg_sentence_length = 0.0

    # Tempos estimados
    if word_count > 0:
        reading_time_seconds = math.ceil((word_count / max(1, words_per_minute_reading)) * 60)
        speaking_time_seconds = math.ceil((word_count / max(1, words_per_minute_speaking)) * 60)
    else:
        reading_time_seconds = 0
        speaking_time_seconds = 0

    # Índices de Legibilidade
    # Flesch Reading Ease: 206.835 - 1.015 * (total_words / total_sentences) - 84.6 * (total_syllables / total_words)
    # Flesch-Brás (Martins et al. 1996): 248.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words)
    if word_count > 0 and sentence_count > 0:
        asl = word_count / sentence_count
        asw = total_syllables / word_count
        flesch_score = round(206.835 - (1.015 * asl) - (84.6 * asw), 2)
        flesch_bras_score = round(248.835 - (1.015 * asl) - (84.6 * asw), 2)
    else:
        flesch_score = 100.0
        flesch_bras_score = 100.0

    # Classificação Flesch
    if flesch_bras_score >= 75.0:
        flesch_class = "Muito Fácil (Ensino Fundamental 1)"
    elif flesch_bras_score >= 50.0:
        flesch_class = "Fácil (Ensino Fundamental 2)"
    elif flesch_bras_score >= 25.0:
        flesch_class = "Médio / Difícil (Ensino Médio)"
    else:
        flesch_class = "Muito Difícil / Acadêmico (Ensino Superior)"

    # Contagem de palavras mais frequentes
    freq_map: Dict[str, int] = {}
    for w in words:
        norm_w = w.lower()
        if ignore_stopwords and norm_w in PORTUGUESE_STOPWORDS:
            continue
        if len(norm_w) < 2 and not norm_w.isalnum():
            continue
        freq_map[norm_w] = freq_map.get(norm_w, 0) + 1

    sorted_freq = sorted(freq_map.items(), key=lambda item: (-item[1], item[0]))
    top_words = sorted_freq[:top_n_words]

    return TextStatsResult(
        char_count=char_count,
        char_count_no_spaces=char_count_no_spaces,
        word_count=word_count,
        line_count=line_count,
        non_empty_lines=non_empty_lines,
        sentence_count=sentence_count,
        paragraph_count=paragraph_count,
        syllable_count=total_syllables,
        avg_word_length=avg_word_length,
        avg_sentence_length=avg_sentence_length,
        reading_time_seconds=reading_time_seconds,
        speaking_time_seconds=speaking_time_seconds,
        flesch_reading_ease=flesch_score,
        flesch_bras=flesch_bras_score,
        flesch_classification=flesch_class,
        top_words=top_words
    )


def format_duration(seconds: int) -> str:
    """Formata segundos em representação amigável (ex: '2 min 15 s')."""
    if seconds <= 0:
        return "0 s"
    mins = seconds // 60
    secs = seconds % 60
    parts = []
    if mins > 0:
        parts.append(f"{mins} min")
    if secs > 0 or not parts:
        parts.append(f"{secs} s")
    return " ".join(parts)
