"""Identificação heurística de formatos de hash.

A análise é local e não realiza nenhuma consulta de rede. O resultado é uma
lista ordenada por confiança, pois formatos como MD5 e NTLM compartilham o mesmo
comprimento e só podem ser diferenciados pelo contexto de uso.
"""
from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Pattern


@dataclass(frozen=True)
class HashCandidate:
    """Candidato de algoritmo identificado para uma string."""

    algorithm: str
    confidence: str
    reason: str
    hashcat_mode: Optional[int] = None
    example: str = ""
    expected_length: Optional[int] = None

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _Assinatura:
    nome: str
    padrao: Pattern[str]
    confianca: str
    motivo: str
    modo_hashcat: Optional[int]
    exemplo: str
    comprimento: Optional[int] = None


# Ordem importa: assinaturas com prefixo inequívoco vêm antes das heurísticas
# puramente baseadas em comprimento.
_ASSINATURAS: tuple[_Assinatura, ...] = (
    _Assinatura(
        "bcrypt",
        re.compile(r"^\$2[abxy]?\$\d{2}\$[./A-Za-z0-9]{53}$"),
        "Alto",
        "Prefixo bcrypt ($2a$, $2b$, $2y$ ou $2x$) com salt e custo explícitos.",
        3200,
        "$2b$12$ExemploDeHashBcryptCom53CaracteresNoFinal1234567890abc",
        60,
    ),
    _Assinatura(
        "argon2id",
        re.compile(r"^\$argon2id\$v=\d+\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+$"),
        "Alto",
        "Formato PHC argon2id com parâmetros de memória, tempo e paralelismo.",
        34000,
        "$argon2id$v=19$m=65536,t=3,p=4$c2FsdA$hash",
    ),
    _Assinatura(
        "argon2i",
        re.compile(r"^\$argon2i\$v=\d+\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+$"),
        "Alto",
        "Formato PHC argon2i.",
        34000,
        "$argon2i$v=19$m=65536,t=3,p=4$c2FsdA$hash",
    ),
    _Assinatura(
        "argon2 (genérico)",
        re.compile(r"^\$argon2(id|i|d)\$"),
        "Médio",
        "Prefixo Argon2 detectado; o modo Hashcat depende da variante.",
        34000,
        "$argon2id$v=19$m=65536,t=3,p=4$...",
    ),
    _Assinatura(
        "scrypt",
        re.compile(r"^\$scrypt\$ln=\d+,r=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+$"),
        "Alto",
        "Formato PHC scrypt com parâmetros ln, r e p.",
        8900,
        "$scrypt$ln=16,r=8,p=1$c2FsdA$hash",
    ),
    _Assinatura(
        "Django (PBKDF2-SHA256)",
        re.compile(r"^pbkdf2_sha256\$\d+\$[^$]+\$[A-Za-z0-9+/=]+$"),
        "Alto",
        "Formato do framework Django: pbkdf2_sha256$iterações$salt$hash.",
        10000,
        "pbkdf2_sha256$600000$salt$hash",
    ),
    _Assinatura(
        "Django (PBKDF2-SHA1)",
        re.compile(r"^pbkdf2_sha1\$\d+\$[^$]+\$[A-Za-z0-9+/=]+$"),
        "Alto",
        "Formato do framework Django com PBKDF2-SHA1.",
        12000,
        "pbkdf2_sha1$600000$salt$hash",
    ),
    _Assinatura(
        "WordPress / PHPass",
        re.compile(r"^\$[PH]\$[A-Za-z0-9./]{31}$"),
        "Alto",
        "Formato Portable PHP password hashing ($P$ ou $H$), usado pelo WordPress.",
        400,
        "$P$BExemploDeHashWordPress1234567890",
        34,
    ),
    _Assinatura(
        "Joomla",
        re.compile(r"^[0-9a-f]{32}:[A-Za-z0-9]{16,32}$", re.IGNORECASE),
        "Alto",
        "Hash Joomla no formato hash:salt.",
        None,
        "5d41402abc4b2a76b9719d911017c592:abcdefghijklmnop",
    ),
    _Assinatura(
        "Drupal 7",
        re.compile(r"^\$S\$[A-Za-z0-9./]{52}$"),
        "Alto",
        "Prefixo $S$ do Drupal 7 (SHA-512 com salt).",
        7900,
        "$S$ExemploDeHashDrupal7ComSalt...",
        55,
    ),
    _Assinatura(
        "MySQL 4.1+ / MySQL 5 (native)",
        re.compile(r"^\*[0-9A-F]{40}$"),
        "Alto",
        "Hash nativo do MySQL 4.1+ começa com asterisco e possui 40 hexadecimais.",
        300,
        "*2470C0C06DEE42FD1618BB99005ADCA2EC9D1E19",
        41,
    ),
    _Assinatura(
        "MySQL 3 (old)",
        re.compile(r"^[0-9a-f]{16}$", re.IGNORECASE),
        "Baixo",
        "Comprimento de 16 caracteres é compatível com MySQL 3, CRC ou outro hash curto.",
        200,
        "5d41402abc4b2a76",
        16,
    ),
    _Assinatura(
        "LM (LAN Manager)",
        re.compile(r"^[0-9A-F]{32}$"),
        "Médio",
        "32 hexadecimais maiúsculos são compatíveis com LM; confirme se o sistema é legado.",
        3000,
        "299BD128C1101FD6D2D4D4B0B2D2D4D4",
        32,
    ),
    _Assinatura(
        "NTLM",
        re.compile(r"^[0-9a-fA-F]{32}$"),
        "Médio",
        "32 hexadecimais também correspondem a NTLM (MD4 da senha em UTF-16LE).",
        1000,
        "8846f7eaee8fb117ad06bdd830b7586c",
        32,
    ),
    _Assinatura(
        "MD5",
        re.compile(r"^[0-9a-fA-F]{32}$"),
        "Médio",
        "Formato hexadecimal de 128 bits, típico de MD5.",
        0,
        "5d41402abc4b2a76b9719d911017c592",
        32,
    ),
    _Assinatura(
        "SHA-1",
        re.compile(r"^[0-9a-fA-F]{40}$"),
        "Alto",
        "Formato hexadecimal de 160 bits, típico de SHA-1.",
        100,
        "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d",
        40,
    ),
    _Assinatura(
        "RIPEMD-160",
        re.compile(r"^[0-9a-fA-F]{40}$"),
        "Baixo",
        "Também possui 40 hexadecimais; diferencie de SHA-1 pelo contexto.",
        6000,
        "108f07b8382412612c048d07d13f814118445acd",
        40,
    ),
    _Assinatura(
        "SHA-224",
        re.compile(r"^[0-9a-fA-F]{56}$"),
        "Alto",
        "Formato hexadecimal de 224 bits.",
        1300,
        "ea09ae9cc6768c50fcee903ed054556e5bfc8347907f12598aa24193",
        56,
    ),
    _Assinatura(
        "SHA-256",
        re.compile(r"^[0-9a-fA-F]{64}$"),
        "Alto",
        "Formato hexadecimal de 256 bits, típico de SHA-256.",
        1400,
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        64,
    ),
    _Assinatura(
        "SHA3-256",
        re.compile(r"^[0-9a-fA-F]{64}$"),
        "Baixo",
        "SHA3-256 usa 64 hexadecimais e só pode ser distinguido pelo contexto.",
        17400,
        "3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532",
        64,
    ),
    _Assinatura(
        "BLAKE2s-256",
        re.compile(r"^[0-9a-fA-F]{64}$"),
        "Baixo",
        "BLAKE2s também produz 256 bits em hexadecimal.",
        None,
        "5d41402abc4b2a76b9719d911017c5925d41402abc4b2a76b9719d911017c592",
        64,
    ),
    _Assinatura(
        "SHA-384",
        re.compile(r"^[0-9a-fA-F]{96}$"),
        "Alto",
        "Formato hexadecimal de 384 bits.",
        10800,
        "59e1748777448c69de6b800d7a33bbfb9ff1b463e44354c3553bcdb9c666fa90125a3c79f90397bdf5f6a13de828684f",
        96,
    ),
    _Assinatura(
        "SHA3-384",
        re.compile(r"^[0-9a-fA-F]{96}$"),
        "Baixo",
        "SHA3-384 compartilha 96 hexadecimais com SHA-384.",
        17400,
        "2c23146a63a29acf99e73b88f8c24eaa7dc60aa771780ccc006afbfa8fe2479b2dd2b21362337441ac12b515911957ff",
        96,
    ),
    _Assinatura(
        "SHA-512",
        re.compile(r"^[0-9a-fA-F]{128}$"),
        "Alto",
        "Formato hexadecimal de 512 bits.",
        1700,
        "9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043",
        128,
    ),
    _Assinatura(
        "SHA3-512",
        re.compile(r"^[0-9a-fA-F]{128}$"),
        "Baixo",
        "SHA3-512 compartilha 128 hexadecimais com SHA-512.",
        17600,
        "b751850b1a57168a5693cd924b6b096e08f621827444f70d884f5d0240d2712e10e116e9192af3c91a7ec57647e3934057340b4cf408d5a56592f8274eec53f0",
        128,
    ),
    _Assinatura(
        "CRC32",
        re.compile(r"^[0-9a-fA-F]{8}$"),
        "Baixo",
        "8 hexadecimais correspondem a verificações curtíssimas como CRC32.",
        None,
        "5d41402a",
        8,
    ),
    _Assinatura(
        "Unix crypt (DES)",
        re.compile(r"^[./0-9A-Za-z]{13}$"),
        "Médio",
        "13 caracteres de alfabeto crypt são compatíveis com o antigo DES crypt.",
        1500,
        "abJnggxhB/yWI",
        13,
    ),
    _Assinatura(
        "SHA-512 crypt (Linux)",
        re.compile(r"^\$6\$[^\$]{1,16}\$[./0-9A-Za-z]{86}$"),
        "Alto",
        "Formato modular crypt $6$ (SHA-512).",
        1800,
        "$6$salt$hash",
        106,
    ),
    _Assinatura(
        "SHA-256 crypt (Linux)",
        re.compile(r"^\$5\$[^\$]{1,16}\$[./0-9A-Za-z]{43}$"),
        "Alto",
        "Formato modular crypt $5$ (SHA-256).",
        7400,
        "$5$salt$hash",
        63,
    ),
    _Assinatura(
        "bcrypt (SHA-256, sistema)",
        re.compile(r"^\$sha256\$[^\$]+\$[A-Za-z0-9+/=]+$"),
        "Alto",
        "Variante $sha256$ de sistemas Unix.",
        None,
        "$sha256$salt$hash",
    ),
)

