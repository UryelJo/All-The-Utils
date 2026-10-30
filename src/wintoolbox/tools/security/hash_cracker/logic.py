"""Quebra de hashes em CPU com wordlist, força bruta e benchmark.

A implementação é intencionalmente local e auditável. O Hashcat é usado apenas
quando o usuário opta explicitamente e o executável está disponível.
"""
from __future__ import annotations

import hashlib
import itertools
import shutil
import struct
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from wintoolbox.tools.security.common import SENHAS_COMUNS


CHARSETS: Dict[str, str] = {
    "Minúsculas (a-z)": "abcdefghijklmnopqrstuvwxyz",
    "Maiúsculas (A-Z)": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "Dígitos (0-9)": "0123456789",
    "Alfanumérico (a-z, 0-9)": "abcdefghijklmnopqrstuvwxyz0123456789",
    "Alfanumérico completo": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "Símbolos comuns": "!@#$%&*()-_=+[]{};:,.<>?/",
    "Impressos ASCII": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%&*()-_=+[]{};:,.<>?/",
}

ALGORITMOS_HASHLIB: Dict[str, str] = {
    "MD5": "md5",
    "SHA-1": "sha1",
    "SHA-224": "sha224",
    "SHA-256": "sha256",
    "SHA-384": "sha384",
    "SHA-512": "sha512",
    "SHA3-256": "sha3_256",
    "SHA3-512": "sha3_512",
    "RIPEMD-160": "ripemd160",
}

MODOS_HASHCAT: Dict[str, int] = {
    "MD5": 0,
    "SHA-1": 100,
    "SHA-224": 1300,
    "SHA-256": 1400,
    "SHA-384": 10800,
    "SHA-512": 1700,
    "SHA3-256": 17400,
    "SHA3-512": 17600,
    "NTLM": 1000,
    "LM": 3000,
    "MySQL 4.1+ / MySQL 5 (native)": 300,
    "bcrypt": 3200,
    "argon2id": 34000,
    "Django (PBKDF2-SHA256)": 10000,
    "WordPress / PHPass": 400,
    "Drupal 7": 7900,
}


class HashNaoSuportado(ValueError):
    """Formato reconhecido, mas sem implementação nativa em CPU."""


@dataclass
class CrackResult:
    """Resultado de uma tentativa de quebra."""

    found: bool
    password: Optional[str] = None
    algorithm: str = ""
    attempts: int = 0
    elapsed: float = 0.0
    rate: float = 0.0
    cancelled: bool = False

    def resumo(self) -> str:
        if self.found:
            return (
                f"Senha encontrada com {self.algorithm} após {self.attempts} tentativa(s) "
                f"em {self.elapsed:.2f}s ({self.rate:,.0f} tentativas/s)."
            )
        if self.cancelled:
            return f"Cancelado após {self.attempts} tentativa(s)."
        return f"Não encontrada após {self.attempts} tentativa(s) em {self.elapsed:.2f}s."


