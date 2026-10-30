"""Análise e quebra de segredo HMAC de tokens JWT.

Implementação sem PyJWT: apenas base64url, HMAC e comparação em tempo constante.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import itertools
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from wintoolbox.tools._helpers import base64url_decode, base64url_encode
from wintoolbox.tools.security.common import SENHAS_COMUNS
from wintoolbox.tools.security.hash_cracker.logic import CHARSETS, carregar_wordlist


class JWTInvalido(ValueError):
    """Token malformado ou algoritmo não suportado."""


@dataclass
class JWTInfo:
    """Partes decodificadas de um JWT."""

    token: str
    header: Dict[str, object]
    payload: Dict[str, object]
    signature: bytes
    signing_input: bytes
    algorithm: str
    header_b64: str
    payload_b64: str
    signature_b64: str

    @property
    def expirado(self) -> bool:
        exp = self.payload.get("exp")
        if not isinstance(exp, (int, float)):
            return False
        return float(exp) < time.time()

    @property
    def expiracao_legivel(self) -> str:
        exp = self.payload.get("exp")
        if not isinstance(exp, (int, float)):
            return "Não informada"
        try:
            return datetime.fromtimestamp(float(exp), tz=timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return str(exp)

    @property
    def emitido_legivel(self) -> str:
        iat = self.payload.get("iat")
        if not isinstance(iat, (int, float)):
            return "Não informado"
        try:
            return datetime.fromtimestamp(float(iat), tz=timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return str(iat)


@dataclass
class JWTCrackResult:
    """Resultado da busca pelo segredo HMAC."""

    found: bool
    secret: Optional[str] = None
    attempts: int = 0
    elapsed: float = 0.0
    rate: float = 0.0
    cancelled: bool = False

    def resumo(self) -> str:
        if self.found:
            return f"Segredo encontrado após {self.attempts} tentativa(s): {self.secret}"
        if self.cancelled:
            return f"Cancelado após {self.attempts} tentativa(s)."
        return f"Segredo não encontrado após {self.attempts} tentativa(s)."


_ALGORITMOS = {
    "HS256": hashlib.sha256,
    "HS384": hashlib.sha384,
    "HS512": hashlib.sha512,
}


def parse_jwt(token: str) -> JWTInfo:
    """Decodifica header/payload e valida a estrutura de três partes."""
    texto = str(token or "").strip()
    partes = texto.split(".")
    if len(partes) != 3:
        raise JWTInvalido("O JWT deve possuir exatamente três partes separadas por ponto.")
    header_b64, payload_b64, signature_b64 = partes
    try:
        header = json.loads(base64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(base64url_decode(payload_b64).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JWTInvalido(f"Header ou payload não são JSON Base64URL válido: {exc}") from exc
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise JWTInvalido("Header e payload devem ser objetos JSON.")
    algoritmo = str(header.get("alg", "")).upper()
    try:
        assinatura = base64url_decode(signature_b64) if signature_b64 else b""
    except (ValueError, binascii.Error) as exc:
        raise JWTInvalido("Assinatura Base64URL inválida.") from exc
    return JWTInfo(
        token=texto,
        header=header,
        payload=payload,
        signature=assinatura,
        signing_input=f"{header_b64}.{payload_b64}".encode("ascii"),
        algorithm=algoritmo,
        header_b64=header_b64,
        payload_b64=payload_b64,
        signature_b64=signature_b64,
    )


def assinar(signing_input: bytes, segredo: str, algoritmo: str = "HS256") -> bytes:
    """Calcula a assinatura HMAC do conteúdo informado."""
    funcao = _ALGORITMOS.get(str(algoritmo).upper())
    if funcao is None:
        raise JWTInvalido(f"Algoritmo {algoritmo} não suportado para HMAC. Use HS256, HS384 ou HS512.")
    return hmac.new(segredo.encode("utf-8"), signing_input, funcao).digest()


def verificar_assinatura(token: str, segredo: str) -> bool:
    """Compara a assinatura do token com a calculada em tempo constante."""
    info = parse_jwt(token)
    if info.algorithm not in _ALGORITMOS:
        return False
    esperado = assinar(info.signing_input, segredo, info.algorithm)
    return hmac.compare_digest(esperado, info.signature)


def crack_jwt_secret(
    token: str,
    candidatos: Iterable[str],
    on_progresso: Optional[Callable[[int, str], None]] = None,
    cancelado: Optional[Callable[[], bool]] = None,
    intervalo: int = 250,
) -> JWTCrackResult:
    """Testa segredos de um iterável contra a assinatura do token."""
    info = parse_jwt(token)
    if info.algorithm not in _ALGORITMOS:
        raise JWTInvalido(
            f"Algoritmo {info.algorithm or 'ausente'} não é HMAC. "
            "Ataques de segredo só se aplicam a HS256, HS384 e HS512."
        )

    inicio = time.perf_counter()
    tentativas = 0
    for candidato in candidatos:
        if cancelado and cancelado():
            decorrido = time.perf_counter() - inicio
            return JWTCrackResult(
                found=False, attempts=tentativas, elapsed=decorrido,
                rate=tentativas / decorrido if decorrido else 0.0, cancelled=True,
            )
        tentativas += 1
        calculada = assinar(info.signing_input, candidato, info.algorithm)
        if hmac.compare_digest(calculada, info.signature):
            decorrido = time.perf_counter() - inicio
            return JWTCrackResult(
                found=True, secret=candidato, attempts=tentativas,
                elapsed=decorrido, rate=tentativas / decorrido if decorrido else 0.0,
            )
        if on_progresso and tentativas % intervalo == 0:
            on_progresso(tentativas, candidato)

    decorrido = time.perf_counter() - inicio
    return JWTCrackResult(
        found=False, attempts=tentativas, elapsed=decorrido,
        rate=tentativas / decorrido if decorrido else 0.0,
    )


def gerar_candidatos_wordlist(caminho: Optional[Path], texto_inline: str = "") -> List[str]:
    """Combina lista interna, arquivo e linhas coladas, sem duplicatas."""
    candidatos: List[str] = []
    if texto_inline.strip():
        candidatos.extend(linha.strip() for linha in texto_inline.splitlines() if linha.strip())
    if caminho is not None:
        candidatos.extend(carregar_wordlist(caminho))
    else:
        candidatos.extend(SENHAS_COMUNS)
    vistos = set()
    saida: List[str] = []
    for candidato in candidatos:
        if candidato not in vistos:
            vistos.add(candidato)
            saida.append(candidato)
    return saida


def gerar_candidatos_forca_bruta(charset: str, minimo: int, maximo: int) -> Iterable[str]:
    """Gera combinações sob demanda, sem carregar tudo em memória."""
    for tamanho in range(minimo, maximo + 1):
        for combinacao in itertools.product(charset, repeat=tamanho):
            yield "".join(combinacao)


def gerar_jwt(
    payload: Dict[str, object],
    segredo: str,
    algoritmo: str = "HS256",
    header_extra: Optional[Dict[str, object]] = None,
) -> str:
    """Cria um JWT assinado com HMAC para validar o segredo encontrado."""
    algoritmo = str(algoritmo).upper()
    if algoritmo not in _ALGORITMOS:
        raise JWTInvalido("Algoritmo de assinatura inválido.")
    header = {"alg": algoritmo, "typ": "JWT"}
    if header_extra:
        header.update(header_extra)
    header_b64 = base64url_encode(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    payload_b64 = base64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    entrada = f"{header_b64}.{payload_b64}".encode("ascii")
    assinatura = assinar(entrada, segredo, algoritmo)
    return f"{header_b64}.{payload_b64}.{base64url_encode(assinatura)}"


def construir_token_sem_assinatura(token: str) -> str:
    """Produz o token com alg=none e assinatura vazia, para testes autorizados."""
    info = parse_jwt(token)
    header = dict(info.header)
    header["alg"] = "none"
    header_b64 = base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    # Reutiliza o mesmo payload original, sem reinterpretar.
    payload_b64 = base64url_encode(json.dumps(info.payload, separators=(",", ":")).encode("utf-8"))
    return f"{header_b64}.{payload_b64}."


def resumo_token(info: JWTInfo) -> str:
    """Texto legível com algoritmos, claims e validade."""
    linhas = [
        f"Algoritmo: {info.algorithm or 'ausente'}",
        f"Assinatura: {len(info.signature)} byte(s)",
        f"Emitido em: {info.emitido_legivel}",
        f"Expira em: {info.expiracao_legivel}",
    ]
    if info.expirado:
        linhas.append("Situação: TOKEN EXPIRADO")
    else:
        linhas.append("Situação: token dentro da validade ou sem exp")
    return "\n".join(linhas)
