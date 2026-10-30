"""Desofuscação de JavaScript com pretty-printer nativo.

O pipeline aplica, na ordem: desescape de sequências (\\xNN, \\uNNNN, octal),
resolução de `String.fromCharCode`, desembrulho de `eval` com literal, renomeação
de identificadores `_0x...`, remoção de blocos mortos simples e formatação.
`jsbeautifier` é usado quando instalado; caso contrário, um tokenizador e
formatador nativo mantém a interface totalmente funcional.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.registry import Tool, register
from wintoolbox.tools._helpers import dependencia_disponivel, formatar_numero
from wintoolbox.tools._widgets import (
    PainelFerramenta,
    adicionar_log_painel,
    botao_copiar,
    criar_card,
    criar_saida_texto,
    criar_tabela,
    executar_assincrono,
    mostrar_erro,
    preencher_tabela,
)

_log = get_logger("rev.js_deobfuscator")

PALAVRAS_RESERVADAS = {
    "break", "case", "catch", "continue", "debugger", "default", "delete", "do",
    "else", "finally", "for", "function", "if", "in", "instanceof", "new",
    "return", "switch", "this", "throw", "try", "typeof", "var", "void", "while",
    "with", "yield", "let", "const", "class", "extends", "super", "async", "await",
    "import", "export", "from", "of", "static", "get", "set",
}

_OPERADORES = (
    "===", "!==", ">>>", "<<=", ">>=", "**=", "=>", "==", "!=", "<=", ">=",
    "&&", "||", "??", "?.", "++", "--", "+=", "-=", "*=", "/=", "%=", "&=",
    "|=", "^=", "**", "<<", ">>", "&&=", "||=", "??=",
)

_PADRAO_ESCAPE = re.compile(
    r"(?<!\\)\\(x[0-9a-fA-F]{2}|u\{[0-9a-fA-F]{1,6}\}|u[0-9a-fA-F]{4}|[0-7]{1,3})"
)
_PADRAO_FROMCHARCODE = re.compile(
    r"String\s*\.\s*fromCharCode\s*\(\s*"
    r"((?:0[xX][0-9a-fA-F]+|\d+)(?:\s*,\s*(?:0[xX][0-9a-fA-F]+|\d+))*)\s*\)"
)
_PADRAO_EVAL_LITERAL = re.compile(
    r"\beval\s*\(\s*(['\"])((?:\\.|(?!\1).){4,})\1\s*\)", re.DOTALL
)
_PADRAO_HEX_IDENT = re.compile(r"\b_0x[0-9a-fA-F]{2,}\b")
_PADRAO_IF_FALSO = re.compile(
    r"\bif\s*\(\s*(?:false|0|!1|!true)\s*\)\s*\{", re.IGNORECASE
)
_PADRAO_IF_VERDADEIRO = re.compile(
    r"\bif\s*\(\s*(?:true|1|!0|!false)\s*\)\s*\{", re.IGNORECASE
)
_PADRAO_WHILE_FALSO = re.compile(
    r"\bwhile\s*\(\s*(?:false|0|!1)\s*\)\s*\{", re.IGNORECASE
)
_PADRAO_IF_SEM_BLOCO = re.compile(
    r"\bif\s*\(\s*(?:false|0|!1)\s*\)\s*[^{;\n]+;", re.IGNORECASE
)


# ---------------------------------------------------------------- tokenizador
def _tokenizar(codigo: str) -> List[Tuple[str, str]]:
    """Tokeniza o essencial de JavaScript preservando strings e comentários."""
    tokens: List[Tuple[str, str]] = []
    indice = 0
    total = len(codigo)
    anterior_significativo = ""

    while indice < total:
        caractere = codigo[indice]

        if caractere in " \t\r\n":
            indice += 1
            continue

        if codigo.startswith("//", indice):
            fim = codigo.find("\n", indice)
            if fim < 0:
                fim = total
            tokens.append(("comentario", codigo[indice:fim]))
            indice = fim
            continue

        if codigo.startswith("/*", indice):
            fim = codigo.find("*/", indice + 2)
            fim = total if fim < 0 else fim + 2
            tokens.append(("comentario", codigo[indice:fim]))
            indice = fim
            continue

        if caractere in "'\"":
            aspa = caractere
            posicao = indice + 1
            while posicao < total:
                if codigo[posicao] == "\\":
                    posicao += 2
                    continue
                if codigo[posicao] == aspa:
                    posicao += 1
                    break
                if codigo[posicao] == "\n":
                    break
                posicao += 1
            tokens.append(("texto", codigo[indice:posicao]))
            anterior_significativo = "texto"
            indice = posicao
            continue

        if caractere == "`":
            posicao = indice + 1
            while posicao < total:
                if codigo[posicao] == "\\":
                    posicao += 2
                    continue
                if codigo[posicao] == "`":
                    posicao += 1
                    break
                posicao += 1
            tokens.append(("texto", codigo[indice:posicao]))
            anterior_significativo = "texto"
            indice = posicao
            continue

        if caractere == "/" and anterior_significativo not in {"ident", "numero", "texto", ")", "]"}:
            posicao = indice + 1
            dentro_classe = False
            while posicao < total:
                atual = codigo[posicao]
                if atual == "\\":
                    posicao += 2
                    continue
                if atual == "[":
                    dentro_classe = True
                elif atual == "]":
                    dentro_classe = False
                elif atual == "/" and not dentro_classe:
                    posicao += 1
                    break
                elif atual == "\n":
                    break
                posicao += 1
            while posicao < total and codigo[posicao].isalpha():
                posicao += 1
            tokens.append(("regex", codigo[indice:posicao]))
            anterior_significativo = "regex"
            indice = posicao
            continue

        if caractere.isalpha() or caractere in "_$":
            posicao = indice
            while posicao < total and (codigo[posicao].isalnum() or codigo[posicao] in "_$"):
                posicao += 1
            tokens.append(("ident", codigo[indice:posicao]))
            anterior_significativo = "ident"
            indice = posicao
            continue

        if caractere.isdigit() or (caractere == "." and indice + 1 < total and codigo[indice + 1].isdigit()):
            posicao = indice
            while posicao < total and (codigo[posicao].isalnum() or codigo[posicao] in ".xX_"):
                posicao += 1
            tokens.append(("numero", codigo[indice:posicao]))
            anterior_significativo = "numero"
            indice = posicao
            continue

        for operador in _OPERADORES:
            if codigo.startswith(operador, indice):
                tokens.append(("punct", operador))
                anterior_significativo = "punct"
                indice += len(operador)
                break
        else:
            tokens.append(("punct", caractere))
            anterior_significativo = "punct"
            indice += 1
    return tokens


def _precisa_espaco(anterior: Tuple[str, str], atual: Tuple[str, str]) -> bool:
    """Decide se dois tokens precisam de espaço para não se fundirem."""
    if not anterior:
        return False
    tipo_anterior, valor_anterior = anterior
    tipo_atual, _ = atual
    if tipo_anterior in {"ident", "numero", "texto", "regex"} and tipo_atual in {
        "ident", "numero", "texto", "regex"
    }:
        return True
    if valor_anterior in {"return", "typeof", "new", "delete", "void", "in", "of", "instanceof"}:
        return True
    return False


def formatar_js(codigo: str, indentacao: int = 2) -> str:
    """Pretty-printer nativo: um token por linha quando estrutural, com recuo."""
    tokens = _tokenizar(codigo)
    partes: List[str] = []
    nivel = 0
    profundidade_arredondada = 0
    inicio_linha = True

    def escrever(texto: str, espaco: bool = False) -> None:
        nonlocal inicio_linha
        if inicio_linha:
            partes.append(" " * (indentacao * max(0, nivel)))
            inicio_linha = False
        if espaco and partes and not partes[-1].endswith((" ", "\n")):
            partes.append(" ")
        partes.append(texto)

    def quebrar() -> None:
        nonlocal inicio_linha
        while partes and partes[-1] == " ":
            partes.pop()
        if partes and not partes[-1].endswith("\n"):
            partes.append("\n")
        inicio_linha = True

    anterior: Optional[Tuple[str, str]] = None
    for indice, token in enumerate(tokens):
        tipo, valor = token
        if tipo == "comentario":
            if valor.startswith("//"):
                escrever(valor.rstrip())
                quebrar()
            else:
                if not inicio_linha:
                    quebrar()
                for linha in valor.splitlines():
                    escrever(linha.rstrip())
                    quebrar()
            anterior = None
            continue

        if valor == "{":
            escrever("{", _precisa_espaco(anterior, token) if anterior else False)
            quebrar()
            nivel += 1
        elif valor == "}":
            if not inicio_linha:
                quebrar()
            nivel = max(0, nivel - 1)
            escrever("}")
            proximo = tokens[indice + 1] if indice + 1 < len(tokens) else None
            if proximo and proximo[1] in {"else", "catch", "finally", "while", ";"}:
                anterior = token
                continue
            quebrar()
        elif valor == ";":
            escrever(";")
            quebrar()
        elif valor == "(":
            escrever("(", _precisa_espaco(anterior, token) if anterior else False)
            profundidade_arredondada += 1
        elif valor == ")":
            escrever(")")
            profundidade_arredondada = max(0, profundidade_arredondada - 1)
        elif valor == "[":
            escrever("[", _precisa_espaco(anterior, token) if anterior else False)
            profundidade_arredondada += 1
        elif valor == "]":
            escrever("]")
            profundidade_arredondada = max(0, profundidade_arredondada - 1)
        elif valor == ",":
            escrever(",")
            if profundidade_arredondada == 0 and nivel > 0:
                quebrar()
            else:
                escrever(" ")
        elif valor == ":":
            escrever(":", espaco=False)
            escrever(" ")
        elif tipo == "punct" and valor in {
            "=", "+", "-", "*", "/", "%", "==", "===", "!=", "!==", "<", ">", "<=", ">=",
            "&&", "||", "??", "=>", "+=", "-=", "*=", "/=", "&", "|", "^", "?", "!",
        }:
            escrever(valor, espaco=not (valor == "!" and anterior and anterior[1] in {"(", "[", "="}))
            escrever(" ")
        else:
            escrever(valor, _precisa_espaco(anterior, token) if anterior else False)
        anterior = token

    texto = "".join(partes)
    texto = re.sub(r"[ \t]+\n", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip() + "\n"


# ------------------------------------------------------------------ desescape
def desescapar(codigo: str) -> Tuple[str, int]:
    """Converte escapes hexadecimais, Unicode e octais em caracteres literais."""
    total = 0

    def _substituir(achado: re.Match[str]) -> str:
        nonlocal total
        sequencia = achado.group(1)
        try:
            if sequencia.startswith("x"):
                caractere = chr(int(sequencia[1:], 16))
            elif sequencia.startswith("u{"):
                caractere = chr(int(sequencia[2:-1], 16))
            elif sequencia.startswith("u"):
                caractere = chr(int(sequencia[1:], 16))
            else:
                caractere = chr(int(sequencia, 8))
        except (ValueError, OverflowError):
            return achado.group(0)
        total += 1
        if caractere in {"'", '"', "\\", "\n"}:
            return "\\" + caractere if caractere != "\n" else "\\n"
        return caractere

    return _PADRAO_ESCAPE.sub(_substituir, codigo), total


def resolver_fromcharcode(codigo: str) -> Tuple[str, int]:
    """Substitui `String.fromCharCode(...)` por literal quando o resultado é legível."""
    total = 0

    def _substituir(achado: re.Match[str]) -> str:
        nonlocal total
        try:
            valores = [int(parte.strip(), 0) for parte in achado.group(1).split(",")]
        except ValueError:
            return achado.group(0)
        if not valores or any(valor < 0 or valor > 0x10FFFF for valor in valores):
            return achado.group(0)
        texto = "".join(chr(valor) for valor in valores)
        imprimiveis = sum(1 for caractere in texto if caractere.isprintable())
        if not texto or imprimiveis / len(texto) < 0.7:
            return achado.group(0)
        total += 1
        return json.dumps(texto)

    return _PADRAO_FROMCHARCODE.sub(_substituir, codigo), total


def desembrulhar_eval(codigo: str, limite: int = 4) -> Tuple[str, int]:
    """Troca `eval("literal")` pelo conteúdo literal, repetindo até estabilizar."""
    total = 0
    for _ in range(limite):
        achado = _PADRAO_EVAL_LITERAL.search(codigo)
        if not achado:
            break
        interno = achado.group(2)
        interno, _ = desescapar(interno)
        if not interno.strip():
            break
        codigo = codigo[: achado.start()] + interno + codigo[achado.end() :]
        total += 1
    return codigo, total


def _aplicar_fora_de_texto(codigo: str, transformacao: Callable[[str], str]) -> str:
    """Aplica uma transformação somente nos trechos que não são strings/comentários."""
    saida: List[str] = []
    indice = 0
    total = len(codigo)
    while indice < total:
        caractere = codigo[indice]
        if caractere in "'\"`":
            aspa = caractere
            posicao = indice + 1
            while posicao < total:
                if codigo[posicao] == "\\":
                    posicao += 2
                    continue
                if codigo[posicao] == aspa:
                    posicao += 1
                    break
                posicao += 1
            saida.append(codigo[indice:posicao])
            indice = posicao
            continue
        if codigo.startswith("//", indice):
            fim = codigo.find("\n", indice)
            fim = total if fim < 0 else fim
            saida.append(codigo[indice:fim])
            indice = fim
            continue
        if codigo.startswith("/*", indice):
            fim = codigo.find("*/", indice + 2)
            fim = total if fim < 0 else fim + 2
            saida.append(codigo[indice:fim])
            indice = fim
            continue
        proximo = indice
        while proximo < total and codigo[proximo] not in "'\"`/":
            proximo += 1
        saida.append(transformacao(codigo[indice:proximo]))
        indice = proximo
    return "".join(saida)


def renomear_hex(codigo: str) -> Tuple[str, int, Dict[str, str]]:
    """Renomeia identificadores `_0x...` por nomes sequenciais legíveis."""
    encontrados = _PADRAO_HEX_IDENT.findall(codigo)
    mapa: Dict[str, str] = {}
    for original in encontrados:
        if original not in mapa:
            mapa[original] = f"ident_{len(mapa) + 1}"

    def _transformar(trecho: str) -> str:
        return _PADRAO_HEX_IDENT.sub(lambda achado: mapa.get(achado.group(0), achado.group(0)), trecho)

    if not mapa:
        return codigo, 0, {}
    return _aplicar_fora_de_texto(codigo, _transformar), len(mapa), mapa


def _fim_do_bloco(codigo: str, inicio: int) -> int:
    """Encontra a chave de fechamento correspondente, ignorando strings e comentários."""
    profundidade = 0
    indice = inicio
    total = len(codigo)
    while indice < total:
        caractere = codigo[indice]
        if caractere in "'\"`":
            aspa = caractere
            indice += 1
            while indice < total:
                if codigo[indice] == "\\":
                    indice += 2
                    continue
                if codigo[indice] == aspa:
                    indice += 1
                    break
                indice += 1
            continue
        if codigo.startswith("//", indice):
            fim = codigo.find("\n", indice)
            indice = total if fim < 0 else fim
            continue
        if codigo.startswith("/*", indice):
            fim = codigo.find("*/", indice + 2)
            indice = total if fim < 0 else fim + 2
            continue
        if caractere == "{":
            profundidade += 1
        elif caractere == "}":
            profundidade -= 1
            if profundidade == 0:
                return indice
        indice += 1
    return -1


def remover_codigo_morto(codigo: str, limite: int = 40) -> Tuple[str, int]:
    """Remove blocos `if (false)`/`while (false)` e desembrulha `if (true)`."""
    removidos = 0
    for _ in range(limite):
        alterou = False

        for padrao in (_PADRAO_IF_FALSO, _PADRAO_WHILE_FALSO):
            achado = padrao.search(codigo)
            if achado:
                abertura = codigo.find("{", achado.start())
                if abertura >= 0:
                    fechamento = _fim_do_bloco(codigo, abertura)
                    if fechamento > abertura:
                        codigo = codigo[: achado.start()] + codigo[fechamento + 1 :]
                        removidos += 1
                        alterou = True
                        break
        if alterou:
            continue

        achado = _PADRAO_IF_VERDADEIRO.search(codigo)
        if achado:
            abertura = codigo.find("{", achado.start())
            if abertura >= 0:
                fechamento = _fim_do_bloco(codigo, abertura)
                if fechamento > abertura:
                    interno = codigo[abertura + 1 : fechamento]
                    codigo = codigo[: achado.start()] + interno + codigo[fechamento + 1 :]
                    removidos += 1
                    alterou = True
        if alterou:
            continue

        achado = _PADRAO_IF_SEM_BLOCO.search(codigo)
        if achado:
            codigo = codigo[: achado.start()] + codigo[achado.end() :]
            removidos += 1
            continue
        break
    return codigo, removidos


# ---------------------------------------------------------------------- diff
def gerar_diff_lado_a_lado(original: str, resultado: str, limite: int = 5000) -> List[Tuple[str, str]]:
    """Compara as linhas e devolve pares (esquerda, direita) para exibição."""
    esquerda = original.splitlines()
    direita = resultado.splitlines()
    comparador = difflib.SequenceMatcher(None, esquerda, direita)
    linhas: List[Tuple[str, str]] = []
    for bloco in comparador.get_opcodes():
        tipo, i1, i2, j1, j2 = bloco
        if tipo == "equal":
            for deslocamento in range(i2 - i1):
                linhas.append((esquerda[i1 + deslocamento], direita[j1 + deslocamento]))
        elif tipo == "replace":
            comprimento = max(i2 - i1, j2 - j1)
            for deslocamento in range(comprimento):
                esq = esquerda[i1 + deslocamento] if i1 + deslocamento < i2 else ""
                dir_ = direita[j1 + deslocamento] if j1 + deslocamento < j2 else ""
                linhas.append((esq, dir_))
        elif tipo == "delete":
            for deslocamento in range(i1, i2):
                linhas.append((esquerda[deslocamento], ""))
        elif tipo == "insert":
            for deslocamento in range(j1, j2):
                linhas.append(("", direita[deslocamento]))
        if len(linhas) >= limite:
            break
    return linhas


# ------------------------------------------------------------------ pipeline
def desofuscar(codigo: str, opcoes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Executa o pipeline de desofuscação e devolve o resultado e o relatório."""
    opcoes = {
        "desescapar": True,
        "fromcharcode": True,
        "eval": True,
        "renomear": True,
        "codigo_morto": True,
        "formatar": True,
        "motor": "auto",
        **(opcoes or {}),
    }
    original = str(codigo or "")
    if not original.strip():
        raise ValueError("Informe o código JavaScript a desofuscar.")

    atual = original
    relatorio: Dict[str, Any] = {
        "desescapados": 0,
        "fromcharcode": 0,
        "evals_resolvidos": 0,
        "identificadores_renomeados": 0,
        "blocos_mortos": 0,
        "formatado": False,
        "motor_formatacao": "desativado",
        "tamanho_original": len(original),
        "tamanho_final": len(original),
    }

    if opcoes.get("desescapar"):
        atual, quantidade = desescapar(atual)
        relatorio["desescapados"] = quantidade
    if opcoes.get("fromcharcode"):
        atual, quantidade = resolver_fromcharcode(atual)
        relatorio["fromcharcode"] = quantidade
    if opcoes.get("eval"):
        atual, quantidade = desembrulhar_eval(atual)
        relatorio["evals_resolvidos"] = quantidade
    mapa: Dict[str, str] = {}
    if opcoes.get("renomear"):
        atual, quantidade, mapa = renomear_hex(atual)
        relatorio["identificadores_renomeados"] = quantidade
    if opcoes.get("codigo_morto"):
        atual, quantidade = remover_codigo_morto(atual)
        relatorio["blocos_mortos"] = quantidade
    if opcoes.get("formatar"):
        motor = str(opcoes.get("motor") or "auto")
        if motor in {"auto", "jsbeautifier"} and dependencia_disponivel("jsbeautifier"):
            try:
                import jsbeautifier

                atual = jsbeautifier.beautify(atual)
                relatorio["formatado"] = True
                relatorio["motor_formatacao"] = "jsbeautifier"
            except Exception as exc:  # noqa: BLE001
                _log.warning("jsbeautifier falhou (%s); usando formatador nativo.", exc)
                atual = formatar_js(atual)
                relatorio["formatado"] = True
                relatorio["motor_formatacao"] = "nativo (fallback)"
        elif motor == "jsbeautifier" and not dependencia_disponivel("jsbeautifier"):
            atual = formatar_js(atual)
            relatorio["formatado"] = True
            relatorio["motor_formatacao"] = "nativo (jsbeautifier ausente)"
        else:
            atual = formatar_js(atual)
            relatorio["formatado"] = True
            relatorio["motor_formatacao"] = "nativo"

    relatorio["tamanho_final"] = len(atual)
    relatorio["mapa_identificadores"] = mapa
    return {
        "codigo": atual,
        "original": original,
        "relatorio": relatorio,
        "diff": gerar_diff_lado_a_lado(original, atual),
    }


