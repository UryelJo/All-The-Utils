"""
Lógica pura para contagem e análise de linhas de código-fonte (estilo CLOC).
Discrimina código efetivo, comentários e linhas em branco, com detecção de TODOs e FIXMEs.
Isolada de qualquer dependência com frameworks de interface gráfica.
"""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Configurações de sintaxe de comentários por linguagem
LANGUAGE_CONFIGS = {
    "Python": {
        "extensions": [".py", ".pyw"],
        "single_comments": ["#"],
        "multi_open": '"""',
        "multi_close": '"""',
        "multi_alt_open": "'''",
        "multi_alt_close": "'''",
    },
    "JavaScript / TypeScript": {
        "extensions": [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"],
        "single_comments": ["//"],
        "multi_open": "/*",
        "multi_close": "*/",
    },
    "C / C++": {
        "extensions": [".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx"],
        "single_comments": ["//"],
        "multi_open": "/*",
        "multi_close": "*/",
    },
    "C# (.NET)": {
        "extensions": [".cs"],
        "single_comments": ["//"],
        "multi_open": "/*",
        "multi_close": "*/",
    },
    "Java / Kotlin": {
        "extensions": [".java", ".kt", ".kts"],
        "single_comments": ["//"],
        "multi_open": "/*",
        "multi_close": "*/",
    },
    "Rust": {
        "extensions": [".rs"],
        "single_comments": ["//"],
        "multi_open": "/*",
        "multi_close": "*/",
    },
    "Go": {
        "extensions": [".go"],
        "single_comments": ["//"],
        "multi_open": "/*",
        "multi_close": "*/",
    },
    "HTML / XML": {
        "extensions": [".html", ".htm", ".xml", ".svg", ".vue"],
        "single_comments": [],
        "multi_open": "<!--",
        "multi_close": "-->",
    },
    "CSS / SCSS": {
        "extensions": [".css", ".scss", ".sass", ".less"],
        "single_comments": ["//"],
        "multi_open": "/*",
        "multi_close": "*/",
    },
    "SQL": {
        "extensions": [".sql"],
        "single_comments": ["--"],
        "multi_open": "/*",
        "multi_close": "*/",
    },
    "Shell / Bash / PowerShell": {
        "extensions": [".sh", ".bash", ".ps1", ".psm1"],
        "single_comments": ["#"],
        "multi_open": "<#",
        "multi_close": "#>",
    },
    "YAML / TOML / INI": {
        "extensions": [".yaml", ".yml", ".toml", ".ini", ".env"],
        "single_comments": ["#", ";"],
        "multi_open": "",
        "multi_close": "",
    },
    "JSON / Dados": {
        "extensions": [".json"],
        "single_comments": ["//"],
        "multi_open": "/*",
        "multi_close": "*/",
    },
    "Markdown": {
        "extensions": [".md", ".markdown"],
        "single_comments": [],
        "multi_open": "<!--",
        "multi_close": "-->",
    }
}

DEFAULT_IGNORED_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    ".idea", ".vscode", "target", "bin", "obj", "dist", "build", ".next",
    ".nuxt", ".gradle", ".pytest_cache", ".mypy_cache", ".ruff_cache"
}


@dataclass
class CodeMarker:
    """Representa uma anotação de tarefa (TODO / FIXME)."""
    file_path: Path
    line_number: int
    marker_type: str  # "TODO" ou "FIXME"
    content: str


@dataclass
class FileStats:
    """Estatísticas de um arquivo fonte individual."""
    path: Path
    language: str
    lines_code: int = 0
    lines_comment: int = 0
    lines_blank: int = 0
    total_lines: int = 0
    markers: List[CodeMarker] = field(default_factory=list)


@dataclass
class LanguageStats:
    """Estatísticas agregadas de uma linguagem de programação."""
    language: str
    files_count: int = 0
    lines_code: int = 0
    lines_comment: int = 0
    lines_blank: int = 0
    total_lines: int = 0


def detect_language(ext: str) -> Optional[str]:
    """Retorna o nome da linguagem com base na extensão do arquivo."""
    ext_lower = ext.lower()
    for lang, cfg in LANGUAGE_CONFIGS.items():
        if ext_lower in cfg["extensions"]:
            return lang
    return None


