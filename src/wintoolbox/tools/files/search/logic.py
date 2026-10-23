"""
Lógica pura da ferramenta de Pesquisa Avançada de Arquivos e Conteúdo.
Suporta filtros por nome (glob/regex), tamanho, data e conteúdo de texto interno.
"""
from dataclasses import dataclass
from datetime import datetime
import fnmatch
import os
from pathlib import Path
import re
from typing import Callable, List, Optional

TEXT_EXTENSIONS = {
    ".txt", ".log", ".py", ".js", ".ts", ".html", ".css", ".json", ".xml",
    ".yaml", ".yml", ".md", ".csv", ".ini", ".cfg", ".sql", ".sh", ".bat",
    ".ps1", ".cpp", ".c", ".h", ".cs", ".java", ".php", ".env", ".toml"
}


@dataclass
class SearchResultItem:
    path: Path
    name: str
    size_bytes: int
    mtime: float
    matched_snippet: Optional[str] = None

    @property
    def formatted_size(self) -> str:
        sz = self.size_bytes
        if sz < 1024:
            return f"{sz} B"
        elif sz < 1024 * 1024:
            return f"{sz / 1024:.1f} KB"
        elif sz < 1024 * 1024 * 1024:
            return f"{sz / (1024 * 1024):.1f} MB"
        return f"{sz / (1024 * 1024 * 1024):.2f} GB"

    @property
    def formatted_mtime(self) -> str:
        return datetime.fromtimestamp(self.mtime).strftime("%d/%m/%Y %H:%M:%S")


def search_file_content(
    file_path: Path,
    query: str,
    case_sensitive: bool = False,
    is_regex: bool = False,
    max_scan_bytes: int = 10 * 1024 * 1024,
) -> Optional[str]:
    """
    Busca por string ou regex dentro de arquivos de texto de forma segura e em streaming.
    Retorna o primeiro snippet encontrado com contexto de linha.
    """
    try:
        if file_path.stat().st_size > max_scan_bytes:
            return None

        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(query if is_regex else re.escape(query), flags)

        # Tenta decodificação UTF-8 ou fallback para latin-1
        for encoding in ("utf-8", "latin-1"):
            try:
                with open(file_path, "r", encoding=encoding, errors="replace") as f:
                    for line_no, line in enumerate(f, start=1):
                        m = pattern.search(line)
                        if m:
                            snippet = line.strip()
                            if len(snippet) > 80:
                                snippet = snippet[:77] + "..."
                            return f"Linha {line_no}: {snippet}"
                break
            except UnicodeDecodeError:
                continue
    except Exception:
        pass
    return None


def search_files(
    root_dir: Path,
    name_pattern: str = "*",
    min_size_bytes: Optional[int] = None,
    max_size_bytes: Optional[int] = None,
    min_mtime: Optional[float] = None,
    max_mtime: Optional[float] = None,
    content_query: str = "",
    case_sensitive: bool = False,
    is_regex: bool = False,
    max_results: int = 500,
    is_cancelled_fn: Optional[Callable[[], bool]] = None,
    progress_cb: Optional[Callable[[int, str], None]] = None,
) -> List[SearchResultItem]:
    """
    Executa a varredura e filtragem combinada de arquivos no sistema de arquivos.
    """
    root_dir = Path(root_dir).resolve()
    if not root_dir.is_dir():
        return []

    results: List[SearchResultItem] = []
    scanned_count = 0

    # Compila regex de nome se aplicável
    name_re = None
    if is_regex and name_pattern:
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            name_re = re.compile(name_pattern, flags)
        except re.error:
            pass

    norm_pattern = name_pattern.lower() if not case_sensitive else name_pattern

    for root, _, files in os.walk(root_dir):
        if is_cancelled_fn and is_cancelled_fn():
            break

        for fname in files:
            if is_cancelled_fn and is_cancelled_fn():
                break

            scanned_count += 1
            if progress_cb and scanned_count % 100 == 0:
                progress_cb(len(results), f"Examinados: {scanned_count} arquivos...")

            # 1. Filtro por Nome
            if name_re:
                if not name_re.search(fname):
                    continue
            elif name_pattern and name_pattern != "*":
                target_name = fname if case_sensitive else fname.lower()
                if not fnmatch.fnmatch(target_name, norm_pattern):
                    continue

            fp = Path(root) / fname

            # 2. Filtro por Tamanho e Data
            try:
                st = fp.stat()
                sz = st.st_size
                mtime = st.st_mtime

                if min_size_bytes is not None and sz < min_size_bytes:
                    continue
                if max_size_bytes is not None and sz > max_size_bytes:
                    continue
                if min_mtime is not None and mtime < min_mtime:
                    continue
                if max_mtime is not None and mtime > max_mtime:
                    continue
            except Exception:
                continue

            # 3. Filtro por Conteúdo Interno de Texto
            snippet = None
            if content_query.strip():
                ext = fp.suffix.lower()
                if ext not in TEXT_EXTENSIONS and sz > 1024 * 1024:
                    continue
                snippet = search_file_content(fp, content_query.strip(), case_sensitive=case_sensitive)
                if snippet is None:
                    continue

            results.append(
                SearchResultItem(
                    path=fp,
                    name=fname,
                    size_bytes=sz,
                    mtime=mtime,
                    matched_snippet=snippet,
                )
            )

            if len(results) >= max_results:
                return results

    return results
