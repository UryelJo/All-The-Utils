"""
Lógica pura da ferramenta Localizador e Removedor de Arquivos Duplicados.
Varredura em 3 estágios (tamanho, hash rápido e SHA-256) e envio para a lixeira.
"""
from collections import defaultdict
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Callable, List, Optional


@dataclass
class DuplicateItem:
    path: Path
    group_id: int
    size: int
    mtime: float
    selected: bool = False


def get_file_quick_hash(file_path: Path) -> str:
    """Calcula hash dos primeiros 4KB do arquivo para descarte rápido."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(4096)
            return hashlib.md5(chunk).hexdigest()
    except Exception:
        return ""


def get_file_full_hash(file_path: Path) -> str:
    """Calcula o hash SHA-256 completo do arquivo."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


def scan_duplicates(
    folder: Path,
    recursive: bool = True,
    progress_cb: Optional[Callable[[int, str], None]] = None,
) -> List[List[Path]]:
    """Localiza grupos de arquivos duplicados através de tamanho, hash rápido e SHA-256."""
    by_size = defaultdict(list)
    root_path = Path(folder)
    it = root_path.rglob("*") if recursive else root_path.glob("*")

    all_files = [p for p in it if p.is_file()]
    total_f = len(all_files)

    for idx, f in enumerate(all_files):
        try:
            s = f.stat().st_size
            if s > 0:
                by_size[s].append(f)
        except Exception:
            pass
        if progress_cb and idx % 50 == 0:
            progress_cb(int((idx / max(total_f, 1)) * 30), "Agrupando por tamanho...")

    candidates = []
    for sz, files in by_size.items():
        if len(files) > 1:
            candidates.extend(files)

    by_quick = defaultdict(list)
    for idx, f in enumerate(candidates):
        qh = get_file_quick_hash(f)
        if qh:
            by_quick[(f.stat().st_size, qh)].append(f)
        if progress_cb and idx % 20 == 0:
            progress_cb(30 + int((idx / max(len(candidates), 1)) * 30), "Verificando hashes rápidos...")

    final_groups = defaultdict(list)
    group_candidates = [flist for flist in by_quick.values() if len(flist) > 1]
    total_cand = sum(len(fl) for fl in group_candidates)
    done_cand = 0

    for flist in group_candidates:
        for f in flist:
            fh = get_file_full_hash(f)
            if fh:
                final_groups[(f.stat().st_size, fh)].append(f)
            done_cand += 1
            if progress_cb:
                progress_cb(60 + int((done_cand / max(total_cand, 1)) * 40), "Calculando SHA-256...")

    return [flist for flist in final_groups.values() if len(flist) > 1]


def format_size(size_bytes: int) -> str:
    """Formata bytes em string humanamente legível (B, KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{round(size_bytes / (1024 * 1024), 2)} MB"
    return f"{round(size_bytes / (1024 * 1024 * 1024), 2)} GB"


def trash_files(paths: List[Path]) -> int:
    """Move uma lista de arquivos para a Lixeira do Windows utilizando send2trash."""
    import send2trash
    deleted = 0
    for p in paths:
        if p.exists():
            send2trash.send2trash(str(p))
            deleted += 1
    return deleted
