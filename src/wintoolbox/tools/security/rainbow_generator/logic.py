"""Geração e consulta de rainbow tables em SQLite.

A tabela armazena apenas hash e plaintext, com índice primário na coluna hash.
A gravação é feita em transações periódicas para permitir cancelamento com
preservação do trabalho já concluído.
"""
from __future__ import annotations

import hashlib
import itertools
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple

from wintoolbox.tools._helpers import formatar_bytes, formatar_numero
from wintoolbox.tools.security.hash_cracker.logic import ALGORITMOS_HASHLIB

ESQUEMA = """
CREATE TABLE IF NOT EXISTS hashes (
    hash TEXT PRIMARY KEY,
    plain TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hash ON hashes(hash);
CREATE TABLE IF NOT EXISTS metadados (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""


@dataclass
class RainbowProgress:
    """Estado de uma geração de rainbow table."""

    gerados: int
    total: int
    caminho: Path
    cancelado: bool = False
    segundos: float = 0.0

    def resumo(self) -> str:
        if self.cancelado:
            return f"Geração cancelada; {formatar_numero(self.gerados)} entradas preservadas."
        return (
            f"{formatar_numero(self.gerados)} entrada(s) geradas em {self.segundos:.1f}s "
            f"({formatar_bytes(self.caminho.stat().st_size if self.caminho.exists() else 0)})."
        )


def estimar_combinacoes(charset: str, comprimento_min: int, comprimento_max: int) -> int:
    """Calcula o número total de combinações do intervalo."""
    if not charset:
        return 0
    if comprimento_min < 1 or comprimento_max < comprimento_min:
        return 0
    return sum(len(charset) ** n for n in range(comprimento_min, comprimento_max + 1))


def estimar_tamanho_bytes(combinacoes: int, algoritmo: str = "MD5") -> int:
    """Estima o tamanho do banco a partir do custo médio por linha."""
    tamanho_hash = {"MD5": 32, "SHA-1": 40, "SHA-256": 64}.get(algoritmo, 64)
    # hash + plaintext (média de 8 bytes) + overhead de página/índice do SQLite.
    por_linha = tamanho_hash + 8 + 48
    return int(combinacoes * por_linha * 1.25)


def criar_banco(caminho: Path) -> sqlite3.Connection:
    """Cria/abre o banco e aplica o esquema idempotente."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(str(caminho), timeout=30.0)
    conexao.executescript(ESQUEMA)
    conexao.commit()
    return conexao


def _gravar_metadados(conexao: sqlite3.Connection, algoritmo: str, charset: str, minimo: int, maximo: int) -> None:
    dados = {
        "algoritmo": algoritmo,
        "charset": charset,
        "comprimento_min": str(minimo),
        "comprimento_max": str(maximo),
        "criado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    conexao.executemany(
        "INSERT OR REPLACE INTO metadados (chave, valor) VALUES (?, ?)",
        list(dados.items()),
    )


def gerar_rainbow(
    caminho: Path,
    algoritmo: str,
    charset: str,
    comprimento_min: int,
    comprimento_max: int,
    on_progresso: Optional[Callable[[int, int], None]] = None,
    cancelado: Optional[Callable[[], bool]] = None,
    lote: int = 2000,
) -> RainbowProgress:
    """Gera a tabela de forma incremental e transacional."""
    if algoritmo not in ALGORITMOS_HASHLIB:
        raise ValueError(f"Algoritmo não suportado: {algoritmo}")
    if not charset:
        raise ValueError("Informe o charset.")
    if comprimento_min < 1 or comprimento_max < comprimento_min:
        raise ValueError("Intervalo de comprimento inválido.")

    total = estimar_combinacoes(charset, comprimento_min, comprimento_max)
    inicio = time.perf_counter()
    gerados = 0
    cancelado_flag = False
    conexao = criar_banco(Path(caminho))
    try:
        _gravar_metadados(conexao, algoritmo, charset, comprimento_min, comprimento_max)
        conexao.commit()
        pendentes: List[Tuple[str, str]] = []
        for tamanho in range(comprimento_min, comprimento_max + 1):
            for combinacao in itertools.product(charset, repeat=tamanho):
                if cancelado and cancelado():
                    cancelado_flag = True
                    break
                plain = "".join(combinacao)
                digest = hashlib.new(ALGORITHMS_LOOKUP[algoritmo], plain.encode("utf-8")).hexdigest()
                pendentes.append((digest, plain))
                gerados += 1
                if len(pendentes) >= lote:
                    conexao.executemany("INSERT OR IGNORE INTO hashes (hash, plain) VALUES (?, ?)", pendentes)
                    conexao.commit()
                    pendentes.clear()
                    if on_progresso:
                        on_progresso(gerados, total)
            if cancelado_flag:
                break
        if pendentes:
            conexao.executemany("INSERT OR IGNORE INTO hashes (hash, plain) VALUES (?, ?)", pendentes)
        conexao.commit()
    finally:
        conexao.close()

    if on_progresso:
        on_progresso(gerados, total)
    return RainbowProgress(
        gerados=gerados,
        total=total,
        caminho=Path(caminho),
        cancelado=cancelado_flag,
        segundos=time.perf_counter() - inicio,
    )


ALGORITHMS_LOOKUP: Dict[str, str] = dict(ALGORITMOS_HASHLIB)


def consultar_hash(caminho: Path, hash_alvo: str) -> Optional[str]:
    """Consulta um hash usando o índice primário (tempo constante)."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"Banco não encontrado: {caminho}")
    alvo = str(hash_alvo or "").strip().lower()
    if not alvo:
        return None
    conexao = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True, timeout=10.0)
    try:
        linha = conexao.execute("SELECT plain FROM hashes WHERE hash = ? LIMIT 1", (alvo,)).fetchone()
        return linha[0] if linha else None
    finally:
        conexao.close()


def metadados_tabela(caminho: Path) -> Dict[str, str]:
    """Lê os metadados gravados na tabela, quando existirem."""
    caminho = Path(caminho)
    if not caminho.is_file():
        return {}
    conexao = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True, timeout=10.0)
    try:
        try:
            linhas = conexao.execute("SELECT chave, valor FROM metadados").fetchall()
        except sqlite3.DatabaseError:
            return {}
        return {str(chave): str(valor) for chave, valor in linhas}
    finally:
        conexao.close()
