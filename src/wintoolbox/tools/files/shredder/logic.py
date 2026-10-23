"""
Lógica pura da ferramenta Triturador Seguro de Arquivos (File Shredder).
Sobrescreve dados em múltiplos passes (zeros, uns e aleatório criptográfico), trunca e renomeia antes de excluir definitivamente.
"""
import os
from pathlib import Path
import secrets
from typing import Callable, List, Optional


def shred_single_file(
    file_path: Path,
    passes: int = 3,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> None:
    """Sobrescreve o arquivo fisicamente no disco antes de apagá-lo."""
    if not file_path.exists() or not file_path.is_file():
        return

    length = file_path.stat().st_size
    chunk_size = 65536

    with open(file_path, "r+b") as f:
        for p in range(passes):
            f.seek(0)
            if p == 0:
                pattern = b"\x00" * chunk_size
            elif p == 1:
                pattern = b"\xff" * chunk_size
            else:
                pattern = secrets.token_bytes(chunk_size)

            written = 0
            while written < length:
                to_write = min(chunk_size, length - written)
                f.write(pattern[:to_write])
                written += to_write
                if progress_cb and length > 0:
                    progress_cb(int(((p * length + written) / (passes * length)) * 90))

            f.flush()
            os.fsync(f.fileno())

        # Trunca para tamanho zero
        f.truncate(0)

    # Renomeia para nome anônimo na MFT
    random_name = file_path.parent / f"tmp_shred_{secrets.token_hex(8)}.tmp"
    file_path.rename(random_name)

    # Remove permanentemente
    random_name.unlink(missing_ok=True)
    if progress_cb:
        progress_cb(100)


def shred_multiple_files(
    files: List[Path],
    passes: int = 3,
    progress_cb: Optional[Callable[[int, str], None]] = None,
) -> int:
    """Tritura uma lista de arquivos reportando o progresso consolidado."""
    total = len(files)
    for idx, f in enumerate(files):
        def on_file_p(percent):
            overall = int(((idx + (percent / 100)) / total) * 100)
            if progress_cb:
                progress_cb(overall, f"Triturando {f.name} ({idx + 1}/{total})...")

        shred_single_file(f, passes=passes, progress_cb=on_file_p)
    return total


def format_file_size(size_bytes: int) -> str:
    """Formata bytes em string humanamente legível."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)} KB"
    return f"{round(size_bytes / (1024 * 1024), 2)} MB"
