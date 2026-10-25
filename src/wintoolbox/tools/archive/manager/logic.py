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


def _find_system_extractor() -> Optional[str]:
    """Localiza binário 7z.exe ou unrar.exe instalado no Windows."""
    import shutil
    for name in ["7z.exe", "7z", "unrar.exe", "unrar"]:
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        r"C:\Program Files\WinRAR\UnRAR.exe",
        r"C:\Program Files\WinRAR\WinRAR.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def extract_archive(
    archive_path: Path,
    output_dir: Path,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> int:
    """Extrai conteúdo de arquivo ZIP, TAR, 7Z ou RAR com acompanhamento de progresso."""
    import subprocess
    ext = archive_path.name.lower()
    count = 0
    output_dir.mkdir(parents=True, exist_ok=True)

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
    elif ext.endswith(".7z"):
        try:
            import py7zr
            with py7zr.SevenZipFile(archive_path, mode="r") as z:
                files = z.getnames()
                count = len(files)
                z.extractall(path=output_dir)
                if progress_cb:
                    progress_cb(100)
                return count
        except ImportError:
            pass

        # Fallback para 7z ou tar.exe nativo do Windows
        before_files = {p for p in output_dir.rglob("*") if p.is_file()}
        cli = _find_system_extractor()
        flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
        if cli and "7z" in cli.lower():
            subprocess.run(
                [cli, "x", str(archive_path), f"-o{output_dir}", "-y"],
                check=True,
                capture_output=True,
                creationflags=flags
            )
        else:
            # bsdtar nativo do Windows suporta 7z
            subprocess.run(
                ["tar", "-xf", str(archive_path), "-C", str(output_dir)],
                check=True,
                capture_output=True,
                creationflags=flags
            )
        after_files = {p for p in output_dir.rglob("*") if p.is_file()}
        count = len(after_files - before_files)
        if progress_cb:
            progress_cb(100)
    elif ext.endswith(".rar"):
        before_files = {p for p in output_dir.rglob("*") if p.is_file()}
        cli = _find_system_extractor()
        flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
        if cli and "7z" in cli.lower():
            subprocess.run(
                [cli, "x", str(archive_path), f"-o{output_dir}", "-y"],
                check=True,
                capture_output=True,
                creationflags=flags
            )
        elif cli and "unrar" in cli.lower():
            subprocess.run(
                [cli, "x", "-y", str(archive_path), str(output_dir) + os.sep],
                check=True,
                capture_output=True,
                creationflags=flags
            )
        else:
            # Tenta via tar.exe nativo do Windows
            subprocess.run(
                ["tar", "-xf", str(archive_path), "-C", str(output_dir)],
                check=True,
                capture_output=True,
                creationflags=flags
            )
        after_files = {p for p in output_dir.rglob("*") if p.is_file()}
        count = len(after_files - before_files)
        if progress_cb:
            progress_cb(100)

    return count


def inspect_archive(archive_path: Path) -> List[Dict]:
    """Lista os arquivos contidos no arquivo compactado sem extrair."""
    import subprocess
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
    elif ext.endswith(".7z"):
        try:
            import py7zr
            with py7zr.SevenZipFile(archive_path, mode="r") as z:
                for info in z.list():
                    items.append({
                        "name": info.filename,
                        "size": getattr(info, "uncompressed", 0),
                        "compressed": getattr(info, "compressed", 0),
                        "is_dir": getattr(info, "is_directory", False),
                    })
                return items
        except ImportError:
            pass

        # Fallback via tar.exe -tf
        flags = 0x08000000 if os.name == "nt" else 0
        res = subprocess.run(
            ["tar", "-tf", str(archive_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags
        )
        for line in res.stdout.splitlines():
            name = line.strip()
            if name:
                items.append({
                    "name": name,
                    "size": 0,
                    "compressed": 0,
                    "is_dir": name.endswith("/"),
                })
    elif ext.endswith(".rar"):
        flags = 0x08000000 if os.name == "nt" else 0
        cli = _find_system_extractor()
        if cli and "7z" in cli.lower():
            # Usa 7z l -slt para parsing robusto estruturado por campos
            res = subprocess.run(
                [cli, "l", "-slt", str(archive_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags
            )
            current_entry: Dict[str, Any] = {}
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    if "name" in current_entry:
                        items.append(current_entry)
                        current_entry = {}
                    continue
                if line.startswith("Path = "):
                    path_val = line[7:].strip()
                    if path_val != str(archive_path):
                        current_entry["name"] = path_val
                elif line.startswith("Size = "):
                    try:
                        current_entry["size"] = int(line[7:].strip())
                    except ValueError:
                        current_entry["size"] = 0
                elif line.startswith("Packed Size = "):
                    try:
                        current_entry["compressed"] = int(line[14:].strip())
                    except ValueError:
                        current_entry["compressed"] = 0
                elif line.startswith("Folder = "):
                    current_entry["is_dir"] = (line[9:].strip() == "+")
            if "name" in current_entry:
                items.append(current_entry)
        else:
            res = subprocess.run(
                ["tar", "-tf", str(archive_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags
            )
            for line in res.stdout.splitlines():
                name = line.strip()
                if name:
                    items.append({"name": name, "size": 0, "compressed": 0, "is_dir": name.endswith("/")})

    return items


def format_archive_size(size_bytes: int) -> str:
    """Formata bytes em string legível."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    return f"{round(size_bytes / (1024 * 1024), 2)} MB"

