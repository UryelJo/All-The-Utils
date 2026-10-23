"""
Lógica pura da ferramenta Analisador de Espaço em Disco.
Mapeamento de subpastas, arquivos pesados e tipos de extensões sem dependência de UI.
"""
from collections import defaultdict
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class DiskItem:
    name: str
    path: str
    size: int
    is_dir: bool
    count: int = 1


def format_disk_size(size_bytes: int) -> str:
    """Formata bytes em string humanamente legível."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{round(size_bytes / (1024 * 1024), 2)} MB"
    return f"{round(size_bytes / (1024 * 1024 * 1024), 2)} GB"


def calc_dir_size(dir_path: str) -> Tuple[int, int, Dict[str, int], Dict[str, int]]:
    """Calcula recursivamente o tamanho, quantidade de arquivos e extensões de um diretório."""
    total_size = 0
    total_count = 0
    ext_sizes = defaultdict(int)
    ext_counts = defaultdict(int)

    for root, _, files in os.walk(dir_path):
        for f in files:
            try:
                fp = os.path.join(root, f)
                s = os.path.getsize(fp)
                total_size += s
                total_count += 1
                ext = Path(f).suffix.lower() or "(sem extensão)"
                ext_sizes[ext] += s
                ext_counts[ext] += 1
            except Exception:
                pass

    return total_size, total_count, ext_sizes, ext_counts


def analyze_directory_usage(
    target: Path,
) -> Tuple[List[DiskItem], List[Tuple[str, int]], Dict[str, int], int]:
    """
    Analisa os itens de primeiro nível de um diretório alvo e consolida o consumo por extensões.
    Retorna (top_level_items, sorted_exts, ext_counts, total_dir_bytes).
    """
    top_level_items: List[DiskItem] = []
    ext_sizes = defaultdict(int)
    ext_counts = defaultdict(int)
    total_dir_bytes = 0

    for entry in os.scandir(target):
        try:
            if entry.is_file(follow_symlinks=False):
                s = entry.stat().st_size
                top_level_items.append(DiskItem(entry.name, entry.path, s, False))
                total_dir_bytes += s
                ext = Path(entry.name).suffix.lower() or "(sem extensão)"
                ext_sizes[ext] += s
                ext_counts[ext] += 1
            elif entry.is_dir(follow_symlinks=False):
                dir_size, dir_count, sub_exts, sub_counts = calc_dir_size(entry.path)
                top_level_items.append(DiskItem(entry.name, entry.path, dir_size, True, dir_count))
                total_dir_bytes += dir_size
                for k, v in sub_exts.items():
                    ext_sizes[k] += v
                for k, v in sub_counts.items():
                    ext_counts[k] += v
        except Exception:
            pass

    top_level_items.sort(key=lambda x: x.size, reverse=True)
    sorted_exts = sorted(ext_sizes.items(), key=lambda x: x[1], reverse=True)

    return top_level_items, sorted_exts, ext_counts, total_dir_bytes