def analyze_file(file_path: Path, language: str) -> FileStats:
    """Analisa o conteúdo de um arquivo de código-fonte linha a linha."""
    cfg = LANGUAGE_CONFIGS[language]
    singles = cfg["single_comments"]
    multi_open = cfg.get("multi_open", "")
    multi_close = cfg.get("multi_close", "")
    multi_alt_open = cfg.get("multi_alt_open", "")
    multi_alt_close = cfg.get("multi_alt_close", "")

    content = ""
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            content = file_path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, OSError):
            continue

    stats = FileStats(path=file_path, language=language)
    lines = content.splitlines()
    stats.total_lines = len(lines)

    in_multi = False
    in_multi_alt = False

    todo_pattern = re.compile(r'\b(TODO|FIXME)\b[:\s]*(.*)', re.IGNORECASE)

    for line_idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()

        # Detecção de tarefas TODO / FIXME
        match = todo_pattern.search(line)
        if match:
            m_type = match.group(1).upper()
            m_text = match.group(2).strip() or line
            stats.markers.append(
                CodeMarker(
                    file_path=file_path,
                    line_number=line_idx,
                    marker_type=m_type,
                    content=m_text
                )
            )

        # 1. Linha em branco
        if not line:
            stats.lines_blank += 1
            continue

        # 2. Continuação de comentário em bloco
        if in_multi:
            stats.lines_comment += 1
            if multi_close and multi_close in line:
                in_multi = False
            continue

        if in_multi_alt:
            stats.lines_comment += 1
            if multi_alt_close and multi_alt_close in line:
                in_multi_alt = False
            continue

        # 3. Início de bloco de comentário
        if multi_open and line.startswith(multi_open):
            stats.lines_comment += 1
            if multi_close and multi_close in line[len(multi_open):]:
                in_multi = False
            else:
                in_multi = True
            continue

        if multi_alt_open and line.startswith(multi_alt_open):
            stats.lines_comment += 1
            if multi_alt_close and multi_alt_close in line[len(multi_alt_open):]:
                in_multi_alt = False
            else:
                in_multi_alt = True
            continue

        # 4. Comentário de linha única
        is_single = False
        for s in singles:
            if line.startswith(s):
                stats.lines_comment += 1
                is_single = True
                break

        if is_single:
            continue

        # 5. Linha de código efetivo
        stats.lines_code += 1

    return stats


def count_project_lines(
    root_dir: Path,
    ignored_dirs: Optional[Set[str]] = None,
    max_files: int = 20000
) -> Tuple[Dict[str, LanguageStats], List[FileStats], List[CodeMarker]]:
    """
    Varre recursivamente uma árvore de diretórios quantificando métricas de linhas de código.
    """
    root_dir = Path(root_dir).resolve()
    if not root_dir.is_dir():
        raise FileNotFoundError(f"Diretório não encontrado: {root_dir}")

    if ignored_dirs is None:
        ignored_dirs = DEFAULT_IGNORED_DIRS

    lang_stats: Dict[str, LanguageStats] = {}
    files_stats: List[FileStats] = []
    all_markers: List[CodeMarker] = []

    file_count = 0

    for root, dirs, files in os.walk(root_dir):
        # Filtra pastas ignoradas in-place para podar a árvore de busca
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]

        for f in files:
            file_count += 1
            if file_count > max_files:
                break

            file_path = Path(root) / f
            lang = detect_language(file_path.suffix)
            if not lang:
                continue

            try:
                f_stat = analyze_file(file_path, lang)
            except Exception:
                continue

            files_stats.append(f_stat)
            all_markers.extend(f_stat.markers)

            if lang not in lang_stats:
                lang_stats[lang] = LanguageStats(language=lang)

            l_stat = lang_stats[lang]
            l_stat.files_count += 1
            l_stat.lines_code += f_stat.lines_code
            l_stat.lines_comment += f_stat.lines_comment
            l_stat.lines_blank += f_stat.lines_blank
            l_stat.total_lines += f_stat.total_lines

    return lang_stats, files_stats, all_markers
