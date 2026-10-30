"""Núcleo puro de quebra de cifras clássicas (sem Qt).

Implementa análise de frequência em português, quebra de César por
qui-quadrado, detecção de tamanho de chave por índice de coincidência,
Kasiski com MDC das distâncias, quebra de Vigenère coluna a coluna e
substituição simples por escalada de colina (hill climbing) guiada por
frequências de letras e bigramas do português.

Nenhuma função aqui depende de Qt, numpy, scipy ou sympy.
"""
from __future__ import annotations

import math
import random
import unicodedata
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
INDICE_LETRA = {letra: indice for indice, letra in enumerate(LETRAS)}

# Frequências aproximadas das letras em português (percentual).
FREQUENCIA_LETRAS_PT: Dict[str, float] = {
    "A": 14.63,
    "B": 1.04,
    "C": 3.88,
    "D": 4.99,
    "E": 12.57,
    "F": 1.02,
    "G": 1.30,
    "H": 1.28,
    "I": 6.18,
    "J": 0.40,
    "K": 0.02,
    "L": 2.78,
    "M": 4.74,
    "N": 5.05,
    "O": 10.73,
    "P": 2.52,
    "Q": 1.20,
    "R": 6.53,
    "S": 7.81,
    "T": 4.34,
    "U": 4.63,
    "V": 1.67,
    "W": 0.01,
    "X": 0.21,
    "Y": 0.01,
    "Z": 0.47,
}

# Bigramas frequentes em português (peso aproximado, sem normalização rígida).
BIGRAMAS_PT: Dict[str, float] = {
    "de": 3.10, "os": 1.90, "as": 1.85, "ar": 1.60, "es": 1.60, "do": 1.50,
    "da": 1.50, "co": 1.40, "ra": 1.40, "ao": 1.30, "re": 1.30, "qu": 1.30,
    "ue": 1.20, "en": 1.20, "te": 1.20, "se": 1.10, "al": 1.10, "nt": 1.10,
    "em": 1.10, "ma": 1.00, "no": 1.00, "na": 1.00, "an": 1.00, "am": 0.95,
    "ca": 0.90, "it": 0.90, "is": 0.90, "or": 0.90, "ta": 0.90, "to": 0.90,
    "ia": 0.85, "er": 0.85, "ir": 0.80, "me": 0.80, "mo": 0.80, "po": 0.80,
    "ro": 0.80, "so": 0.80, "ss": 0.75, "st": 0.75, "tr": 0.75, "pr": 0.75,
    "br": 0.70, "cr": 0.70, "fr": 0.60, "gr": 0.60, "dr": 0.55, "ch": 0.65,
    "lh": 0.45, "nh": 0.55, "rr": 0.45, "sc": 0.45, "mp": 0.55, "mb": 0.45,
    "nd": 0.55, "ng": 0.40, "nc": 0.45, "ns": 0.60, "ei": 0.60, "ou": 0.70,
    "ai": 0.55, "oi": 0.45, "eu": 0.50, "ui": 0.45, "li": 0.75, "lo": 0.75,
    "la": 0.85, "le": 0.75, "lu": 0.35, "ve": 0.60, "vi": 0.55, "va": 0.65,
    "vo": 0.55, "ce": 0.70, "ci": 0.60, "om": 0.55, "um": 0.65, "un": 0.45,
    "ha": 0.45, "he": 0.35, "ho": 0.40, "ja": 0.18, "ge": 0.30, "gi": 0.25,
    "gu": 0.45, "xa": 0.08, "ex": 0.35, "ze": 0.15, "za": 0.15, "zo": 0.12,
    "fa": 0.35, "fe": 0.35, "fi": 0.35, "fo": 0.40, "fu": 0.20, "pa": 0.65,
    "pe": 0.65, "pi": 0.55, "pu": 0.35, "ba": 0.55, "be": 0.55, "bi": 0.35,
    "bo": 0.50, "bu": 0.25, "ti": 0.70, "tu": 0.55, "di": 0.60, "du": 0.40,
    "ni": 0.55, "nu": 0.30, "mi": 0.60, "mu": 0.45, "si": 0.60, "su": 0.55,
    "sa": 0.75,
}

