"""
Lógica pura para sanitização e sobrescrita de espaço livre em discos e partições.
Utiliza o comando nativo cipher /w do Windows ou rotina de preenchimento criptográfico para prevenir recuperação forense.

Zero dependências de interface gráfica ou widgets.
"""
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable, Dict, List, Optional


def get_drive_space_info(target_path: str) -> Dict[str, Any]:
    """
    Retorna o espaço total, usado e livre de um diretório ou partição.
    """
    p = Path(target_path)
    if not p.exists():
        raise FileNotFoundError(f"Caminho não encontrado: {target_path}")

    total, used, free = shutil.disk_usage(str(p))

    def _fmt(size: int) -> str:
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

    return {
        "path": str(p),
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "total_formatted": _fmt(total),
        "used_formatted": _fmt(used),
        "free_formatted": _fmt(free),
        "percent_free": round((free / (total or 1)) * 100, 1),
    }


def build_cipher_wipe_command(target_dir: str) -> List[str]:
    """
    Gera o comando nativo do Windows para sanitização de espaço livre: cipher /w:<diretório>.
    O cipher executa 3 passadas no espaço não alocado (0x00, 0xFF e números pseudoaleatórios).
    """
    clean_dir = str(Path(target_dir).resolve())
    return ["cipher", f"/w:{clean_dir}"]


def sanitize_free_space_python(
    target_dir: str,
    max_mb: Optional[int] = None,
    pattern: bytes = b"\x00",
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """
    Rotina em Python puro para preencher o espaço livre temporariamente com bytes constantes
    e em seguida expurgar o arquivo, forçando a sobrescrita de setores vazios.
    """
    p = Path(target_dir)
    if not p.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {target_dir}")

    space = shutil.disk_usage(str(p))
    free_available = space.free

    # Se max_mb for especificado, respeita o limite (com margem de segurança de 50 MB)
    margin = 50 * 1024 * 1024
    usable_free = max(0, free_available - margin)
    target_bytes = usable_free
    if max_mb:
        target_bytes = min(target_bytes, max_mb * 1024 * 1024)

    if target_bytes <= 0:
        return {"bytes_wiped": 0, "success": True, "message": "Espaço livre insuficiente para sobrescrita segura."}

    block_size = 1024 * 1024  # 1 MB por bloco
    pattern_block = (pattern * (block_size // len(pattern) + 1))[:block_size]

    temp_file = p / f"_wipe_temp_{os.getpid()}.tmp"
    bytes_written = 0

    try:
        with open(temp_file, "wb") as f:
            while bytes_written < target_bytes:
                chunk_len = min(block_size, target_bytes - bytes_written)
                f.write(pattern_block[:chunk_len])
                bytes_written += chunk_len
                if progress_callback:
                    progress_callback(bytes_written, target_bytes)
            f.flush()
            os.fsync(f.fileno())
    finally:
        if temp_file.exists():
            try:
                os.remove(temp_file)
            except OSError:
                pass

    return {
        "bytes_wiped": bytes_written,
        "mb_wiped": round(bytes_written / (1024 * 1024), 2),
        "success": True,
        "message": f"Sobrescrita concluída com sucesso ({round(bytes_written / (1024 * 1024), 1)} MB sobrescritos).",
    }
