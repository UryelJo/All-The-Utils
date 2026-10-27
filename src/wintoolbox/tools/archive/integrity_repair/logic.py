"""
Lógica pura para verificação de integridade estrutural e recuperação de emergência
de arquivos compactados danificados ou parcialmente corrompidos.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import struct
from typing import Any, Callable, Dict, List, Optional
import zlib
import zipfile


@dataclass
class ArchiveMemberStatus:
    name: str
    size: int
    compressed_size: int
    crc_expected: int
    crc_actual: int
    status: str  # "OK", "CORROMPIDO", "ERRO_LEITURA"
    error_message: Optional[str] = None


def verify_zip_integrity(archive_path: Path) -> Dict[str, Any]:
    """
    Inspeciona cada membro do arquivo ZIP validando checksum CRC32 e integridade de streams.
    """
    archive_path = Path(archive_path).resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {archive_path}")

    members: List[Dict[str, Any]] = []
    intact_count = 0
    corrupt_count = 0
    total_uncompressed = 0

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue

                crc_expected = info.CRC
                calc_crc = 0
                status = "OK"
                err_msg = None

                try:
                    # Lê em pedaços e calcula CRC
                    with zf.open(info, "r") as f:
                        while chunk := f.read(65536):
                            calc_crc = zlib.crc32(chunk, calc_crc)

                    if calc_crc != crc_expected:
                        status = "CORROMPIDO"
                        err_msg = f"CRC incompatível: esperado {hex(crc_expected)}, obtido {hex(calc_crc)}"
                        corrupt_count += 1
                    else:
                        intact_count += 1
                        total_uncompressed += info.file_size

                except Exception as e:
                    status = "ERRO_LEITURA"
                    err_msg = str(e)
                    corrupt_count += 1

                members.append({
                    "name": info.filename,
                    "size": info.file_size,
                    "compressed_size": info.compress_size,
                    "crc_expected": hex(crc_expected),
                    "crc_actual": hex(calc_crc),
                    "status": status,
                    "error": err_msg,
                })

        overall_status = "INTACTO" if corrupt_count == 0 else "PARCIALMENTE_CORROMPIDO"
        return {
            "status": overall_status,
            "archive_name": archive_path.name,
            "total_members": len(members),
            "intact_members": intact_count,
            "corrupt_members": corrupt_count,
            "total_uncompressed_bytes": total_uncompressed,
            "members": members,
            "header_intact": True,
        }

    except zipfile.BadZipFile as bz:
        # Tenta varredura de emergência por Local Headers PK\x03\x04
        salvage_list = scan_zip_local_headers(archive_path)
        return {
            "status": "DIRETORIO_CENTRAL_DANIFICADO",
            "archive_name": archive_path.name,
            "total_members": len(salvage_list),
            "intact_members": len(salvage_list),
            "corrupt_members": 1,
            "total_uncompressed_bytes": sum(m["size"] for m in salvage_list),
            "members": salvage_list,
            "header_intact": False,
            "error": f"Diretório central ausente ou truncado: {str(bz)}",
        }


def scan_zip_local_headers(archive_path: Path) -> List[Dict[str, Any]]:
    """
    Varredura heurística de baixo nível em arquivos ZIP quando o Central Directory
    foi truncado ou apagado. Localiza assinaturas PK\\x03\\x04.
    """
    found: List[Dict[str, Any]] = []
    data = archive_path.read_bytes()
    idx = 0
    sig = b"PK\x03\x04"

    while True:
        idx = data.find(sig, idx)
        if idx == -1 or idx + 30 > len(data):
            break

        try:
            # Desempacota cabeçalho local de arquivo ZIP (30 bytes)
            (
                ver,
                flags,
                method,
                mod_time,
                mod_date,
                crc,
                csize,
                usize,
                fn_len,
                extra_len,
            ) = struct.unpack("<HHHHHIIIHH", data[idx + 4 : idx + 30])

            fn_start = idx + 30
            fn_end = fn_start + fn_len
            if fn_end <= len(data):
                filename = data[fn_start:fn_end].decode("utf-8", errors="replace")
                data_start = fn_end + extra_len
                found.append({
                    "name": filename,
                    "size": usize,
                    "compressed_size": csize,
                    "crc_expected": hex(crc),
                    "crc_actual": "N/A",
                    "status": "RECUPERAVEL",
                    "method": method,
                    "data_offset": data_start,
                    "error": None,
                })
        except Exception:
            pass

        idx += 4

    return found


def salvage_archive_files(
    archive_path: Path,
    output_dir: Path,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Dict[str, Any]:
    """
    Executa a extração de salvamento de emergência:
    Tenta extrair cada membro individualmente. Se um membro estiver corrompido,
    ele é ignorado ou registrado, garantindo que nenhum arquivo intacto seja perdido.
    """
    archive_path = Path(archive_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    salvaged_files: List[str] = []
    failed_files: List[Dict[str, str]] = []

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            members = zf.infolist()
            total = len(members)

            for idx, info in enumerate(members):
                if info.is_dir():
                    continue

                dest_file = output_dir / info.filename
                # Proteção de segurança
                try:
                    if not dest_file.resolve().is_relative_to(output_dir.resolve()):
                        failed_files.append({"name": info.filename, "reason": "Path Traversal bloqueado"})
                        continue
                except AttributeError:
                    if not str(dest_file.resolve()).startswith(str(output_dir.resolve())):
                        failed_files.append({"name": info.filename, "reason": "Path Traversal bloqueado"})
                        continue

                try:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info, "r") as src, open(dest_file, "wb") as dst:
                        calc_crc = 0
                        while chunk := src.read(65536):
                            calc_crc = zlib.crc32(chunk, calc_crc)
                            dst.write(chunk)

                    if calc_crc != info.CRC:
                        # Arquivo foi gravado mas está corrompido internamente
                        failed_files.append({
                            "name": info.filename,
                            "reason": f"CRC incorreto (esperado {hex(info.CRC)}, obtido {hex(calc_crc)})",
                        })
                    else:
                        salvaged_files.append(info.filename)

                except Exception as e:
                    failed_files.append({"name": info.filename, "reason": str(e)})

                if progress_cb and total > 0:
                    progress_cb(int(((idx + 1) / total) * 100))

    except zipfile.BadZipFile:
        # Modo de recuperação direta por headers locais
        raw_items = scan_zip_local_headers(archive_path)
        data = archive_path.read_bytes()
        total = len(raw_items)

        for idx, item in enumerate(raw_items):
            fn = item["name"]
            dest_file = output_dir / fn
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            offset = item.get("data_offset", 0)
            csize = item.get("compressed_size", 0)
            method = item.get("method", 0)

            try:
                comp_bytes = data[offset : offset + csize]
                if method == 0:  # STORED
                    dest_file.write_bytes(comp_bytes)
                    salvaged_files.append(fn)
                elif method == 8:  # DEFLATED
                    decomp = zlib.decompress(comp_bytes, -zlib.MAX_WBITS)
                    dest_file.write_bytes(decomp)
                    salvaged_files.append(fn)
                else:
                    failed_files.append({"name": fn, "reason": f"Método de compressão {method} não suportado"})
            except Exception as e:
                failed_files.append({"name": fn, "reason": f"Falha na descompressão crua: {e}"})

            if progress_cb and total > 0:
                progress_cb(int(((idx + 1) / total) * 100))

    return {
        "status": "CONCLUIDO",
        "salvaged_count": len(salvaged_files),
        "failed_count": len(failed_files),
        "salvaged_files": salvaged_files,
        "failed_files": failed_files,
        "output_dir": str(output_dir),
    }