_NOMES_POR_COMPRIMENTO: Dict[int, List[HashCandidate]] = {}


def _normalizar(valor: str) -> str:
    """Remove espaços, aspas e prefixos ``hash:`` comuns em dumps."""
    texto = str(valor or "").strip().strip('"\'')
    if ":" in texto and not texto.startswith("$"):
        partes = texto.split(":")
        if len(partes) == 2 and len(partes[0]) >= 32 and re.fullmatch(r"[0-9a-fA-F]+", partes[0] or ""):
            return partes[0]
    return texto


def _eh_base64_de_hash(texto: str) -> Optional[HashCandidate]:
    """Reconhece Base64 cujo conteúdo decodificado é um hash hexadecimal."""
    if len(texto) < 20 or len(texto) > 180 or not re.fullmatch(r"[A-Za-z0-9+/=_-]+", texto):
        return None
    if re.fullmatch(r"[0-9a-fA-F]+", texto):
        return None
    try:
        bruto = base64.b64decode(texto.replace("-", "+").replace("_", "/") + "=" * (-len(texto) % 4), validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(bruto) < 12:
        return None
    decodificado = bruto.hex()
    candidatos = identify_hash(decodificado, _permitir_base64=False)
    if not candidatos:
        return None
    interno = candidatos[0]
    return HashCandidate(
        algorithm=f"Base64 de {interno.algorithm}",
        confidence="Médio",
        reason=f"O conteúdo decodificado em Base64 tem {len(bruto) * 8} bits e parece {interno.algorithm}.",
        hashcat_mode=interno.hashcat_mode,
        example="Texto Base64 que decodifica para um hash hexadecimal.",
        expected_length=len(texto),
    )


def identify_hash(valor: str, _permitir_base64: bool = True) -> List[HashCandidate]:
    """Retorna candidatos de algoritmo, do mais provável ao menos provável."""
    texto = _normalizar(valor)
    if not texto:
        return []

    candidatos: List[HashCandidate] = []
    for assinatura in _ASSINATURAS:
        if assinatura.padrao.fullmatch(texto):
            candidato = HashCandidate(
                algorithm=assinatura.nome,
                confidence=assinatura.confianca,
                reason=assinatura.motivo,
                hashcat_mode=assinatura.modo_hashcat,
                example=assinatura.exemplo,
                expected_length=assinatura.comprimento if assinatura.comprimento is not None else len(texto),
            )
            if candidato not in candidatos:
                candidatos.append(candidato)

    # Assinaturas ambiguas de mesmo comprimento são mantidas; a ordenação
    # coloca confiança Alta antes de Média/Baixa.
    if _permitir_base64:
        b64 = _eh_base64_de_hash(texto)
        if b64 is not None and b64 not in candidatos:
            candidatos.append(b64)

    ordem = {"Alto": 0, "Médio": 1, "Baixa": 2, "Baixo": 2}
    candidatos.sort(key=lambda c: (ordem.get(c.confidence, 9), c.algorithm.lower()))

    # Evita repetir o mesmo algoritmo por assinaturas genéricas.
    vistos: set[str] = set()
    unicos: List[HashCandidate] = []
    for candidato in candidatos:
        chave = candidato.algorithm.lower()
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(candidato)
    return unicos


def identify_hash_type(valor: str) -> Optional[str]:
    """Atalho que devolve apenas o nome do candidato mais provável."""
    candidatos = identify_hash(valor)
    return candidatos[0].algorithm if candidatos else None


def hashcat_command(candidato: HashCandidate, hash_alvo: str, wordlist: str = "wordlist.txt") -> str:
    """Monta uma linha de comando de referência para o Hashcat."""
    if candidato.hashcat_mode is None:
        return "# Este formato não possui modo Hashcat direto; use o modo nativo em CPU."
    return f'hashcat -m {candidato.hashcat_mode} -a 0 "{hash_alvo}" "{wordlist}"'
