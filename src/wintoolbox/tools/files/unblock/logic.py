"""
Lógica pura de remoção da marca da web (Mark of the Web / Zone.Identifier) do NTFS.
Desbloqueia executáveis, planilhas, scripts e arquivos baixados da internet.
Totalmente desacoplada de bibliotecas de interface visual.
"""
import ctypes
import os
from pathlib import Path
from typing import Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("files.unblock")


def is_file_blocked(file_path: Path) -> bool:
    """
    Verifica se o arquivo possui o Alternate Data Stream (ADS) ':Zone.Identifier'
    que identifica arquivos baixados de zonas não confiáveis ou internet.
    """
    zone_stream = str(file_path) + ":Zone.Identifier"
    try:
        # Tenta abrir o stream para leitura
        handle = ctypes.windll.kernel32.CreateFileW(
            zone_stream,
            0x80000000,  # GENERIC_READ
            0x00000001,  # FILE_SHARE_READ
            None,
            3,           # OPEN_EXISTING
            0x00000080,  # FILE_ATTRIBUTE_NORMAL
            None
        )
        if handle != -1 and handle != 0:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


def unblock_file(file_path: Path) -> Tuple[bool, str]:
    """
    Remove o Alternate Data Stream ':Zone.Identifier' do arquivo NTFS.
    Equivale ao comando PowerShell Unblock-File ou botão 'Desbloquear' nas Propriedades do arquivo.
    """
    zone_stream = str(file_path) + ":Zone.Identifier"

    # Se o stream existe, deleta
    ret = ctypes.windll.kernel32.DeleteFileW(zone_stream)
    if ret:
        return True, "Bloqueio Mark of the Web removido com sucesso."

    # Se não deletou via API direta, verifica se já estava desbloqueado
    last_err = ctypes.windll.kernel32.GetLastError()
    # ERROR_FILE_NOT_FOUND = 2
    if last_err == 2 or not is_file_blocked(file_path):
        return True, "O arquivo já estava desbloqueado (sem marcação de internet)."

    # Tentativa de fallback via PowerShell nativo
    try:
        import subprocess
        p = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", f'Unblock-File -LiteralPath "{str(file_path)}"'],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )
        if p.returncode == 0:
            return True, "Desbloqueado com sucesso via PowerShell."
    except Exception:
        pass

    return False, f"Falha ao desbloquear o arquivo (Código de erro Win32: {last_err})."
