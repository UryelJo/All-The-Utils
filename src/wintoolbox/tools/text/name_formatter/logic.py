"""
Lógica pura para formatação e capitalização gramatical de nomes próprios em Português do Brasil.

Regras atendidas:
- Capitalização de prenomes e sobrenomes
- Preservação em minúsculo de partículas de ligação (de, da, do, dos, das, e, d', van, von, del)
- Preservação em maiúsculo de numerais romanos (I, II, III, IV, V, VI, etc.)
- Tratamento de apóstrofos (D'Ávila, O'Connor) e hífens (Maria-Helena)
- Geração de formatos derivados: Citação bibliográfica ABNT, Primeiro/Último nome e Iniciais

Isolado de qualquer biblioteca de interface gráfica.
"""
from dataclasses import dataclass
import re
from typing import List, Tuple


# Partículas de ligação que devem permanecer em minúsculas
LOWERCASE_PARTICLES = {
    "de", "da", "do", "das", "dos", "e", "em", "del", "van", "von", "di"
}

# Numerais romanos comuns usados em nomes e títulos
ROMAN_NUMERALS = {
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"
}

# Sufixos de parentesco que não devem ser considerados último sobrenome isolado na ABNT
FAMILY_SUFFIXES = {
    "filho", "filha", "junior", "júnior", "neto", "neta", "sobrinho", "sobrinha"
}


@dataclass(frozen=True)
class FormattedName:
    """Representação estruturada das variantes de um nome próprio formatado."""
    original: str
    capitalized: str
    abnt: str
    short_name: str
    initials: str


def _capitalize_part(word: str) -> str:
    """Capitaliza uma palavra individual respeitando apóstrofos e hífens internos."""
    w_low = word.lower()

    # Numerais romanos
    if w_low in ROMAN_NUMERALS:
        return w_low.upper()

    # Partículas com apóstrofo (ex: d'avila -> D'Ávila)
    if "'" in word or "’" in word:
        apostrophe = "'" if "'" in word else "’"
        subparts = word.split(apostrophe)
        capitalized_subs = [
            s.lower() if s.lower() in LOWERCASE_PARTICLES else s.capitalize()
            for s in subparts
        ]
        return apostrophe.join(capitalized_subs)

    # Nomes com hífen (ex: jean-luc -> Jean-Luc)
    if "-" in word:
        subparts = word.split("-")
        return "-".join(s.capitalize() for s in subparts)

    return word.capitalize()


def format_name_pt(name: str) -> str:
    """
    Formata um nome próprio conforme as normas gramaticais brasileiras.
    Ex: 'JOAO DA SILVA' -> 'João da Silva'
    """
    clean_name = re.sub(r"\s+", " ", name.strip())
    if not clean_name:
        return ""

    words = clean_name.split()
    total = len(words)
    formatted_words = []

    for idx, word in enumerate(words):
        w_low = word.lower()

        # A primeira e a última palavra nunca ficam em minúsculas
        if idx == 0 or idx == total - 1:
            formatted_words.append(_capitalize_part(word))
        elif w_low in LOWERCASE_PARTICLES:
            formatted_words.append(w_low)
        else:
            formatted_words.append(_capitalize_part(word))

    return " ".join(formatted_words)


def format_abnt(name: str) -> str:
    """
    Gera a citação bibliográfica no padrão ABNT.
    Ex: 'João Carlos da Silva' -> 'SILVA, João Carlos da'
    Ex: 'Pedro Álvares Cabral Neto' -> 'CABRAL NETO, Pedro Álvares'
    """
    formatted = format_name_pt(name)
    if not formatted:
        return ""

    parts = formatted.split()
    if len(parts) == 1:
        return parts[0].upper()

    last_part_low = parts[-1].lower()

    # Se o último nome for sufixo de parentesco (Neto, Filho, Júnior), agrega o penúltimo
    if last_part_low in FAMILY_SUFFIXES and len(parts) >= 3:
        surname = f"{parts[-2]} {parts[-1]}".upper()
        forenames = " ".join(parts[:-2])
    else:
        surname = parts[-1].upper()
        forenames = " ".join(parts[:-1])

    return f"{surname}, {forenames}"


def get_short_name(name: str) -> str:
    """Retorna o primeiro e o último nome (ex: 'João Silva')."""
    formatted = format_name_pt(name)
    if not formatted:
        return ""
    parts = formatted.split()
    if len(parts) <= 2:
        return formatted

    last_low = parts[-1].lower()
    if last_low in FAMILY_SUFFIXES and len(parts) >= 3:
        return f"{parts[0]} {parts[-2]} {parts[-1]}"

    return f"{parts[0]} {parts[-1]}"


def get_initials(name: str) -> str:
    """Retorna as iniciais do nome, ignorando partículas de ligação (ex: 'João da Silva' -> 'J. S.')."""
    formatted = format_name_pt(name)
    if not formatted:
        return ""
    parts = formatted.split()
    initials = [
        f"{p[0]}." for p in parts if p.lower() not in LOWERCASE_PARTICLES and p
    ]
    return " ".join(initials)


def process_name(raw_name: str) -> FormattedName:
    """Retorna todas as variantes de formatação para um nome."""
    cap = format_name_pt(raw_name)
    abnt = format_abnt(raw_name)
    short = get_short_name(raw_name)
    ini = get_initials(raw_name)
    return FormattedName(
        original=raw_name.strip(),
        capitalized=cap,
        abnt=abnt,
        short_name=short,
        initials=ini,
    )


def process_names_batch(names_text: str) -> List[FormattedName]:
    """Processa múltiplas linhas de nomes."""
    lines = [line.strip() for line in names_text.splitlines() if line.strip()]
    return [process_name(line) for line in lines]