def _md4(dados: bytes) -> bytes:
    """MD4 puro (RFC 1320), necessário para calcular NTLM sem pycryptodome."""
    mensagem = bytearray(dados)
    tamanho_bits = (len(dados) * 8) & 0xFFFFFFFFFFFFFFFF
    mensagem.append(0x80)
    while len(mensagem) % 64 != 56:
        mensagem.append(0)
    mensagem += struct.pack("<Q", tamanho_bits)

    a0, b0, c0, d0 = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476

    def _rotl(valor: int, n: int) -> int:
        return ((valor << n) | (valor >> (32 - n))) & 0xFFFFFFFF

    for offset in range(0, len(mensagem), 64):
        bloco = mensagem[offset : offset + 64]
        x = list(struct.unpack("<16I", bloco))
        a, b, c, d = a0, b0, c0, d0

        for i in range(16):
            k = i
            s = [3, 7, 11, 19][i % 4]
            a = _rotl((a + ((b & c) | (~b & d)) + x[k]) & 0xFFFFFFFF, s)
            a, b, c, d = d, a, b, c

        for i in range(16):
            k = (i % 4) * 4 + (i // 4)
            s = [3, 5, 9, 13][i % 4]
            a = _rotl((a + ((b & c) | (b & d) | (c & d)) + x[k] + 0x5A827999) & 0xFFFFFFFF, s)
            a, b, c, d = d, a, b, c

        for i in range(16):
            k = [0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15][i]
            s = [3, 9, 11, 15][i % 4]
            a = _rotl((a + (b ^ c ^ d) + x[k] + 0x6ED9EBA1) & 0xFFFFFFFF, s)
            a, b, c, d = d, a, b, c

        a0 = (a0 + a) & 0xFFFFFFFF
        b0 = (b0 + b) & 0xFFFFFFFF
        c0 = (c0 + c) & 0xFFFFFFFF
        d0 = (d0 + d) & 0xFFFFFFFF

    return struct.pack("<4I", a0, b0, c0, d0)


def calcular_hash(senha: str, algoritmo: str) -> str:
    """Calcula o hash de ``senha`` no algoritmo informado."""
    if algoritmo == "NTLM":
        return _md4(senha.encode("utf-16le")).hex()
    nome = ALGORITMOS_HASHLIB.get(algoritmo)
    if nome is None:
        raise HashNaoSuportado(
            f"O algoritmo {algoritmo} não é suportado no modo nativo em CPU. "
            "Use o Hashcat para formatos com salt."
        )
    try:
        return hashlib.new(nome, senha.encode("utf-8", errors="surrogatepass")).hexdigest()
    except ValueError as exc:
        raise HashNaoSuportado(
            f"O algoritmo {algoritmo} não está disponível nesta instalação do Python."
        ) from exc


def detectar_algoritmo(hash_alvo: str) -> str:
    """Escolhe o algoritmo nativo mais provável para o hash informado."""
    from wintoolbox.tools.security.hash_identify.logic import identify_hash

    candidatos = identify_hash(hash_alvo)
    for candidato in candidatos:
        if candidato.algorithm in ALGORITMOS_HASHLIB or candidato.algorithm == "NTLM":
            # 32 hexadecimais: MD5 é o uso mais comum em exercícios e dumps.
            if len(hash_alvo.strip()) == 32:
                return "MD5" if not hash_alvo.strip().isupper() else "NTLM"
            return candidato.algorithm
    return "MD5" if len(hash_alvo.strip()) == 32 else "SHA-256"


def carregar_wordlist(caminho: Optional[Path] = None, limite: int = 5_000_000) -> List[str]:
    """Carrega wordlist em UTF-8/Latin-1 ou recorre à lista interna de 100 senhas."""
    if caminho is None:
        return list(SENHAS_COMUNS)
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"Wordlist não encontrada: {caminho}")

    senhas: List[str] = []
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            with open(caminho, "r", encoding=codificacao, errors="strict") as fp:
                for linha in fp:
                    if len(senhas) >= limite:
                        break
                    senha = linha.rstrip("\r\n")
                    if senha:
                        senhas.append(senha)
            return senhas
        except UnicodeDecodeError:
            senhas.clear()
            continue
    with open(caminho, "r", encoding="utf-8", errors="replace") as fp:
        for linha in fp:
            if len(senhas) >= limite:
                break
            senha = linha.rstrip("\r\n")
            if senha:
                senhas.append(senha)
    return senhas


