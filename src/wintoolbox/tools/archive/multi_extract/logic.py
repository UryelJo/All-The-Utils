"""
Lógica pura para extração em lote de arquivos compactados (ZIP, TAR, TAR.GZ, TAR.BZ2, TAR.XZ).
Inclui proteção estrita contra ataques Zip Slip / Path Traversal e extração em subpastas organizadas.

Zero dependências de interface gráfica.
"""
import os
from pathlib import Path
import tarfile
from typing import Any, Dict, List, Optional
import zipfile


def is_safe_path(base_dir: Path, member_name: str) -> bool:
    """
    Verifica se o caminho do membro do arquivo compactado está contido no diretório de destino.
    Protege contra ataques de Zip Slip (ex: '../../windows/system32/cmd.exe').
    """
    base = base_dir.resolve()
    target = (base / member_name).resolve()
    try:
        return target.is_relative_to(base)
    except AttributeError:
        # Fallback para versões legadas
        return str(target).startswith(str(base))


def extract_single_archive(
    archive_path: Path,
    output_base: Path,
    create_subfolder: bool = True,
) -> Dict[str, Any]:
    """
    Extrai com segurança um único arquivo compactado (ZIP ou TAR).
    """
    arch = Path(archive_path).resolve()
    if not arch.is_file():
        raise FileNotFoundError(f"Arquivo compactado não encontrado: {arch}")

    dest_dir = output_base.resolve()
    if create_subfolder:
        folder_name = arch.stem
        # Trata extensões duplas como .tar.gz
        if folder_name.endswith(".tar"):
            folder_name = folder_name[:-4]
        dest_dir = dest_dir / folder_name

    dest_dir.mkdir(parents=True, exist_ok=True)

    extracted_files_count = 0
    total_uncompressed_bytes = 0

    if zipfile.is_zipfile(arch):
        with zipfile.ZipFile(arch, "r") as zf:
            for member in zf.infolist():
                if not is_safe_path(dest_dir, member.filename):
                    raise ValueError(
                        f"Ataque Zip Slip detectado no arquivo {arch.name}! Caminho malicioso: {member.filename}"
                    )
                zf.extract(member, dest_dir)
                if not member.is_dir():
                    extracted_files_count += 1
                    total_uncompressed_bytes += member.file_size

    elif tarfile.is_tarfile(arch):
        with tarfile.open(arch, "r:*") as tf:
            for member in tf.getmembers():
                if not is_safe_path(dest_dir, member.name):
                    raise ValueError(
                        f"Ataque Tar Slip detectado no arquivo {arch.name}! Caminho malicioso: {member.name}"
                    )
                tf.extract(member, dest_dir, filter="data" if hasattr(tarfile, "data_filter") else None)
                if member.isfile():
                    extracted_files_count += 1
                    total_uncompressed_bytes += member.size
    else:
        raise ValueError(f"Formato de arquivo compactado não suportado: {arch.suffix}")

    return {
        "archive_name": arch.name,
        "archive_path": str(arch),
        "dest_dir": str(dest_dir),
        "files_count": extracted_files_count,
        "total_bytes": total_uncompressed_bytes,
        "status": "OK",
        "error": None,
    }


def extract_batch_archives(
    archives: List[Path],
    output_base: Path,
    create_subfolder: bool = True,
) -> List[Dict[str, Any]]:
    """
    Extrai uma lista de arquivos compactados e gera o relatório completo de cada um.
    """
    results: List[Dict[str, Any]] = []

    for arch in archives:
        try:
            res = extract_single_archive(arch, output_base, create_subfolder=create_subfolder)
            results.append(res)
        except Exception as exc:
            results.append({
                "archive_name": Path(arch).name,
                "archive_path": str(arch),
                "dest_dir": str(output_base),
                "files_count": 0,
                "total_bytes": 0,
                "status": "FALHOU",
                "error": str(exc),
            })

    return results
