"""
Lógica pura de divisão e junção de arquivos compactados em múltiplos volumes (.001, .002 ou .part1.zip).
Suporta criação de volumes a partir de arquivos existentes ou empacotamento automático de pastas.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable, Dict, List, Optional
import zipfile

# Presets de tamanhos comuns de volumes em bytes
VOLUME_PRESETS = {
    "10 MB": 10 * 1024 * 1024,
    "25 MB (Discord / E-mail)": 25 * 1024 * 1024,
    "50 MB (WhatsApp)": 50 * 1024 * 1024,
    "100 MB": 100 * 1024 * 1024,
    "700 MB (CD-ROM)": 700 * 1024 * 1024,
    "2000 MB (FAT32 / Telegram)": 2000 * 1024 * 1024,
    "4000 MB (FAT32 Limite 4 GB)": 4000 * 1024 * 1024,
}


def split_file_into_volumes(
    input_file: Path,
    output_dir: Path,
    volume_size_bytes: int,
    pattern: str = "EXT_NUM",  # "EXT_NUM" (.zip.001) ou "PART_NUM" (.part01.zip)
    progress_cb: Optional[Callable[[int], None]] = None,
) -> List[Path]:
    """
    Divide um arquivo em múltiplos volumes sequenciais de tamanho fixo.
    """
    input_file = Path(input_file).resolve()
    if not input_file.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_file}")

    if volume_size_bytes <= 0:
        raise ValueError("O tamanho do volume deve ser maior que zero bytes.")

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    total_size = input_file.stat().st_size
    bytes_read = 0
    part_idx = 1
    created_volumes: List[Path] = []

    stem = input_file.stem
    ext = input_file.suffix

    with open(input_file, "rb") as src:
        while True:
            if pattern == "PART_NUM":
                part_name = f"{stem}.part{part_idx:02d}{ext}"
            else:  # "EXT_NUM"
                part_name = f"{input_file.name}.{part_idx:03d}"

            part_path = output_dir / part_name
            written_for_part = 0

            with open(part_path, "wb") as dst:
                while written_for_part < volume_size_bytes:
                    to_read = min(65536, volume_size_bytes - written_for_part)
                    chunk = src.read(to_read)
                    if not chunk:
                        break
                    dst.write(chunk)
                    written_for_part += len(chunk)
                    bytes_read += len(chunk)

                    if progress_cb and total_size > 0:
                        progress_cb(int((bytes_read / total_size) * 100))

            if written_for_part > 0:
                created_volumes.append(part_path)
                part_idx += 1
            else:
                # Arquivo vazio ou fim da leitura
                part_path.unlink(missing_ok=True)
                break

    return created_volumes


def find_volume_parts(first_part: Path) -> List[Path]:
    """
    Localiza todas as partes sequenciais de um volume no mesmo diretório.
    Ex: dado 'backup.zip.001', encontra .001, .002, .003...
    Ex: dado 'backup.part01.zip', encontra part01, part02, part03...
    """
    first_part = Path(first_part).resolve()
    if not first_part.is_file():
        raise FileNotFoundError(f"Arquivo de volume não encontrado: {first_part}")

    folder = first_part.parent
    name = first_part.name

    # Padrão 1: nome.ext.001, nome.ext.002
    m1 = re.match(r"^(.*?)\.(\d{3,})$", name)
    if m1:
        prefix = m1.group(1)
        # Busca todas as partes com prefixo
        candidates = []
        for f in folder.iterdir():
            if f.is_file():
                m = re.match(r"^" + re.escape(prefix) + r"\.(\d{3,})$", f.name)
                if m:
                    candidates.append((int(m.group(1)), f))
        candidates.sort(key=lambda x: x[0])
        return [c[1] for c in candidates]

    # Padrão 2: nome.part01.zip, nome.part02.zip
    m2 = re.match(r"^(.*?)\.part(\d+)(.*)$", name, re.IGNORECASE)
    if m2:
        prefix = m2.group(1)
        suffix = m2.group(3)
        candidates = []
        for f in folder.iterdir():
            if f.is_file():
                m = re.match(
                    r"^" + re.escape(prefix) + r"\.part(\d+)" + re.escape(suffix) + r"$",
                    f.name,
                    re.IGNORECASE,
                )
                if m:
                    candidates.append((int(m.group(1)), f))
        candidates.sort(key=lambda x: x[0])
        return [c[1] for c in candidates]

    return [first_part]


def join_volumes_to_file(
    volume_parts: List[Path],
    output_file: Path,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Reconstrói o arquivo consolidado a partir de uma lista de partes ordenadas.
    """
    if not volume_parts:
        raise ValueError("A lista de partes de volumes não pode ser vazia.")

    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    total_bytes = sum(p.stat().st_size for p in volume_parts)
    bytes_written = 0

    with open(output_file, "wb") as dst:
        for p in volume_parts:
            with open(p, "rb") as src:
                while chunk := src.read(65536):
                    dst.write(chunk)
                    bytes_written += len(chunk)
                    if progress_cb and total_bytes > 0:
                        progress_cb(int((bytes_written / total_bytes) * 100))

    return output_file