_PESO_TOTAL_BIGRAMAS = sum(valor for valor in BIGRAMAS_PT.values() if valor > 0)
_PROB_BIGRAMA_COBERTA = 0.88
_PROB_BIGRAMA_PADRAO = (1.0 - _PROB_BIGRAMA_COBERTA) / (26 * 26)

LOG_FREQ_LETRA: Dict[str, float] = {
    letra: math.log(max(FREQUENCIA_LETRAS_PT[letra], 0.005) / 100.0) for letra in LETRAS
}

LOG_BIGRAMA: Dict[str, float] = {}
for _par, _peso in BIGRAMAS_PT.items():
    if _peso <= 0 or len(_par) != 2:
        continue
    LOG_BIGRAMA[_par] = math.log(_peso / _PESO_TOTAL_BIGRAMAS * _PROB_BIGRAMA_COBERTA)
for _a in LETRAS:
    for _b in LETRAS:
        LOG_BIGRAMA.setdefault(_a + _b, math.log(_PROB_BIGRAMA_PADRAO))

LOG_BIGRAMA_MATRIZ: List[List[float]] = [
    [LOG_BIGRAMA[_a + _b] for _b in LETRAS] for _a in LETRAS
]


# ---------------------------------------------------------------------------
# Normalização e estatísticas
# ---------------------------------------------------------------------------
def remover_acentos(texto: str) -> str:
    """Remove acentos preservando as letras base."""
    decomposto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(caractere for caractere in decomposto if unicodedata.category(caractere) != "Mn")


def normalizar(texto: str) -> str:
    """Mantém apenas letras A-Z, sem acentos e em maiúsculas."""
    return "".join(caractere for caractere in remover_acentos(texto).upper() if "A" <= caractere <= "Z")


def aplicar_cesar(texto: str, deslocamento: int) -> str:
    """Aplica (ou desfaz) um deslocamento de César preservando maiúsculas e pontuação."""
    deslocamento = int(deslocamento) % 26
    saida: List[str] = []
    for caractere in str(texto or ""):
        base = remover_acentos(caractere).upper()
        if len(base) == 1 and "A" <= base <= "Z":
            novo = LETRAS[(INDICE_LETRA[base] + deslocamento) % 26]
            saida.append(novo if caractere.isupper() else novo.lower())
        else:
            saida.append(caractere)
    return "".join(saida)


def contar_letras(texto: str) -> Dict[str, int]:
    """Contagem de cada letra A-Z no texto normalizado."""
    contagem = Counter(normalizar(texto))
    return {letra: int(contagem.get(letra, 0)) for letra in LETRAS}


def indice_coincidencia(texto: str) -> float:
    """Índice de coincidência de Friedman (0,066 a 0,075 em português)."""
    normalizado = normalizar(texto)
    total = len(normalizado)
    if total < 2:
        return 0.0
    contagem = Counter(normalizado)
    soma = sum(quantidade * (quantidade - 1) for quantidade in contagem.values())
    return soma / (total * (total - 1))


def frequencia_letras(texto: str) -> List[Dict[str, Any]]:
    """Tabela de frequência por letra com comparativo em português."""
    normalizado = normalizar(texto)
    total = len(normalizado) or 1
    contagem = Counter(normalizado)
    linhas: List[Dict[str, Any]] = []
    for letra in LETRAS:
        quantidade = int(contagem.get(letra, 0))
        linhas.append(
            {
                "letra": letra,
                "ocorrencias": quantidade,
                "percentual": quantidade / total * 100.0,
                "esperado_pt": FREQUENCIA_LETRAS_PT[letra],
            }
        )
    linhas.sort(key=lambda item: item["ocorrencias"], reverse=True)
    return linhas