def resumo_relatorio(relatorio: Dict[str, Any]) -> str:
    """Texto curto com as transformações aplicadas."""
    linhas = [
        f"Tamanho original: {formatar_numero(relatorio.get('tamanho_original', 0))} caracteres",
        f"Tamanho final: {formatar_numero(relatorio.get('tamanho_final', 0))} caracteres",
        f"Escapes convertidos: {relatorio.get('desescapados', 0)}",
        f"Chamadas fromCharCode resolvidas: {relatorio.get('fromcharcode', 0)}",
        f"Blocos eval desembrulhados: {relatorio.get('evals_resolvidos', 0)}",
        f"Identificadores _0x renomeados: {relatorio.get('identificadores_renomeados', 0)}",
        f"Blocos de código morto removidos: {relatorio.get('blocos_mortos', 0)}",
        f"Formatação: {relatorio.get('motor_formatacao', 'desativado')}",
    ]
    return "\n".join(linhas)


@register
class JsDeobfuscatorTool(Tool):
    """Ferramenta de desofuscação de JavaScript."""

    id = "rev.js_deobfuscator"
    name = "Desofuscador de JavaScript"
    category = "Reverse Engineering"
    description = (
        "Desescapa sequências, resolve String.fromCharCode, desembrulha eval literal, "
        "renomeia identificadores _0x, remove código morto simples e mostra o diff lado a lado"
    )
    keywords = [
        "javascript", "js", "desofuscar", "ofuscado", "beautifier", "pretty print",
        "eval", "unpacker", "identificadores", "diff", "engenharia reversa",
    ]
    optional_deps = ["jsbeautifier"]

    def build_view(self, parent: Optional[QWidget] = None) -> QWidget:
        return JsDeobfuscatorView(self, parent)


