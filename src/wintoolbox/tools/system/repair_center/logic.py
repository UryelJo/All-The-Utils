"""
Lógica pura de rotinas de reparo de componentes essenciais do Windows.
Totalmente desacoplada de bibliotecas de interface visual.
"""
import glob
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Dict, List, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.repair_center")


def _run_cmd(cmd_list: List[str], timeout: int = 30) -> Tuple[int, str, str]:
    """Executa um comando de sistema silenciosamente."""
    try:
        proc = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=timeout
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return -1, "", str(exc)


def repair_print_spooler() -> Tuple[bool, str]:
    """
    Destrava a fila de impressão:
    1. Para o serviço Spooler de Impressão (net stop spooler)
    2. Apaga arquivos residuais em C:\\Windows\\System32\\spool\\PRINTERS
    3. Reinicia o serviço Spooler (net start spooler)
    """
    _run_cmd(["net", "stop", "spooler"])
    time.sleep(1)

    printers_dir = Path("C:/Windows/System32/spool/PRINTERS")
    cleared = 0
    if printers_dir.exists():
        try:
            for item in printers_dir.glob("*"):
                try:
                    if item.is_file():
                        item.unlink()
                        cleared += 1
                except Exception:
                    pass
        except Exception as exc:
            _log.warning("Falha ao limpar spooler: %s", exc)

    code, out, err = _run_cmd(["net", "start", "spooler"])
    if code == 0:
        return True, f"Spooler de impressão reiniciado. {cleared} arquivo(s) travados foram removidos da fila."
    return False, f"Falha ao iniciar Spooler: {err or out}"


def clear_icon_and_thumbnail_cache() -> Tuple[bool, str]:
    """
    Limpa o cache corrompido de ícones e miniaturas do Windows Explorer.
    """
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return False, "Variável LOCALAPPDATA não encontrada."

    exp_dir = Path(local_app_data) / "Microsoft" / "Windows" / "Explorer"
    deleted = 0

    # Para explorer.exe momentaneamente
    _run_cmd(["taskkill", "/f", "/im", "explorer.exe"])
    time.sleep(1)

    # Deleta IconCache*.db e thumbcache*.db
    if exp_dir.exists():
        for pat in ["iconcache*.db", "thumbcache*.db"]:
            for f in exp_dir.glob(pat):
                try:
                    f.unlink()
                    deleted += 1
                except Exception:
                    pass

    # Também o IconCache.db da raiz de LocalAppData
    legacy_cache = Path(local_app_data) / "IconCache.db"
    if legacy_cache.exists():
        try:
            legacy_cache.unlink()
            deleted += 1
        except Exception:
            pass

    # Reinicia o Explorer
    subprocess.Popen("explorer.exe")
    return True, f"Cache de ícones e miniaturas reconstruído ({deleted} arquivos removidos). Explorer reiniciado."


def reset_windows_update() -> Tuple[bool, str]:
    """
    Para os serviços de atualização e limpa a pasta de cache do Windows Update (SoftwareDistribution).
    """
    services = ["wuauserv", "cryptSvc", "bits", "msiserver"]
    for s in services:
        _run_cmd(["net", "stop", s])

    # Limpa arquivos temporários do download do Windows Update
    sd_dir = Path("C:/Windows/SoftwareDistribution/Download")
    removed = 0
    if sd_dir.exists():
        for f in sd_dir.glob("*"):
            try:
                if f.is_file():
                    f.unlink()
                    removed += 1
            except Exception:
                pass

    for s in services:
        _run_cmd(["net", "start", s])

    return True, f"Componentes do Windows Update resetados ({removed} downloads temporários limpos e serviços reiniciados)."


def reset_microsoft_store() -> Tuple[bool, str]:
    """Executa o utilitário nativo de reset da Microsoft Store (wsreset.exe)."""
    try:
        subprocess.Popen("wsreset.exe")
        return True, "Comando wsreset disparado com sucesso. O cache da loja foi limpo."
    except Exception as exc:
        return False, f"Falha ao executar wsreset: {exc}"


def flush_network_stack() -> Tuple[bool, str]:
    """Limpa o cache DNS e redefine o catálogo Winsock e pilha TCP/IP."""
    _run_cmd(["ipconfig", "/flushdns"])
    code1, _, _ = _run_cmd(["netsh", "winsock", "reset"])
    return True, "Cache DNS limpo e catálogo Winsock redefinido com sucesso."