def estatisticas_texto(texto: str) -> Dict[str, Any]:
    """Resumo estrutural do texto analisado."""
    bruto = str(texto or "")
    normalizado = normalizar(bruto)
    palavras = [palavra for palavra in remover_acentos(bruto).split() if palavra]
    contagem = Counter(normalizado)
    mais_comuns = contagem.most_common(8)
    return {
        "caracteres": len(bruto),
        "letras": len(normalizado),
        "palavras": len(palavras),
        "letras_distintas": len(contagem),
        "indice_coincidencia": indice_coincidencia(bruto),
        "mais_comuns": [{"letra": letra, "ocorrencias": qtd} for letra, qtd in mais_comuns],
    }


# ---------------------------------------------------------------------------
# César
# ---------------------------------------------------------------------------
def _qui_quadrado_da_distribuicao(contagem: Sequence[int]) -> float:
    """Qui-quadrado entre uma contagem observada de 26 letras e o esperado em português."""
    total = sum(contagem)
    if total <= 0:
        return float("inf")
    estatistica = 0.0
    for indice, letra in enumerate(LETRAS):
        esperado = FREQUENCIA_LETRAS_PT[letra] / 100.0 * total
        if esperado <= 0:
            continue
        estatistica += (contagem[indice] - esperado) ** 2 / esperado
    return estatistica


def _contagem_ordenada(texto: str) -> List[int]:
    contagem = [0] * 26
    for caractere in normalizar(texto):
        contagem[INDICE_LETRA[caractere]] += 1
    return contagem


def quebrar_cesar(texto: str) -> Dict[str, Any]:
    """Testa os 26 deslocamentos e escolhe o mais compatível com o português."""
    normalizado = normalizar(texto)
    if len(normalizado) < 4:
        raise ValueError("Texto curto demais para a análise de César (mínimo de 4 letras).")
    contagem = _contagem_ordenada(texto)
    ranking: List[Dict[str, Any]] = []
    for deslocamento in range(26):
        # Ao decifrar com ``deslocamento``, a letra cifrada i vira (i - deslocamento)
        distribuicao = [0] * 26
        for indice in range(26):
            distribuicao[(indice - deslocamento) % 26] += contagem[indice]
        pontuacao = _qui_quadrado_da_distribuicao(distribuicao)
        ranking.append(
            {
                "deslocamento": deslocamento,
                "qui_quadrado": pontuacao,
                "texto": aplicar_cesar(texto, -deslocamento),
            }
        )
    ranking.sort(key=lambda item: item["qui_quadrado"])
    melhor = ranking[0]
    return {
        "deslocamento": melhor["deslocamento"],
        "qui_quadrado": melhor["qui_quadrado"],
        "texto": melhor["texto"],
        "ranking": ranking[:10],
        "rot13": aplicar_cesar(texto, 13),
    }


# ---------------------------------------------------------------------------
# Kasiski e índice de coincidência
# ---------------------------------------------------------------------------
def _divisores(valor: int, maximo: int) -> List[int]:
    return [numero for numero in range(2, maximo + 1) if numero <= valor and valor % numero == 0]


def kasiski(
    texto: str,
    tamanho_minimo: int = 3,
    maximo_chave: int = 20,
    maximo_sequencias: int = 15,
) -> Dict[str, Any]:
    """Busca sequências repetidas e usa o MDC das distâncias para sugerir o tamanho da chave."""
    normalizado = normalizar(texto)
    if len(normalizado) < tamanho_minimo * 2:
        return {"sequencias": [], "candidatos": [], "observacao": "Texto curto para Kasiski."}

    posicoes: Dict[str, List[int]] = {}
    for tamanho in range(tamanho_minimo, tamanho_minimo + 3):
        if len(normalizado) < tamanho * 2:
            continue
        for inicio in range(len(normalizado) - tamanho + 1):
            trecho = normalizado[inicio : inicio + tamanho]
            lista = posicoes.setdefault(trecho, [])
            lista.append(inicio)

    votos: Counter = Counter()
    sequencias: List[Dict[str, Any]] = []
    for trecho, lista_posicoes in posicoes.items():
        if len(lista_posicoes) < 2:
            continue
        distancias = [b - a for a, b in zip(lista_posicoes, lista_posicoes[1:])]
        if not distancias:
            continue
        mdc_distancias = 0
        for distancia in distancias:
            mdc_distancias = math.gcd(mdc_distancias, distancia)
        if mdc_distancias < 2:
            continue
        sequencias.append(
            {
                "trecho": trecho,
                "ocorrencias": len(lista_posicoes),
                "posicoes": lista_posicoes[:10],
                "distancias": distancias[:10],
                "mdc": mdc_distancias,
            }
        )
        for candidato in _divisores(mdc_distancias, maximo_chave):
            votos[candidato] += 1

    sequencias.sort(key=lambda item: (item["ocorrencias"], len(item["trecho"])), reverse=True)
    candidatos = [
        {"tamanho": tamanho, "votos": quantidade}
        for tamanho, quantidade in votos.most_common(10)
    ]
    return {
        "sequencias": sequencias[:maximo_sequencias],
        "candidatos": candidatos,
        "observacao": "" if sequencias else "Nenhuma repetição útil encontrada.",
    }


