"""
Lógica pura da ferramenta Gerenciador de Compactação e Extração (ZIP, TAR, TAR.GZ).
Compacta, inspeciona e extrai arquivos sem acoplamento com interface gráfica.
"""
import os
from pathlib import Path
import tarfile
from typing import Callable, Dict, List, Optional
import zipfile


def compress_items(
    source_paths: List[Path],
    output_archive: Path,
    fmt: str = "ZIP",
    progress_cb: Optional[Callable[[int], None]] = None,
) -> None:
    """Compacta múltiplos arquivos e pastas em arquivo ZIP ou TAR."""
    fmt = fmt.upper()
    total_files = []
    for p in source_paths:
        if p.is_file():
            total_files.append((p, p.name))
        elif p.is_dir():
            for root, _, files in os.walk(p):
                for f in files:
                    full = Path(root) / f
                    rel = full.relative_to(p.parent)
                    total_files.append((full, str(rel)))

    total_count = len(total_files)

    if fmt == "ZIP":
        with zipfile.ZipFile(output_archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, (fpath, arcname) in enumerate(total_files):
                zf.write(fpath, arcname)
                if progress_cb and total_count > 0:
                    progress_cb(int(((idx + 1) / total_count) * 100))
    elif fmt == "TAR.GZ":
        with tarfile.open(output_archive, "w:gz") as tf:
            for idx, (fpath, arcname) in enumerate(total_files):
                tf.add(fpath, arcname=arcname)
                if progress_cb and total_count > 0:
                    progress_cb(int(((idx + 1) / total_count) * 100))
    elif fmt == "TAR":
        with tarfile.open(output_archive, "w") as tf:
            for idx, (fpath, arcname) in enumerate(total_files):
                tf.add(fpath, arcname=arcname)
                if progress_cb and total_count > 0:
                    progress_cb(int(((idx + 1) / total_count) * 100))


def extract_archive(
    archive_path: Path,
    output_dir: Path,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> int:
    """Extrai conteúdo de arquivo ZIP ou TAR com acompanhamento de progresso."""
    ext = archive_path.name.lower()
    count = 0

    if ext.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            infolist = zf.infolist()
            total = len(infolist)
            for idx, info in enumerate(infolist):
                zf.extract(info, output_dir)
                count += 1
                if progress_cb and total > 0:
                    progress_cb(int(((idx + 1) / total) * 100))
    elif ext.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
        with tarfile.open(archive_path, "r:*") as tf:
            members = tf.getmembers()
            total = len(members)
            for idx, member in enumerate(members):
                try:
                    tf.extract(member, output_dir, filter="data")
                except TypeError:
                    tf.extract(member, output_dir)
                count += 1
                if progress_cb and total > 0:
                    progress_cb(int(((idx + 1) / total) * 100))
    return count


def inspect_archive(archive_path: Path) -> List[Dict]:
    """Lista os arquivos contidos no arquivo compactado sem extrair."""
    items = []
    ext = archive_path.name.lower()

    if ext.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                items.append({
                    "name": info.filename,
                    "size": info.file_size,
                    "compressed": info.compress_size,
                    "is_dir": info.is_dir(),
                })
    elif ext.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
        with tarfile.open(archive_path, "r:*") as tf:
            for m in tf.getmembers():
                items.append({
                    "name": m.name,
                    "size": m.size,
                    "compressed": m.size,
                    "is_dir": m.isdir(),
                })
    return items


def format_archive_size(size_bytes: int) -> str:
    """Formata bytes em string legível."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    return f"{round(size_bytes / (1024 * 1024), 2)} MB"