class HashCracker:
    """Executor de tentativas em CPU com cancelamento cooperativo."""

    def __init__(
        self,
        hash_alvo: str,
        algoritmo: Optional[str] = None,
        wordlist: Optional[Path] = None,
    ) -> None:
        self.hash_alvo = str(hash_alvo or "").strip().lower()
        if not self.hash_alvo:
            raise ValueError("Informe o hash alvo.")
        self.algoritmo = algoritmo or detectar_algoritmo(self.hash_alvo)
        self.wordlist = wordlist
        self.tentativas = 0
        self._inicio = 0.0

    def verificar(self, senha: str) -> bool:
        self.tentativas += 1
        try:
            return calcular_hash(senha, self.algoritmo).lower() == self.hash_alvo
        except HashNaoSuportado:
            raise

    def _resultado(self, senha: Optional[str], cancelado: bool = False) -> CrackResult:
        decorrido = max(0.0, time.perf_counter() - self._inicio)
        taxa = self.tentativas / decorrido if decorrido > 0 else 0.0
        return CrackResult(
            found=senha is not None,
            password=senha,
            algorithm=self.algoritmo,
            attempts=self.tentativas,
            elapsed=decorrido,
            rate=taxa,
            cancelled=cancelado,
        )

    def quebrar_wordlist(
        self,
        on_progresso: Optional[Callable[[int, str], None]] = None,
        cancelado: Optional[Callable[[], bool]] = None,
        pausado: Optional[Callable[[], bool]] = None,
        intervalo: int = 250,
    ) -> CrackResult:
        """Percorre a wordlist e retorna ao primeiro hash correspondente."""
        senhas = carregar_wordlist(self.wordlist)
        self.tentativas = 0
        self._inicio = time.perf_counter()
        for senha in senhas:
            if cancelado and cancelado():
                return self._resultado(None, cancelado=True)
            while pausado and pausado():
                if cancelado and cancelado():
                    return self._resultado(None, cancelado=True)
                time.sleep(0.1)
            if self.verificar(senha):
                return self._resultado(senha)
            if on_progresso and self.tentativas % intervalo == 0:
                on_progresso(self.tentativas, senha)
        if on_progresso:
            on_progresso(self.tentativas, "")
        return self._resultado(None)

    def quebrar_forca_bruta(
        self,
        charset: str,
        comprimento_min: int = 1,
        comprimento_max: int = 4,
        on_progresso: Optional[Callable[[int, str], None]] = None,
        cancelado: Optional[Callable[[], bool]] = None,
        pausado: Optional[Callable[[], bool]] = None,
        intervalo: int = 250,
    ) -> CrackResult:
        """Testa todas as combinações no intervalo de comprimento."""
        if not charset:
            raise ValueError("Selecione ao menos um conjunto de caracteres.")
        if comprimento_min < 1 or comprimento_max < comprimento_min:
            raise ValueError("Intervalo de comprimento inválido.")

        self.tentativas = 0
        self._inicio = time.perf_counter()
        for tamanho in range(comprimento_min, comprimento_max + 1):
            for combinacao in itertools.product(charset, repeat=tamanho):
                if cancelado and cancelado():
                    return self._resultado(None, cancelado=True)
                while pausado and pausado():
                    if cancelado and cancelado():
                        return self._resultado(None, cancelado=True)
                    time.sleep(0.1)
                senha = "".join(combinacao)
                if self.verificar(senha):
                    return self._resultado(senha)
                if on_progresso and self.tentativas % intervalo == 0:
                    on_progresso(self.tentativas, senha)
        if on_progresso:
            on_progresso(self.tentativas, "")
        return self._resultado(None)

    def benchmark(self, segundos: float = 1.0) -> CrackResult:
        """Mede tentativas por segundo sem alvo real."""
        if self.algoritmo not in ALGORITMOS_HASHLIB and self.algoritmo != "NTLM":
            raise HashNaoSuportado("Benchmark indisponível para este algoritmo com salt.")
        inicio = time.perf_counter()
        tentativas = 0
        while time.perf_counter() - inicio < max(0.2, segundos):
            calcular_hash(f"benchmark-{tentativas}", self.algoritmo)
            tentativas += 1
        decorrido = max(1e-9, time.perf_counter() - inicio)
        return CrackResult(
            found=False,
            algorithm=self.algoritmo,
            attempts=tentativas,
            elapsed=decorrido,
            rate=tentativas / decorrido,
        )


def encontrar_hashcat() -> Optional[str]:
    """Localiza hashcat.exe no PATH."""
    return shutil.which("hashcat") or shutil.which("hashcat.exe")


def comando_hashcat(hash_alvo: str, algoritmo: str, wordlist: Path) -> Optional[List[str]]:
    """Monta a chamada do Hashcat para o algoritmo e wordlist informados."""
    executavel = encontrar_hashcat()
    modo = MODOS_HASHCAT.get(algoritmo)
    if not executavel or modo is None:
        return None
    return [executavel, "-m", str(modo), "-a", "0", hash_alvo, str(wordlist), "--potfile-disable"]


def quebrar_com_hashcat(
    hash_alvo: str,
    algoritmo: str,
    wordlist: Path,
    timeout: int = 3600,
) -> CrackResult:
    """Executa o Hashcat em modo wordlist e interpreta a saída de status."""
    comando = comando_hashcat(hash_alvo, algoritmo, wordlist)
    if comando is None:
        raise HashNaoSuportado("Hashcat não encontrado ou algoritmo sem modo compatível.")
    inicio = time.perf_counter()
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    processo = subprocess.run(
        comando,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=flags,
    )
    decorrido = time.perf_counter() - inicio
    saida = (processo.stdout or "") + "\n" + (processo.stderr or "")
    senha = None
    for linha in saida.splitlines():
        if ":" in linha and hash_alvo.lower() in linha.lower():
            partes = linha.split(":")
            if len(partes) >= 2 and partes[-1].strip():
                senha = ":".join(partes[1:]).strip()
                break
    return CrackResult(
        found=senha is not None,
        password=senha,
        algorithm=algoritmo,
        attempts=0,
        elapsed=decorrido,
        rate=0.0,
    )