def detectar_tamanho_chave(texto: str, maximo: int = 20) -> List[Dict[str, Any]]:
    """Calcula o índice de coincidência médio das colunas para cada tamanho de chave."""
    normalizado = normalizar(texto)
    resultados: List[Dict[str, Any]] = []
    if len(normalizado) < 8:
        return resultados
    limite = max(1, min(int(maximo), len(normalizado) // 2))
    for tamanho in range(1, limite + 1):
        colunas = [normalizado[indice::tamanho] for indice in range(tamanho)]
        indices = [indice_coincidencia(coluna) for coluna in colunas if len(coluna) >= 2]
        media = sum(indices) / len(indices) if indices else 0.0
        resultados.append(
            {
                "tamanho": tamanho,
                "ic_medio": media,
                "tamanho_medio_coluna": len(normalizado) / tamanho,
            }
        )
    return resultados


def _melhor_deslocamento_coluna(coluna: str) -> Dict[str, Any]:
    """Escolhe o deslocamento que aproxima a coluna da distribuição do português."""
    contagem = _contagem_ordenada(coluna)
    melhor_deslocamento = 0
    melhor_pontuacao = float("inf")
    for deslocamento in range(26):
        distribuicao = [0] * 26
        for indice in range(26):
            distribuicao[(indice - deslocamento) % 26] += contagem[indice]
        pontuacao = _qui_quadrado_da_distribuicao(distribuicao)
        if pontuacao < melhor_pontuacao:
            melhor_pontuacao = pontuacao
            melhor_deslocamento = deslocamento
    return {
        "deslocamento": melhor_deslocamento,
        "letra_chave": LETRAS[melhor_deslocamento],
        "qui_quadrado": melhor_pontuacao,
        "amostra": coluna,
    }


def decifrar_vigenere(texto: str, chave: str) -> str:
    """Decifra Vigenère preservando pontuação (a chave avança apenas em letras)."""
    chave_normalizada = normalizar(chave)
    if not chave_normalizada:
        raise ValueError("Informe uma chave não vazia.")
    chave_indices = [INDICE_LETRA[letra] for letra in chave_normalizada]
    saida: List[str] = []
    posicao = 0
    for caractere in str(texto or ""):
        base = remover_acentos(caractere).upper()
        if len(base) == 1 and "A" <= base <= "Z":
            deslocamento = chave_indices[posicao % len(chave_indices)]
            novo = LETRAS[(INDICE_LETRA[base] - deslocamento) % 26]
            saida.append(novo if caractere.isupper() else novo.lower())
            posicao += 1
        else:
            saida.append(caractere)
    return "".join(saida)


def quebrar_vigenere(
    texto: str,
    maximo_chave: int = 15,
    tamanho_forcado: Optional[int] = None,
    candidatos_avaliados: int = 6,
) -> Dict[str, Any]:
    """Quebra Vigenère estimando o tamanho da chave e resolvendo cada coluna."""
    normalizado = normalizar(texto)
    if len(normalizado) < 12:
        raise ValueError("Texto curto demais para a análise de Vigenère (mínimo de 12 letras).")

    tabela = detectar_tamanho_chave(normalizado, maximo_chave)
    if not tabela:
        raise ValueError("Não foi possível estimar o tamanho da chave com este texto.")
    if tamanho_forcado:
        forcado = int(tamanho_forcado)
        escolhidos = [item for item in tabela if item["tamanho"] == forcado]
        if not escolhidos:
            raise ValueError(
                f"O tamanho de chave {forcado} está fora do limite analisado (1 a {maximo_chave})."
            )
        candidatos = escolhidos
    else:
        candidatos = sorted(tabela, key=lambda item: item["ic_medio"], reverse=True)[:candidatos_avaliados]

    melhor: Optional[Dict[str, Any]] = None
    for candidato in candidatos:
        tamanho = candidato["tamanho"]
        colunas = [normalizado[indice::tamanho] for indice in range(tamanho)]
        analises = [_melhor_deslocamento_coluna(coluna) for coluna in colunas]
        chave = "".join(item["letra_chave"] for item in analises)
        claro = decifrar_vigenere(texto, chave)
        pontuacao = pontuar_texto(claro) / max(1, len(normalizar(claro)))
        registro = {
            "tamanho": tamanho,
            "ic_medio": candidato["ic_medio"],
            "chave": chave,
            "texto": claro,
            "pontuacao": pontuacao,
            "colunas": [
                {
                    "posicao": indice + 1,
                    "letra_chave": item["letra_chave"],
                    "deslocamento": item["deslocamento"],
                    "qui_quadrado": item["qui_quadrado"],
                    "amostra": item["amostra"][:40],
                }
                for indice, item in enumerate(analises)
            ],
        }
        if melhor is None or registro["pontuacao"] > melhor["pontuacao"]:
            melhor = registro

    assert melhor is not None
    return {
        "chave": melhor["chave"],
        "tamanho": melhor["tamanho"],
        "texto": melhor["texto"],
        "pontuacao": melhor["pontuacao"],
        "tabela_tamanhos": tabela,
        "colunas": melhor["colunas"],
    }


# ---------------------------------------------------------------------------
# Substituição simples
# ---------------------------------------------------------------------------
def pontuar_texto(texto: str) -> float:
    """Pontuação de verossimilhança em português (log de letras e bigramas)."""
    normalizado = normalizar(texto)
    if not normalizado:
        return float("-inf")
    total = 0.0
    for letra, quantidade in Counter(normalizado).items():
        total += quantidade * LOG_FREQ_LETRA[letra]
    for primeiro, segundo in zip(normalizado, normalizado[1:]):
        total += LOG_BIGRAMA[primeiro + segundo]
    return total


def aplicar_substituicao(texto: str, mapeamento: Dict[str, str]) -> str:
    """Decifra aplicando um mapeamento letra cifrada -> letra clara."""
    tabela = {
        chave.upper(): valor.upper()
        for chave, valor in mapeamento.items()
        if len(chave) == 1 and len(valor) == 1
    }
    saida: List[str] = []
    for caractere in str(texto or ""):
        base = remover_acentos(caractere).upper()
        if len(base) == 1 and "A" <= base <= "Z":
            novo = tabela.get(base, base)
            saida.append(novo if caractere.isupper() else novo.lower())
        else:
            saida.append(caractere)
    return "".join(saida)


def _mapeamento_por_frequencia(contagem: List[int]) -> List[int]:
    """Atribui as letras claras mais frequentes às letras cifradas mais frequentes."""
    cifras = sorted((indice for indice in range(26) if contagem[indice] > 0), key=lambda i: contagem[i], reverse=True)
    claras = sorted(range(26), key=lambda i: FREQUENCIA_LETRAS_PT[LETRAS[i]], reverse=True)
    mapa = list(range(26))
    for cifra, clara in zip(cifras, claras):
        mapa[cifra] = clara
    return mapa


def quebrar_substituicao(
    texto: str,
    reinicios: int = 6,
    iteracoes: int = 2500,
    semente: Optional[int] = None,
) -> Dict[str, Any]:
    """Quebra substituição simples por escalada de colina sobre a permutação de letras."""
    normalizado = normalizar(texto)
    if len(normalizado) < 30:
        raise ValueError(
            "Texto curto demais para quebrar substituição simples com confiança "
            "(mínimo de 30 letras)."
        )
    reinicios = max(1, int(reinicios))
    iteracoes = max(100, int(iteracoes))

    contagem = [0] * 26
    bigramas = [[0] * 26 for _ in range(26)]
    for caractere in normalizado:
        contagem[INDICE_LETRA[caractere]] += 1
    for primeiro, segundo in zip(normalizado, normalizado[1:]):
        bigramas[INDICE_LETRA[primeiro]][INDICE_LETRA[segundo]] += 1

    presentes = [indice for indice in range(26) if contagem[indice] > 0]

    def avaliar(mapa: List[int]) -> float:
        total = 0.0
        for indice in presentes:
            total += contagem[indice] * LOG_FREQ_LETRA[LETRAS[mapa[indice]]]
        for primeiro in presentes:
            linha = bigramas[primeiro]
            for segundo in presentes:
                quantidade = linha[segundo]
                if quantidade:
                    total += quantidade * LOG_BIGRAMA_MATRIZ[mapa[primeiro]][mapa[segundo]]
        return total

    gerador = random.Random(semente)
    inicializacoes: List[List[int]] = [list(range(26)), _mapeamento_por_frequencia(contagem)]
    while len(inicializacoes) < reinicios:
        embaralhado = list(range(26))
        gerador.shuffle(embaralhado)
        inicializacoes.append(embaralhado)

    melhor_mapa = list(range(26))
    melhor_pontuacao = float("-inf")
    total_iteracoes = 0
    for indice_reinicio in range(reinicios):
        mapa = list(inicializacoes[indice_reinicio])
        atual = avaliar(mapa)
        for _ in range(iteracoes):
            total_iteracoes += 1
            if len(presentes) >= 2:
                primeiro, segundo = gerador.sample(presentes, 2)
            else:
                break
            mapa[primeiro], mapa[segundo] = mapa[segundo], mapa[primeiro]
            novo = avaliar(mapa)
            if novo >= atual:
                atual = novo
            else:
                mapa[primeiro], mapa[segundo] = mapa[segundo], mapa[primeiro]
        if atual > melhor_pontuacao:
            melhor_pontuacao = atual
            melhor_mapa = list(mapa)

    mapeamento = {
        LETRAS[cifra]: LETRAS[clara] for cifra, clara in enumerate(melhor_mapa) if contagem[cifra] > 0
    }
    return {
        "mapeamento": mapeamento,
        "texto": aplicar_substituicao(texto, mapeamento),
        "pontuacao": melhor_pontuacao / max(1, len(normalizado)),
        "iteracoes": total_iteracoes,
        "reinicios": reinicios,
        "letras_mapeadas": len(mapeamento),
    }


# ---------------------------------------------------------------------------
# Orquestração e relatório
# ---------------------------------------------------------------------------
def analisar_texto(
    texto: str,
    maximo_chave: int = 15,
    reinicios: int = 6,
    incluir_substituicao: bool = True,
    progresso: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, Any]:
    """Executa todas as análises clássicas e monta o relatório textual."""
    bruto = str(texto or "")
    if len(normalizar(bruto)) < 12:
        raise ValueError(
            "Informe um texto com pelo menos 12 letras para a análise de cifras clássicas."
        )

    etapas = 5 if incluir_substituicao else 4
    atual = 0

    def avisar(mensagem: str) -> None:
        nonlocal atual
        atual += 1
        if progresso is not None:
            progresso(atual, etapas, mensagem)

    avisar("Calculando estatísticas e frequências...")
    estatisticas = estatisticas_texto(bruto)
    frequencias = frequencia_letras(bruto)

    avisar("Testando os 26 deslocamentos de César...")
    cesar = quebrar_cesar(bruto)

    avisar("Procurando repetições (Kasiski) e tamanhos de chave...")
    kasiski_resultado = kasiski(bruto, maximo_chave=maximo_chave)
    tamanhos = detectar_tamanho_chave(bruto, maximo_chave)

    avisar("Quebrando Vigenère coluna a coluna...")
    vigenere: Optional[Dict[str, Any]] = None
    erro_vigenere = ""
    try:
        vigenere = quebrar_vigenere(bruto, maximo_chave)
    except ValueError as exc:
        erro_vigenere = str(exc)

    substituicao: Optional[Dict[str, Any]] = None
    erro_substituicao = ""
    if incluir_substituicao:
        avisar("Quebrando substituição simples por escalada de colina...")
        try:
            substituicao = quebrar_substituicao(bruto, reinicios=reinicios)
        except ValueError as exc:
            erro_substituicao = str(exc)

    resultado: Dict[str, Any] = {
        "estatisticas": estatisticas,
        "frequencias": frequencias,
        "cesar": cesar,
        "kasiski": kasiski_resultado,
        "tamanhos_chave": tamanhos,
        "vigenere": vigenere,
        "erro_vigenere": erro_vigenere,
        "substituicao": substituicao,
        "erro_substituicao": erro_substituicao,
        "texto_original": bruto,
    }
    resultado["relatorio"] = gerar_relatorio(resultado, maximo_chave)
    return resultado


def _formatar_percentual(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",") + "%"


def gerar_relatorio(resultado: Dict[str, Any], maximo_chave: int = 15) -> str:
    """Relatório textual completo em pt-BR."""
    estatisticas = resultado["estatisticas"]
    linhas: List[str] = []
    linhas.append("=" * 74)
    linhas.append("RELATÓRIO DE ANÁLISE DE CIFRAS CLÁSSICAS")
    linhas.append("=" * 74)
    linhas.append(
        f"Texto: {estatisticas['letras']} letras, {estatisticas['palavras']} palavras, "
        f"{estatisticas['caracteres']} caracteres."
    )
    linhas.append(f"Letras distintas: {estatisticas['letras_distintas']}")
    linhas.append(
        "Índice de coincidência: "
        f"{estatisticas['indice_coincidencia']:.4f}".replace(".", ",")
        + " (0,066 a 0,075 indica texto em português sem cifra polialfabética)."
    )
    comuns = ", ".join(
        f"{item['letra']}={item['ocorrencias']}" for item in estatisticas["mais_comuns"]
    )
    linhas.append(f"Letras mais comuns: {comuns}")
    linhas.append("")
    linhas.append("1. Análise de frequência")
    linhas.append("   Letra | Ocorrências | Frequência | Esperado em português")
    for item in resultado["frequencias"]:
        if item["ocorrencias"] == 0:
            continue
        linhas.append(
            f"   {item['letra']}     | {item['ocorrencias']:>11} | "
            f"{_formatar_percentual(item['percentual']):>10} | "
            f"{_formatar_percentual(item['esperado_pt']):>10}"
        )
    linhas.append("")
    linhas.append("2. Cifra de César")
    cesar = resultado["cesar"]
    linhas.append(f"   Melhor deslocamento: {cesar['deslocamento']}")
    linhas.append(f"   Qui-quadrado: {cesar['qui_quadrado']:.2f}".replace(".", ","))
    linhas.append("   Texto decifrado (trecho):")
    linhas.append(_recuo(cesar["texto"], 6))
    linhas.append("   Outras hipóteses:")
    for item in cesar["ranking"][1:6]:
        linhas.append(
            f"     deslocamento {item['deslocamento']:>2} (qui-quadrado "
            f"{item['qui_quadrado']:.2f})".replace(".", ",")
        )
        linhas.append(_recuo(_trecho(item["texto"], 96), 7))
    linhas.append("")
    linhas.append("3. Kasiski e tamanho de chave")
    kasiski_resultado = resultado["kasiski"]
    if kasiski_resultado["sequencias"]:
        linhas.append("   Sequências repetidas mais relevantes:")
        for item in kasiski_resultado["sequencias"][:8]:
            linhas.append(
                f"     {item['trecho']!r} em {item['ocorrencias']} posições; "
                f"distâncias {item['distancias'][:6]}; MDC {item['mdc']}"
            )
        candidatos = ", ".join(
            f"{item['tamanho']} ({item['votos']} voto(s))" for item in kasiski_resultado["candidatos"]
        )
        linhas.append(f"   Tamanhos candidatos por MDC: {candidatos or 'nenhum'}")
    else:
        linhas.append("   Nenhuma repetição útil encontrada para o método de Kasiski.")
    melhores_tamanhos = sorted(
        resultado["tamanhos_chave"], key=lambda item: item["ic_medio"], reverse=True
    )[:5]
    if melhores_tamanhos:
        linhas.append("   Índice de coincidência médio por tamanho de chave:")
        for item in melhores_tamanhos:
            media = f"{item['ic_medio']:.4f}".replace(".", ",")
            linhas.append(f"     {item['tamanho']:>2}: {media}")
    linhas.append("")
    linhas.append("4. Cifra de Vigenère")
    vigenere = resultado.get("vigenere")
    if vigenere:
        linhas.append(f"   Tamanho estimado da chave: {vigenere['tamanho']}")
        linhas.append(f"   Chave provável: {vigenere['chave']}")
        linhas.append(
            "   Índice de coincidência médio das colunas: "
            f"{vigenere['ic_medio']:.4f}".replace(".", ",")
        )
        linhas.append("   Colunas resolvidas:")
        for coluna in vigenere["colunas"]:
            linhas.append(
                f"     coluna {coluna['posicao']:>2}: letra {coluna['letra_chave']} "
                f"(deslocamento {coluna['deslocamento']})"
            )
        linhas.append("   Texto decifrado (trecho):")
        linhas.append(_recuo(vigenere["texto"], 6))
    else:
        linhas.append(f"   Não foi possível analisar: {resultado.get('erro_vigenere') or 'texto insuficiente'}")
    linhas.append("")
    linhas.append("5. Substituição simples")
    substituicao = resultado.get("substituicao")
    if substituicao:
        mapeamento = ", ".join(
            f"{cifra}->{clara}" for cifra, clara in sorted(substituicao["mapeamento"].items())
        )
        linhas.append(f"   Mapeamento obtido: {mapeamento}")
        linhas.append(
            f"   Pontuação média por letra: {substituicao['pontuacao']:.3f}".replace(".", ",")
        )
        linhas.append(
            f"   Reinícios: {substituicao['reinicios']} | Iterações: {substituicao['iteracoes']}"
        )
        linhas.append("   Texto decifrado (trecho):")
        linhas.append(_recuo(substituicao["texto"], 6))
    else:
        linhas.append(
            f"   Não foi possível analisar: {resultado.get('erro_substituicao') or 'análise desativada'}"
        )
    linhas.append("")
    linhas.append("Observações")
    linhas.append(
        "   O resultado é heurístico: textos curtos, com muitos números ou mistura de"
    )
    linhas.append(
        "   idiomas podem levar a chaves e textos incorretos. Confirme visualmente as"
    )
    linhas.append("   hipóteses e ajuste o tamanho de chave quando necessário.")
    linhas.append("=" * 74)
    return "\n".join(linhas)


def _recuo(texto: str, espacos: int, limite: int = 400) -> str:
    recuo = " " * espacos
    trecho = _trecho(texto, limite)
    return "\n".join(recuo + linha for linha in trecho.splitlines())


def _trecho(texto: str, limite: int) -> str:
    texto = str(texto or "").strip()
    if len(texto) <= limite:
        return texto
    return texto[:limite] + "..."


__all__ = [
    "BIGRAMAS_PT",
    "FREQUENCIA_LETRAS_PT",
    "LETRAS",
    "analisar_texto",
    "aplicar_cesar",
    "aplicar_substituicao",
    "contar_letras",
    "decifrar_vigenere",
    "detectar_tamanho_chave",
    "estatisticas_texto",
    "frequencia_letras",
    "gerar_relatorio",
    "indice_coincidencia",
    "kasiski",
    "normalizar",
    "pontuar_texto",
    "quebrar_cesar",
    "quebrar_substituicao",
    "quebrar_vigenere",
    "remover_acentos",
]
