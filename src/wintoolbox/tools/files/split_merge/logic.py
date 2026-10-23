"""
Lógica pura da ferramenta Divisor e Juntador de Arquivos (File Split & Merge).
Operações de leitura e escrita em blocos sem acoplamento a UI.
"""
from pathlib import Path
from typing import Callable, List, Optional


def split_file(
    src_path: Path,
    part_size_bytes: int,
    out_dir: Path,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> List[Path]:
    """Divide um arquivo em partes numeradas sequencialmente (.part001, .part002...)."""
    total_size = src_path.stat().st_size
    parts: List[Path] = []
    part_num = 1
    read_total = 0

    chunk_size = 1048576  # 1MB buffer
    with open(src_path, "rb") as f_in:
        while read_total < total_size:
            part_name = f"{src_path.name}.part{str(part_num).zfill(3)}"
            part_path = out_dir / part_name
            parts.append(part_path)

            current_part_written = 0
            with open(part_path, "wb") as f_out:
                while current_part_written < part_size_bytes and read_total < total_size:
                    to_read = min(chunk_size, part_size_bytes - current_part_written)
                    data = f_in.read(to_read)
                    if not data:
                        break
                    f_out.write(data)
                    current_part_written += len(data)
                    read_total += len(data)
                    if progress_cb and total_size > 0:
                        progress_cb(int((read_total / total_size) * 100))

            part_num += 1

    return parts


def merge_files(
    part_paths: List[Path],
    output_file: Path,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> None:
    """Reconstitui o arquivo original juntando as partes em ordem."""
    part_paths.sort(key=lambda p: p.name)
    total_size = sum(p.stat().st_size for p in part_paths)
    written_total = 0
    chunk_size = 1048576

    with open(output_file, "wb") as f_out:
        for p in part_paths:
            with open(p, "rb") as f_in:
                while chunk := f_in.read(chunk_size):
                    f_out.write(chunk)
                    written_total += len(chunk)
                    if progress_cb and total_size > 0:
                        progress_cb(int((written_total / total_size) * 100))
