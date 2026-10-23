"""
Lógica pura do Modificador em Lote de Datas e Atributos de Arquivos (Timestamp Editor).
Altera CreationTime (ctime), LastWriteTime (mtime) e LastAccessTime (atime) no Windows via kernel32 SetFileTime.
"""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import List, Optional

# Constantes da API Win32
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000  # Permite abrir diretórios também


class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD)
    ]


@dataclass
class FileTimestampInfo:
    path: Path
    ctime: float
    mtime: float
    atime: float

    @property
    def formatted_ctime(self) -> str:
        return datetime.fromtimestamp(self.ctime).strftime("%d/%m/%Y %H:%M:%S")

    @property
    def formatted_mtime(self) -> str:
        return datetime.fromtimestamp(self.mtime).strftime("%d/%m/%Y %H:%M:%S")

    @property
    def formatted_atime(self) -> str:
        return datetime.fromtimestamp(self.atime).strftime("%d/%m/%Y %H:%M:%S")


@dataclass
class TimestampUpdateResult:
    path: Path
    success: bool
    error: Optional[str] = None


def unix_to_filetime(timestamp: float) -> FILETIME:
    """Converte um timestamp Unix (segundos desde 1970) para estrutura FILETIME do Windows."""
    # 100-nanosecond intervals since January 1, 1601 UTC
    ft_val = int(timestamp * 10000000) + 116444736000000000
    low = ft_val & 0xFFFFFFFF
    high = (ft_val >> 32) & 0xFFFFFFFF
    return FILETIME(low, high)


def get_file_timestamps(path: Path) -> FileTimestampInfo:
    """Lê as datas de criação, modificação e acesso de um arquivo."""
    st = path.stat()
    # No Windows st.st_ctime representa creation time
    return FileTimestampInfo(
        path=path,
        ctime=st.st_ctime,
        mtime=st.st_mtime,
        atime=st.st_atime,
    )


def set_file_timestamps(
    path: Path,
    ctime: Optional[float] = None,
    mtime: Optional[float] = None,
    atime: Optional[float] = None,
) -> bool:
    """
    Define os atributos de data e hora do arquivo no Windows usando kernel32.SetFileTime.
    """
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    kernel32 = ctypes.windll.kernel32

    # Abre o handle do arquivo com permissão de escrita de atributos
    handle = kernel32.CreateFileW(
        str(path),
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS,
        None
    )

    if handle == -1 or handle == 0xFFFFFFFF:
        err = ctypes.GetLastError()
        raise OSError(f"Falha ao abrir arquivo para gravação de atributos (Erro Win32: {err})")

    try:
        ft_creation = ctypes.byref(unix_to_filetime(ctime)) if ctime is not None else None
        ft_access = ctypes.byref(unix_to_filetime(atime)) if atime is not None else None
        ft_write = ctypes.byref(unix_to_filetime(mtime)) if mtime is not None else None

        res = kernel32.SetFileTime(handle, ft_creation, ft_access, ft_write)
        if res == 0:
            err = ctypes.GetLastError()
            raise OSError(f"Falha na API SetFileTime (Erro Win32: {err})")
        return True
    finally:
        kernel32.CloseHandle(handle)


def batch_update_timestamps(
    files: List[Path],
    ctime: Optional[float] = None,
    mtime: Optional[float] = None,
    atime: Optional[float] = None,
    offset_seconds: Optional[float] = None,
) -> List[TimestampUpdateResult]:
    """
    Aplica as novas datas a uma lista de arquivos.
    Se offset_seconds for fornecido, adiciona o offset às datas originais de cada arquivo.
    """
    results: List[TimestampUpdateResult] = []

    for f in files:
        p = Path(f)
        try:
            curr = get_file_timestamps(p)

            target_c = ctime
            target_m = mtime
            target_a = atime

            if offset_seconds is not None:
                if target_c is None:
                    target_c = curr.ctime + offset_seconds
                if target_m is None:
                    target_m = curr.mtime + offset_seconds
                if target_a is None:
                    target_a = curr.atime + offset_seconds

            set_file_timestamps(p, ctime=target_c, mtime=target_m, atime=target_a)
            results.append(TimestampUpdateResult(path=p, success=True))
        except Exception as e:
            results.append(TimestampUpdateResult(path=p, success=False, error=str(e)))

    return results
