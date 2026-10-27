"""
Lógica pura para comparação e diagnóstico diferencial de árvores de diretórios (Folder Diff).
Identifica arquivos idênticos, modificados e exclusivos em cada diretório com suporte a hash SHA-256 opcional.

Zero dependências de interface gráfica.
"""
from datetime import datetime
import fnmatch
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def _compute_quick_hash(file_path: Path) -> str:
    """Calcula SHA-256 em blocos para validação precisa de arquivos."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _format_size(size_bytes: Optional[int]) -> str:
    if size_bytes is None:
        return "-"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _format_mtime(timestamp: Optional[float]) -> str:
    if timestamp is None:
        return "-"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def scan_directory_tree(
    root_dir: Path,
    ignore_patterns: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Varre recursivamente um diretório e mapeia os caminhos relativos normalizados com seus metadados.
    """
    root = Path(root_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"O caminho informado não é um diretório: {root}")

    tree: Dict[str, Dict[str, Any]] = {}
    patterns = ignore_patterns or [".git*", "*.tmp", "desktop.ini", "Thumbs.db"]

    for item in root.rglob("*"):
        if item.is_file():
            rel_path = str(item.relative_to(root)).replace("\\", "/")

            # Verifica se deve ignorar
            if any(fnmatch.fnmatch(item.name, p) or fnmatch.fnmatch(rel_path, p) for p in patterns):
                continue

            stat = item.stat()
            tree[rel_path] = {
                "full_path": item,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            }

    return tree


def compare_directories(
    dir_a: Path,
    dir_b: Path,
    deep_hash_compare: bool = False,
    ignore_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Compara detalhadamente dois diretórios e categoriza cada arquivo.
    """
    path_a = Path(dir_a)
    path_b = Path(dir_b)

    tree_a = scan_directory_tree(path_a, ignore_patterns=ignore_patterns)
    tree_b = scan_directory_tree(path_b, ignore_patterns=ignore_patterns)

    all_rel_paths: Set[str] = set(tree_a.keys()) | set(tree_b.keys())
    results: List[Dict[str, Any]] = []

    count_identical = 0
    count_modified = 0
    count_only_a = 0
    count_only_b = 0

    for rel_path in sorted(all_rel_paths):
        in_a = rel_path in tree_a
        in_b = rel_path in tree_b

        if in_a and not in_b:
            meta_a = tree_a[rel_path]
            results.append({
                "status": "APENAS_EM_A",
                "rel_path": rel_path,
                "size_a": _format_size(meta_a["size"]),
                "size_b": "-",
                "raw_size_a": meta_a["size"],
                "raw_size_b": 0,
                "mtime_a": _format_mtime(meta_a["mtime"]),
                "mtime_b": "-",
                "details": "Presente apenas na pasta Origem (A)",
            })
            count_only_a += 1

        elif in_b and not in_a:
            meta_b = tree_b[rel_path]
            results.append({
                "status": "APENAS_EM_B",
                "rel_path": rel_path,
                "size_a": "-",
                "size_b": _format_size(meta_b["size"]),
                "raw_size_a": 0,
                "raw_size_b": meta_b["size"],
                "mtime_a": "-",
                "mtime_b": _format_mtime(meta_b["mtime"]),
                "details": "Presente apenas na pasta Destino (B)",
            })
            count_only_b += 1

        else:
            meta_a = tree_a[rel_path]
            meta_b = tree_b[rel_path]

            is_modified = False
            details = "Arquivos idênticos"

            if meta_a["size"] != meta_b["size"]:
                is_modified = True
                details = f"Tamanhos diferentes ({meta_a['size']} B vs {meta_b['size']} B)"
            elif deep_hash_compare:
                hash_a = _compute_quick_hash(meta_a["full_path"])
                hash_b = _compute_quick_hash(meta_b["full_path"])
                if hash_a != hash_b:
                    is_modified = True
                    details = "Hashes SHA-256 diferentes (conteúdo divergente)"
            else:
                # Se os tamanhos são iguais mas timestamps diferem
                if abs(meta_a["mtime"] - meta_b["mtime"]) > 2.0:
                    details = "Mesmo tamanho, datas de modificação diferentes"

            status = "MODIFICADO" if is_modified else "IDENTICO"
            if is_modified:
                count_modified += 1
            else:
                count_identical += 1

            results.append({
                "status": status,
                "rel_path": rel_path,
                "size_a": _format_size(meta_a["size"]),
                "size_b": _format_size(meta_b["size"]),
                "raw_size_a": meta_a["size"],
                "raw_size_b": meta_b["size"],
                "mtime_a": _format_mtime(meta_a["mtime"]),
                "mtime_b": _format_mtime(meta_b["mtime"]),
                "details": details,
            })

    total_files = len(all_rel_paths)
    similarity_pct = (count_identical / total_files * 100.0) if total_files > 0 else 100.0

    return {
        "summary": {
            "total_files": total_files,
            "identical": count_identical,
            "modified": count_modified,
            "only_a": count_only_a,
            "only_b": count_only_b,
            "similarity_pct": similarity_pct,
        },
        "records": results,
    }