class JsDeobfuscatorView(PainelFerramenta):
    """Painel interativo do desofuscador."""

    def __init__(self, tool: JsDeobfuscatorTool, parent: Optional[QWidget] = None) -> None:
        super().__init__(tool, parent)
        self._resultado: Dict[str, Any] = {}
        self._executando = False

        motor = "jsbeautifier instalado" if dependencia_disponivel("jsbeautifier") else "formatador nativo"
        self.adicionar_aviso(
            f"Motor de formatação disponível: {motor}. O desofuscador não executa o código: "
            "ele apenas transforma o texto informado.",
            destaque=False,
        )

        card_opcoes, layout_opcoes = self.adicionar_card("Etapas e opções")
        linha_1 = QHBoxLayout()
        self.chk_desescapar = QCheckBox("Converter escapes (\\x, \\u, octal)")
        self.chk_desescapar.setChecked(True)
        self.chk_fromcharcode = QCheckBox("Resolver String.fromCharCode")
        self.chk_fromcharcode.setChecked(True)
        self.chk_eval = QCheckBox("Desembrulhar eval literal")
        self.chk_eval.setChecked(True)
        for caixa in (self.chk_desescapar, self.chk_fromcharcode, self.chk_eval):
            linha_1.addWidget(caixa)
        layout_opcoes.addLayout(linha_1)

        linha_2 = QHBoxLayout()
        self.chk_renomear = QCheckBox("Renomear identificadores _0x")
        self.chk_renomear.setChecked(True)
        self.chk_morto = QCheckBox("Remover código morto")
        self.chk_morto.setChecked(True)
        self.chk_formatar = QCheckBox("Formatar código")
        self.chk_formatar.setChecked(True)
        for caixa in (self.chk_renomear, self.chk_morto, self.chk_formatar):
            linha_2.addWidget(caixa)

        linha_2.addWidget(QLabel("Motor:"))
        self.cmb_motor = QComboBox()
        self.cmb_motor.addItem("Automático", "auto")
        self.cmb_motor.addItem("jsbeautifier (se instalado)", "jsbeautifier")
        self.cmb_motor.addItem("Nativo", "nativo")
        self.cmb_motor.setEnabled(dependencia_disponivel("jsbeautifier"))
        linha_2.addWidget(self.cmb_motor)
        linha_2.addStretch()
        layout_opcoes.addLayout(linha_2)

        linha_acoes = QHBoxLayout()
        btn_carregar = QPushButton("Carregar .js...")
        btn_carregar.clicked.connect(self._carregar)
        linha_acoes.addWidget(btn_carregar)
        self.btn_desofuscar = QPushButton("Desofuscar")
        self.btn_desofuscar.setProperty("class", "primary")
        self.btn_desofuscar.clicked.connect(self._desofuscar)
        linha_acoes.addWidget(self.btn_desofuscar)
        self.btn_exportar = QPushButton("Exportar resultado...")
        self.btn_exportar.clicked.connect(self._exportar)
        linha_acoes.addWidget(self.btn_exportar)
        self.btn_copiar = botao_copiar(lambda: self.saida.toPlainText(), self, "Copiar resultado")
        linha_acoes.addWidget(self.btn_copiar)
        btn_limpar = QPushButton("Limpar")
        btn_limpar.clicked.connect(self._limpar)
        linha_acoes.addWidget(btn_limpar)
        linha_acoes.addStretch()
        layout_opcoes.addLayout(linha_acoes)

        self.lbl_status = QLabel("Nenhuma desofuscação executada.")
        self.lbl_status.setWordWrap(True)
        layout_opcoes.addWidget(self.lbl_status)

        card_textos, layout_textos = self.adicionar_card("Código original e desofuscado")
        linha_textos = QHBoxLayout()
        coluna_entrada = QVBoxLayout()
        coluna_entrada.addWidget(QLabel("Original (editável):"))
        self.entrada = QPlainTextEdit()
        self.entrada.setPlaceholderText("Cole o JavaScript ofuscado ou carregue um arquivo .js")
        self.entrada.setMinimumHeight(300)
        coluna_entrada.addWidget(self.entrada)
        linha_textos.addLayout(coluna_entrada, 1)

        coluna_saida = QVBoxLayout()
        coluna_saida.addWidget(QLabel("Desofuscado:"))
        self.saida = criar_saida_texto(300, self)
        coluna_saida.addWidget(self.saida)
        linha_textos.addLayout(coluna_saida, 1)
        layout_textos.addLayout(linha_textos)

        card_diff, layout_diff = self.adicionar_card("Diferenças lado a lado")
        self.tabela_diff = criar_tabela(["Original", "Desofuscado"], self)
        self.tabela_diff.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela_diff.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout_diff.addWidget(self.tabela_diff)

        card_rel, layout_rel = self.adicionar_card("Relatório")
        self.relatorio = criar_saida_texto(140, self)
        layout_rel.addWidget(self.relatorio)

        self.log = adicionar_log_painel(self, "Log da desofuscação")
        self.adicionar_espaco()

    # ------------------------------------------------------------------ ações
    def _carregar(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Carregar JavaScript", "", "JavaScript (*.js *.mjs *.cjs);;Todos os arquivos (*.*)"
        )
        if not caminho:
            return
        try:
            codigo = Path(caminho).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            mostrar_erro(self, "Falha ao ler o arquivo", exc)
            return
        self.entrada.setPlainText(codigo)
        self.lbl_status.setText(f"Arquivo carregado: {caminho} ({formatar_numero(len(codigo))} caracteres).")

    def _limpar(self) -> None:
        self.entrada.clear()
        self.saida.clear()
        self.relatorio.clear()
        self.tabela_diff.setRowCount(0)
        self._resultado = {}
        self.lbl_status.setText("Campos limpos.")

    def _definir_execucao(self, ativa: bool) -> None:
        self._executando = ativa
        for botao in (self.btn_desofuscar, self.btn_exportar):
            botao.setEnabled(not ativa)

    def _desofuscar(self) -> None:
        if self._executando:
            return
        codigo = self.entrada.toPlainText()
        if not codigo.strip():
            mostrar_erro(self, "Código vazio", "Cole o JavaScript ofuscado ou carregue um arquivo.")
            return

        opcoes = {
            "desescapar": self.chk_desescapar.isChecked(),
            "fromcharcode": self.chk_fromcharcode.isChecked(),
            "eval": self.chk_eval.isChecked(),
            "renomear": self.chk_renomear.isChecked(),
            "codigo_morto": self.chk_morto.isChecked(),
            "formatar": self.chk_formatar.isChecked(),
            "motor": self.cmb_motor.currentData() or "auto",
        }

        self._definir_execucao(True)
        self.lbl_status.setText("Desofuscando...")
        self.log.append_log("INFO", f"Desofuscando {formatar_numero(len(codigo))} caracteres.")

        def tarefa(ctx):
            resultado = desofuscar(codigo, opcoes)
            ctx.log("INFO", f"Formatação: {resultado['relatorio']['motor_formatacao']}.")
            return resultado

        def concluiu(resultado) -> None:
            self._definir_execucao(False)
            self._resultado = resultado or {}
            self.saida.setPlainText(self._resultado.get("codigo", ""))
            self.relatorio.setPlainText(resumo_relatorio(self._resultado.get("relatorio", {})))
            self._preencher_diff(self._resultado.get("diff", []))
            self.lbl_status.setText(
                f"Concluído: {formatar_numero(self._resultado.get('relatorio', {}).get('tamanho_final', 0))} "
                "caracteres gerados."
            )
            self.log.append_log("INFO", "Desofuscação concluída.")

        def falhou(erro: Exception) -> None:
            self._definir_execucao(False)
            self.lbl_status.setText("Falha na desofuscação.")
            self.log.append_log("ERROR", str(erro))
            mostrar_erro(self, "Falha na desofuscação", erro)

        executar_assincrono(self, tarefa, concluiu, falhou)

    def _preencher_diff(self, linhas: Sequence[Tuple[str, str]]) -> None:
        if not linhas:
            linhas = [("(sem diferenças)", "")]
        preencher_tabela(self.tabela_diff, [[esquerda, direita] for esquerda, direita in linhas[:2000]])

    def _exportar(self) -> None:
        if not self._resultado.get("codigo"):
            mostrar_erro(self, "Nada para exportar", "Execute a desofuscação antes de exportar.")
            return
        destino, _ = QFileDialog.getSaveFileName(
            self, "Salvar resultado", "desofuscado.js", "JavaScript (*.js);;Texto (*.txt)"
        )
        if not destino:
            return
        try:
            Path(destino).write_text(self._resultado["codigo"], encoding="utf-8")
            self.lbl_status.setText(f"Resultado exportado para {destino}.")
            self.log.append_log("INFO", f"Resultado gravado em {destino}.")
        except OSError as exc:
            mostrar_erro(self, "Falha ao exportar", exc)
