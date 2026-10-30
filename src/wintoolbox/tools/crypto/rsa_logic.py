"""Núcleo puro dos ataques RSA clássicos (sem Qt e sem sympy).

Todas as rotinas usam apenas a biblioteca padrão: ``math.isqrt`` para raízes
inteiras, o algoritmo de Euclides estendido para inversos modulares e
``hashlib`` quando é preciso derivar valores. Nada aqui depende de sympy,
gmpy2 ou de qualquer interface gráfica, o que permite testar os ataques de
forma isolada.

Ataques implementados:

* **Wiener**: expoente privado pequeno, recuperado pelas frações continuadas de
  ``e/n``.
* **Fermat**: primos ``p`` e ``q`` muito próximos, fatorados pela diferença de
  quadrados.
* **Módulo comum**: mesmo ``n`` com dois expoentes públicos coprimos, resolvido
  pela identidade de Bézout.
* **Håstad (transmissão de baixo expoente)**: mesmo ``e`` com módulos distintos,
  resolvido pelo Teorema Chinês do Resto seguido de radiciação inteira exata.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Entrada e aritmética básica
# ---------------------------------------------------------------------------
def parse_inteiro(texto: str) -> int:
    """Converte texto em inteiro positivo, aceitando decimal, hexadecimal e ``nome=valor``."""
    bruto = str(texto or "").strip().replace("_", "").replace(" ", "")
    if not bruto:
        raise ValueError("Informe um número inteiro.")
    if "=" in bruto:
        esquerda, direita = bruto.split("=", 1)
        if esquerda and esquerda.replace("_", "").isalpha():
            bruto = direita.strip()
    sinal = 1
    if bruto[:1] in "+-":
        if bruto[0] == "-":
            sinal = -1
        bruto = bruto[1:]
    if not bruto:
        raise ValueError("Informe um número inteiro.")
    try:
        if bruto.lower().startswith("0x"):
            valor = int(bruto, 16)
        elif bruto.lower().startswith("0b"):
            valor = int(bruto, 2)
        else:
            valor = int(bruto, 10)
    except ValueError as exc:
        raise ValueError(f"Valor inteiro inválido: {texto!r}") from exc
    valor *= sinal
    if valor < 0:
        raise ValueError("Use apenas inteiros positivos nos campos do RSA.")
    return valor


def mdc(a: int, b: int) -> int:
    """Máximo divisor comum."""
    return math.gcd(int(a), int(b))


def euclides_estendido(a: int, b: int) -> Tuple[int, int, int]:
    """Devolve ``(g, x, y)`` tal que ``a*x + b*y = g = mdc(a, b)``."""
    a, b = int(a), int(b)
    antigo_r, r = a, b
    antigo_s, s = 1, 0
    antigo_t, t = 0, 1
    while r != 0:
        quociente = antigo_r // r
        antigo_r, r = r, antigo_r - quociente * r
        antigo_s, s = s, antigo_s - quociente * s
        antigo_t, t = t, antigo_t - quociente * t
    if antigo_r < 0:
        return -antigo_r, -antigo_s, -antigo_t
    return antigo_r, antigo_s, antigo_t


def inverso_modular(valor: int, modulo: int) -> int:
    """Inverso multiplicativo de ``valor`` módulo ``modulo``."""
    valor %= modulo
    if valor == 0:
        raise ValueError("Não existe inverso modular para zero.")
    g, x, _ = euclides_estendido(valor, modulo)
    if g != 1:
        raise ValueError(
            f"Não existe inverso modular: mdc({valor}, {modulo}) = {g}. "
            "Verifique se os valores são coprimos."
        )
    return x % modulo


def potencia_modular(base: int, expoente: int, modulo: int) -> int:
    """Potência modular aceitando expoente negativo (usa o inverso modular)."""
    if modulo <= 0:
        raise ValueError("Módulo inválido.")
    if expoente >= 0:
        return pow(int(base) % modulo, int(expoente), modulo)
    inverso = inverso_modular(base, modulo)
    return pow(inverso, -int(expoente), modulo)


def raiz_inteira_exata(valor: int, grau: int) -> Optional[int]:
    """Raiz inteira exata de ``valor`` no grau informado, ou ``None`` se não existir."""
    valor = int(valor)
    grau = int(grau)
    if grau < 2:
        raise ValueError("O grau da raiz deve ser no mínimo 2.")
    if valor < 0:
        return None
    if valor in (0, 1):
        return valor
    if grau >= valor.bit_length():
        # 2^grau já é maior que o valor, então a única raiz inteira possível é 1
        return None
    if grau == 2:
        raiz = math.isqrt(valor)
        return raiz if raiz * raiz == valor else None
    if valor.bit_length() > 4_000_000:
        raise ValueError(
            f"Radiciação de grau {grau} sobre um inteiro de {valor.bit_length()} bits é "
            "grande demais para esta ferramenta."
        )
    estimativa = 1 << ((valor.bit_length() + grau - 1) // grau)
    while True:
        proxima = ((grau - 1) * estimativa + valor // (estimativa ** (grau - 1))) // grau
        if proxima >= estimativa:
            break
        estimativa = proxima
    if estimativa ** grau == valor:
        return estimativa
    if (estimativa + 1) ** grau == valor:
        return estimativa + 1
    return None


def inteiro_para_bytes(valor: int) -> bytes:
    """Converte um inteiro em bytes big-endian mínimos."""
    valor = int(valor)
    if valor < 0:
        raise ValueError("Não é possível converter inteiro negativo em bytes.")
    if valor == 0:
        return b"\x00"
    return valor.to_bytes((valor.bit_length() + 7) // 8, "big")


def bytes_para_inteiro(dados: bytes) -> int:
    """Converte bytes big-endian em inteiro."""
    return int.from_bytes(bytes(dados), "big")


def interpretar_mensagem(valor: int) -> Dict[str, Any]:
    """Tenta representar o inteiro decifrado como texto e devolve todas as formas úteis."""
    dados = inteiro_para_bytes(int(valor))
    texto: Optional[str] = None
    origem = ""

    if dados.startswith(b"\x00\x02"):
        # PKCS#1 v1.5: 0x00 0x02 <preenchimento> 0x00 <mensagem>
        separador = dados.find(b"\x00", 2)
        if separador > 0 and separador + 1 < len(dados):
            candidato = dados[separador + 1 :]
            try:
                texto = candidato.decode("utf-8")
                origem = "PKCS#1 v1.5 (UTF-8)"
            except UnicodeDecodeError:
                texto = candidato.decode("latin-1")
                origem = "PKCS#1 v1.5 (latin-1)"

    if texto is None:
        try:
            candidato = dados.decode("utf-8")
            if candidato.isprintable() or "\n" in candidato:
                texto = candidato
                origem = "UTF-8"
        except UnicodeDecodeError:
            texto = None

    if texto is None:
        imprimiveis = sum(1 for byte in dados if 32 <= byte < 127 or byte in (9, 10, 13))
        if dados and imprimiveis / len(dados) > 0.85:
            texto = dados.decode("latin-1")
            origem = "latin-1 (provável texto)"

    return {
        "inteiro": int(valor),
        "hexadecimal": format(int(valor), "x"),
        "bytes": dados,
        "texto": texto,
        "origem_texto": origem,
        "tamanho_bytes": len(dados),
    }


# ---------------------------------------------------------------------------
# Geração de chave a partir dos fatores
# ---------------------------------------------------------------------------
def chave_privada_de_fatores(p: int, q: int, e: int) -> Dict[str, int]:
    """Calcula ``n``, ``phi`` e ``d`` a partir de ``p``, ``q`` e ``e``."""
    p, q, e = int(p), int(q), int(e)
    if p <= 1 or q <= 1:
        raise ValueError("Fatores inválidos: p e q devem ser maiores que 1.")
    if p == q:
        raise ValueError("p e q são iguais; a chave não é utilizável.")
    n = p * q
    phi = (p - 1) * (q - 1)
    if mdc(e, phi) != 1:
        raise ValueError(
            f"O expoente e={e} não é coprimo de phi(n)={phi}; não é possível calcular d."
        )
    d = inverso_modular(e, phi)
    return {"p": p, "q": q, "n": n, "phi": phi, "e": e, "d": d}


def decifrar_com_chave(cifra: int, d: int, n: int) -> int:
    """Decifra um inteiro com a chave privada."""
    return pow(int(cifra) % int(n), int(d), int(n))


# ---------------------------------------------------------------------------
# Ataque de Wiener
# ---------------------------------------------------------------------------
def _convergentes(numerador: int, denominador: int) -> Iterable[Tuple[int, int]]:
    """Convergentes da fração continuada de ``numerador/denominador``."""
    x, y = int(numerador), int(denominador)
    termos: List[int] = []
    while y:
        quociente = x // y
        termos.append(quociente)
        x, y = y, x - quociente * y
    p_menos_2, p_menos_1 = 0, 1
    q_menos_2, q_menos_1 = 1, 0
    for termo in termos:
        p = termo * p_menos_1 + p_menos_2
        q = termo * q_menos_1 + q_menos_2
        yield p, q
        p_menos_2, p_menos_1 = p_menos_1, p
        q_menos_2, q_menos_1 = q_menos_1, q


def ataque_wiener(n: int, e: int) -> Optional[Dict[str, Any]]:
    """Recupera a chave privada quando ``d`` é pequeno (ataque de Wiener)."""
    n, e = int(n), int(e)
    if n <= 3 or e <= 1:
        raise ValueError("Informe n maior que 3 e e maior que 1.")
    if e >= n:
        raise ValueError("O expoente e deve ser menor que o módulo n.")
    tentativas = 0
    for k, d in _convergentes(e, n):
        tentativas += 1
        if k == 0 or d == 0:
            continue
        if (e * d - 1) % k != 0:
            continue
        phi = (e * d - 1) // k
        soma = n - phi + 1
        discriminante = soma * soma - 4 * n
        if discriminante < 0:
            continue
        raiz = math.isqrt(discriminante)
        if raiz * raiz != discriminante:
            continue
        p = (soma + raiz) // 2
        q = (soma - raiz) // 2
        if p * q != n or p <= 1 or q <= 1:
            continue
        return {
            "sucesso": True,
            "p": min(p, q),
            "q": max(p, q),
            "d": d,
            "k": k,
            "phi": phi,
            "n": n,
            "e": e,
            "convergentes_testados": tentativas,
        }
    return None


# ---------------------------------------------------------------------------
# Fatoração de Fermat
# ---------------------------------------------------------------------------
def fatorar_fermat(n: int, max_iteracoes: int = 2_000_000) -> Optional[Dict[str, Any]]:
    """Fatora ``n`` quando os dois primos são próximos (método de Fermat)."""
    n = int(n)
    if n < 4:
        raise ValueError("Informe um módulo maior ou igual a 4.")
    if n % 2 == 0:
        return {"p": 2, "q": n // 2, "iteracoes": 0, "metodo": "divisão por 2"}
    raiz = math.isqrt(n)
    if raiz * raiz == n:
        if raiz == 1:
            raise ValueError("O módulo 1 não possui fatoração útil.")
        return {"p": raiz, "q": raiz, "iteracoes": 0, "metodo": "quadrado perfeito"}
    a = raiz + 1
    limite = max(1, int(max_iteracoes))
    for iteracao in range(1, limite + 1):
        b2 = a * a - n
        b = math.isqrt(b2)
        if b * b == b2:
            p = a - b
            q = a + b
            if p * q == n and p > 1:
                return {"p": p, "q": q, "iteracoes": iteracao, "metodo": "diferença de quadrados"}
        a += 1
    return None


# ---------------------------------------------------------------------------
# Módulo comum
# ---------------------------------------------------------------------------
def ataque_modulo_comum(
    n: int,
    e1: int,
    c1: int,
    e2: int,
    c2: int,
) -> Dict[str, Any]:
    """Recupera a mensagem quando o mesmo ``n`` é usado com dois expoentes coprimos."""
    n, e1, e2 = int(n), int(e1), int(e2)
    c1, c2 = int(c1), int(c2)
    if n <= 3:
        raise ValueError("Informe um módulo n maior que 3.")
    if e1 <= 0 or e2 <= 0:
        raise ValueError("Os expoentes públicos devem ser positivos.")
    if e1 == e2:
        raise ValueError(
            "Os expoentes são iguais; o ataque de módulo comum exige expoentes diferentes."
        )
    g, a, b = euclides_estendido(e1, e2)
    combinado = (potencia_modular(c1, a, n) * potencia_modular(c2, b, n)) % n
    aviso = ""
    if g == 1:
        mensagem = combinado
    else:
        raiz = raiz_inteira_exata(combinado, g)
        if raiz is None:
            raise ValueError(
                f"Os expoentes têm mdc {g}: a combinação produz m^{g} módulo n, mas a "
                "raiz inteira de grau "
                f"{g} não é exata. Isso indica que a mensagem não foi cifrada em texto puro "
                "ou que as premissas do ataque não valem."
            )
        mensagem = raiz
        aviso = (
            f"Expoentes com mdc {g}; foi extraída a raiz inteira de grau {g} da combinação."
        )
    return {
        "sucesso": True,
        "m": mensagem,
        "g": g,
        "coeficiente_a": a,
        "coeficiente_b": b,
        "n": n,
        "e1": e1,
        "e2": e2,
        "aviso": aviso,
    }


# ---------------------------------------------------------------------------
# Håstad (broadcast de baixo expoente)
# ---------------------------------------------------------------------------
def ataque_hastad(chaves: Sequence[Tuple[int, int, int]]) -> Dict[str, Any]:
    """Resolve o ataque de Håstad para o mesmo ``e`` e módulos distintos.

    ``chaves`` é uma sequência de ``(n, e, c)``.
    """
    if len(chaves) < 2:
        raise ValueError("Informe pelo menos duas chaves (n, e, c) para o ataque de Håstad.")
    normalizadas: List[Tuple[int, int, int]] = []
    for indice, item in enumerate(chaves, start=1):
        if len(item) != 3:
            raise ValueError(f"Chave {indice}: informe exatamente n, e e c.")
        n, e, c = (int(item[0]), int(item[1]), int(item[2]))
        if n <= 3:
            raise ValueError(f"Chave {indice}: módulo n inválido.")
        if e <= 1:
            raise ValueError(f"Chave {indice}: expoente e inválido.")
        normalizadas.append((n, e, c))

    expoentes = {item[1] for item in normalizadas}
    if len(expoentes) != 1:
        raise ValueError(
            "O ataque de Håstad exige o mesmo expoente e em todas as chaves; "
            f"recebi {sorted(expoentes)}."
        )
    expoente = expoentes.pop()
    modulos = [item[0] for item in normalizadas]
    if len(set(modulos)) != len(modulos):
        raise ValueError("Os módulos devem ser distintos para o ataque de Håstad.")
    for i in range(len(modulos)):
        for j in range(i + 1, len(modulos)):
            if mdc(modulos[i], modulos[j]) != 1:
                raise ValueError(
                    f"Os módulos n{i + 1} e n{j + 1} não são coprimos; o ataque não se aplica."
                )

    produto = math.prod(modulos)
    acumulado = 0
    for n, _, c in normalizadas:
        parte = produto // n
        acumulado = (acumulado + (c % n) * parte * inverso_modular(parte % n, n)) % produto

    raiz = raiz_inteira_exata(acumulado, expoente)
    aviso = ""
    if raiz is None:
        aviso = (
            "A combinação módulo o produto dos n não é uma potência exata de grau "
            f"{expoente}. Normalmente isso indica que a mensagem é maior que algum dos "
            "módulos, que o preenchimento (padding) foi usado de forma inconsistente ou "
            "que falta uma das cifras."
        )
    elif len(normalizadas) < expoente:
        aviso = (
            f"Foram usadas {len(normalizadas)} chaves para um expoente {expoente}. "
            "O resultado só é confiável quando a mensagem elevada ao expoente é menor que "
            "o produto dos módulos."
        )
    return {
        "sucesso": raiz is not None,
        "m": raiz,
        "expoente": expoente,
        "produto_modulos": produto,
        "combinacao": acumulado,
        "quantidade_chaves": len(normalizadas),
        "aviso": aviso,
    }


def parse_chaves_hastad(texto: str) -> List[Tuple[int, int, int]]:
    """Interpreta linhas no formato ``n, e, c`` separadas por vírgula, ponto e vírgula ou espaço."""
    chaves: List[Tuple[int, int, int]] = []
    for numero, linha in enumerate(str(texto or "").splitlines(), start=1):
        limpa = linha.strip()
        if not limpa or limpa.startswith("#"):
            continue
        partes = [parte for parte in limpa.replace(";", ",").replace("\t", " ").split(",") if parte.strip()]
        if len(partes) != 3:
            partes = [parte for parte in limpa.split() if parte.strip()]
        if len(partes) != 3:
            raise ValueError(
                f"Linha {numero}: esperava três valores (n, e, c), encontrei {len(partes)}."
            )
        try:
            n = parse_inteiro(partes[0])
            e = parse_inteiro(partes[1])
            c = parse_inteiro(partes[2])
        except ValueError as exc:
            raise ValueError(f"Linha {numero}: {exc}") from exc
        chaves.append((n, e, c))
    if not chaves:
        raise ValueError("Informe pelo menos duas linhas no formato n, e, c.")
    return chaves


# ---------------------------------------------------------------------------
# Análise automática e relatórios textuais
# ---------------------------------------------------------------------------
def analise_automatica(n: int, e: int, cifra: Optional[int] = None) -> Dict[str, Any]:
    """Tenta Wiener e Fermat em sequência e devolve os resultados obtidos."""
    n, e = int(n), int(e)
    resultados: List[Dict[str, Any]] = []
    wiener = ataque_wiener(n, e)
    if wiener:
        resultados.append({"ataque": "Wiener", "dados": wiener})
    fermat = fatorar_fermat(n, max_iteracoes=200_000)
    if fermat:
        try:
            chave = chave_privada_de_fatores(fermat["p"], fermat["q"], e)
        except ValueError as exc:
            chave = {"erro": str(exc), "p": fermat["p"], "q": fermat["q"]}
        resultados.append({"ataque": "Fermat", "dados": {**fermat, "chave": chave}})
    return {"resultados": resultados, "n": n, "e": e, "cifra": cifra}


def _linhas_plaintext(valor: int) -> List[str]:
    """Linhas com a representação de um inteiro já decifrado (mensagem em claro)."""
    info = interpretar_mensagem(int(valor))
    linhas = [
        f"Mensagem recuperada (inteiro): {info['inteiro']}",
        f"Mensagem recuperada (hex)    : {info['hexadecimal']}",
    ]
    if info["texto"] is not None:
        linhas.append(f"Mensagem recuperada (texto)  : {info['texto']!r}")
        linhas.append(f"Codificação detectada        : {info['origem_texto']}")
    else:
        linhas.append(
            "A mensagem recuperada não parece texto legível; confira o hexadecimal acima."
        )
    return linhas


def _linhas_mensagem(cifra: Optional[int], d: Optional[int], n: int) -> List[str]:
    """Linhas com a mensagem decifrada, quando ``cifra`` e ``d`` estão disponíveis."""
    if cifra is None or d is None or n <= 0:
        return []
    try:
        bruto = decifrar_com_chave(cifra, d, n)
    except Exception as exc:  # pragma: no cover - proteção defensiva
        return [f"Falha ao decifrar a mensagem: {exc}"]
    return _linhas_plaintext(bruto)


def relatorio_wiener(resultado: Optional[Dict[str, Any]], cifra: Optional[int] = None) -> str:
    """Relatório textual do ataque de Wiener."""
    linhas = ["ATAQUE DE WIENER (expoente privado pequeno)", ""]
    if not resultado:
        linhas.append("Resultado: a chave NÃO é vulnerável ao ataque de Wiener.")
        linhas.append(
            "Nenhum convergente de e/n produziu um d válido dentro das premissas do ataque."
        )
        return "\n".join(linhas)
    linhas.append("Resultado: chave VULNERÁVEL. Fatores recuperados pelas frações continuadas.")
    linhas.append(f"p = {resultado['p']}")
    linhas.append(f"q = {resultado['q']}")
    linhas.append(f"d = {resultado['d']}")
    linhas.append(f"phi(n) = {resultado['phi']}")
    linhas.append(f"k = {resultado['k']} (numerador do convergente)")
    linhas.append(f"Convergentes testados: {resultado['convergentes_testados']}")
    linhas.extend(_linhas_mensagem(cifra, resultado["d"], resultado["n"]))
    return "\n".join(linhas)


def relatorio_fermat(
    resultado: Optional[Dict[str, Any]],
    n: int,
    e: Optional[int] = None,
    cifra: Optional[int] = None,
    max_iteracoes: int = 0,
) -> str:
    """Relatório textual da fatoração de Fermat."""
    linhas = ["FATORAÇÃO DE FERMAT (primos próximos)", ""]
    if not resultado:
        linhas.append("Resultado: NÃO foi possível fatorar dentro do limite de iterações.")
        if max_iteracoes:
            linhas.append(f"Limite utilizado: {max_iteracoes} iterações.")
        linhas.append("Aumente o limite ou use outro método de fatoração.")
        return "\n".join(linhas)
    linhas.append(f"Resultado: módulo FATORADO por {resultado['metodo']}.")
    linhas.append(f"p = {resultado['p']}")
    linhas.append(f"q = {resultado['q']}")
    linhas.append(f"Iterações necessárias: {resultado['iteracoes']}")
    d = None
    if e is not None:
        try:
            chave = chave_privada_de_fatores(resultado["p"], resultado["q"], int(e))
            linhas.append(f"phi(n) = {chave['phi']}")
            linhas.append(f"d = {chave['d']}")
            d = chave["d"]
        except ValueError as exc:
            linhas.append(f"Falha ao calcular a chave privada: {exc}")
    linhas.extend(_linhas_mensagem(cifra, d, int(n)))
    return "\n".join(linhas)


def relatorio_modulo_comum(resultado: Dict[str, Any]) -> str:
    """Relatório textual do ataque de módulo comum."""
    linhas = ["ATAQUE DE MÓDULO COMUM (mesmo n, expoentes coprimos)", ""]
    linhas.append("Resultado: mensagem RECUPERADA pela identidade de Bézout.")
    linhas.append(f"mdc(e1, e2) = {resultado['g']}")
    linhas.append(f"Coeficientes de Bézout: a = {resultado['coeficiente_a']}, b = {resultado['coeficiente_b']}")
    if resultado.get("aviso"):
        linhas.append(f"Observação: {resultado['aviso']}")
    linhas.extend(_linhas_plaintext(resultado["m"]))
    return "\n".join(linhas)


def relatorio_hastad(resultado: Dict[str, Any], cifras: Optional[Sequence[Tuple[int, int, int]]] = None) -> str:
    """Relatório textual do ataque de Håstad."""
    linhas = ["ATAQUE DE HÅSTAD (mesmo e, módulos distintos)", ""]
    linhas.append(f"Chaves utilizadas: {resultado['quantidade_chaves']}")
    linhas.append(f"Expoente comum: {resultado['expoente']}")
    if resultado["sucesso"]:
        linhas.append("Resultado: mensagem RECUPERADA pela combinação módulo o produto dos n.")
        linhas.extend(_linhas_plaintext(resultado["m"]))
    else:
        linhas.append("Resultado: a combinação não produziu uma potência exata.")
    if resultado.get("aviso"):
        linhas.append(f"Observação: {resultado['aviso']}")
    return "\n".join(linhas)


def relatorio_analise_automatica(resultado: Dict[str, Any], cifra: Optional[int] = None) -> str:
    """Relatório da tentativa automática (Wiener e Fermat)."""
    linhas = ["ANÁLISE AUTOMÁTICA DE CHAVE RSA", ""]
    n = resultado["n"]
    e = resultado["e"]
    linhas.append(f"n = {n}")
    linhas.append(f"e = {e}")
    linhas.append(f"bits de n = {n.bit_length()}")
    if not resultado["resultados"]:
        linhas.append("")
        linhas.append("Nenhuma vulnerabilidade conhecida foi confirmada pelos testes automáticos.")
        linhas.append("A chave não é vulnerável a Wiener nem a Fermat com primos próximos.")
        return "\n".join(linhas)
    linhas.append("")
    for item in resultado["resultados"]:
        ataque = item["ataque"]
        dados = item["dados"]
        linhas.append(f"Vulnerabilidade encontrada: {ataque}")
        if ataque == "Wiener":
            linhas.append(f"  p = {dados['p']}")
            linhas.append(f"  q = {dados['q']}")
            linhas.append(f"  d = {dados['d']}")
            linhas.extend("  " + linha for linha in _linhas_mensagem(cifra, dados["d"], n))
        else:
            linhas.append(f"  p = {dados['p']}")
            linhas.append(f"  q = {dados['q']}")
            linhas.append(f"  iterações = {dados['iteracoes']}")
            chave = dados.get("chave", {})
            if "d" in chave:
                linhas.append(f"  d = {chave['d']}")
                linhas.extend("  " + linha for linha in _linhas_mensagem(cifra, chave["d"], n))
            elif chave.get("erro"):
                linhas.append(f"  aviso: {chave['erro']}")
        linhas.append("")
    return "\n".join(linhas)


__all__ = [
    "analise_automatica",
    "ataque_hastad",
    "ataque_modulo_comum",
    "ataque_wiener",
    "bytes_para_inteiro",
    "chave_privada_de_fatores",
    "decifrar_com_chave",
    "euclides_estendido",
    "fatorar_fermat",
    "inteiro_para_bytes",
    "interpretar_mensagem",
    "inverso_modular",
    "mdc",
    "parse_chaves_hastad",
    "parse_inteiro",
    "potencia_modular",
    "raiz_inteira_exata",
    "relatorio_analise_automatica",
    "relatorio_fermat",
    "relatorio_hastad",
    "relatorio_modulo_comum",
    "relatorio_wiener",
]
