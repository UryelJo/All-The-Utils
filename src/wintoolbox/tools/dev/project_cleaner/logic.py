"""
Lógica pura para localização e limpeza em lote de pastas pesadas de compilação e dependências de código.
Suporta ecossistemas Node.js, Python, Rust, .NET, Java/Gradle e C++.
Isolada de qualquer dependência com bibliotecas de interface gráfica.
"""
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

# Mapeamento de nomes de diretórios/padrões para tipos de projeto
DEFAULT_TARGET_CATEGORIES: Dict[str, Dict[str, str]] = {
    "node": {
        "node_modules": "Dependências Node.js / NPM",
        ".next": "Cache de Build Next.js",
        ".nuxt": "Cache de Build Nuxt",
        ".turbo": "Cache do Turborepo",
        ".parcel-cache": "Cache do Parcel",
    },
    "python": {
        "__pycache__": "Bytecode Python (__pycache__)",
        ".pytest_cache": "Cache do Pytest",
        ".mypy_cache": "Cache de Tipagem Mypy",
        ".ruff_cache": "Cache do Linter Ruff",
        ".venv": "Ambiente Virtual (.venv)",
        "venv": "Ambiente Virtual (venv)",
        ".tox": "Ambiente de Testes Tox",
    },
    "rust": {
        "target": "Compilação Rust Cargo (target)",
    },
    "dotnet": {
        "bin": "Binários .NET (bin)",
        "obj": "Objetos Intermediários .NET (obj)",
    },
    "java": {
        ".gradle": "Cache do Gradle (.gradle)",
    },
    "coverage": {
        "coverage": "Relatórios de Cobertura de Código",
        ".coverage": "Dados de Cobertura SQLite",
        "htmlcov": "Relatório HTML de Cobertura",
    }
}


@dataclass
class CleanableItem:
    """Representa uma pasta ou arquivo de compilação elegível para limpeza."""
    path: Path
    category: str
    description: str
    size_bytes: int
    file_count: int


def _remove_readonly(func: Callable, path: str, excinfo: Tuple) -> None:
    """Callback de erro para shutil.rmtree para remover atributos de somente leitura no Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def get_dir_size_and_count(dir_path: Path) -> Tuple[int, int]:
    """Calcula recursivamente o tamanho total em bytes e a quantidade de arquivos de uma pasta."""
    total_size = 0
    file_count = 0
    try:
        for entry in os.scandir(dir_path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total_size += entry.stat(follow_symlinks=False).st_size
                    file_count += 1
                elif entry.is_dir(follow_symlinks=False):
                    sub_size, sub_count = get_dir_size_and_count(Path(entry.path))
                    total_size += sub_size
                    file_count += sub_count
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        pass
    return total_size, file_count


def scan_cleanable_items(
    root_dir: Path,
    enabled_categories: Optional[Set[str]] = None,
    max_depth: int = 5,
    progress_callback: Optional[Callable[[str], None]] = None
) -> List[CleanableItem]:
    """
    Varre um diretório raiz em busca de pastas de compilação e dependências descartáveis.
    """
    root_dir = Path(root_dir).resolve()
    if not root_dir.is_dir():
        raise FileNotFoundError(f"Diretório não encontrado: {root_dir}")

    if enabled_categories is None:
        enabled_categories = set(DEFAULT_TARGET_CATEGORIES.keys())

    # Constrói dicionário de busca rápido: nome_da_pasta -> (categoria, descricao)
    lookup: Dict[str, Tuple[str, str]] = {}
    for cat, items in DEFAULT_TARGET_CATEGORIES.items():
        if cat in enabled_categories:
            for folder_name, desc in items.items():
                lookup[folder_name.lower()] = (cat, desc)

    results: List[CleanableItem] = []

    def _walk(current_path: Path, current_depth: int):
        if current_depth > max_depth:
            return

        if progress_callback:
            progress_callback(str(current_path))

        try:
            entries = list(os.scandir(current_path))
        except (OSError, PermissionError):
            return

        for entry in entries:
            name_lower = entry.name.lower()
            if entry.is_dir(follow_symlinks=False):
                entry_path = Path(entry.path)
                # Verifica se a pasta é um alvo de limpeza
                if name_lower in lookup:
                    cat, desc = lookup[name_lower]
                    sz, count = get_dir_size_and_count(entry_path)
                    results.append(
                        CleanableItem(
                            path=entry_path,
                            category=cat,
                            description=desc,
                            size_bytes=sz,
                            file_count=count
                        )
                    )
                    # Não desce mais na pasta que já será excluída por completo
                    continue

                # Evita descer em diretórios ocultos do git
                if name_lower == ".git":
                    continue

                _walk(entry_path, current_depth + 1)

    _walk(root_dir, 1)
    results.sort(key=lambda x: x.size_bytes, reverse=True)
    return results


def delete_cleanable_items(
    items: List[Path],
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Exclui os itens informados e retorna (quantidade_deletada, bytes_liberados).
    """
    deleted_count = 0
    bytes_freed = 0

    for path in items:
        path = Path(path).resolve()
        if not path.exists():
            continue

        if path.is_dir():
            sz, _ = get_dir_size_and_count(path)
            if not dry_run:
                shutil.rmtree(path, onerror=_remove_readonly)
            deleted_count += 1
            bytes_freed += sz
        elif path.is_file():
            sz = path.stat().st_size
            if not dry_run:
                try:
                    os.chmod(path, stat.S_IWRITE)
                    path.unlink()
                except Exception:
                    continue
            deleted_count += 1
            bytes_freed += sz

    return deleted_count, bytes_freed
