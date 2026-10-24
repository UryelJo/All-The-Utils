"""
Lógica pura de reparo e apropriação de permissões NTFS (takeown e icacls).
Totalmente desacoplada de bibliotecas de interface visual.
"""
import os
from pathlib import Path
import subprocess
from typing import Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("files.permissions")


def repair_ntfs_permissions(
    target_path: Path,
    take_ownership: bool = True,
    reset_acls: bool = True,
    grant_current_user: bool = True
) -> Tuple[bool, str]:
    """
    Toma posse (takeown) e redefine as permissões NTFS (icacls)
    de arquivos ou pastas que estão apresentando erro de Acesso Negado.
    """
    p_str = str(target_path).strip()
    if not p_str or not target_path.exists():
        return False, f"O caminho informado não existe: {p_str}"

    is_dir = target_path.is_dir()
    logs = []

    # 1. Tomar posse (takeown)
    if take_ownership:
        takeown_cmd = ["takeown", "/F", p_str]
        if is_dir:
            takeown_cmd.extend(["/R", "/D", "Y"])

        try:
            proc = subprocess.run(
                takeown_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )
            if proc.returncode == 0:
                logs.append("Posse do item transferida com sucesso.")
            else:
                logs.append(f"Aviso takeown: {proc.stderr.strip() or proc.stdout.strip()}")
        except Exception as exc:
            logs.append(f"Falha takeown: {exc}")

    # 2. Redefinir ACLs herdadas (icacls /reset)
    if reset_acls:
        icacls_reset = ["icacls", p_str, "/reset"]
        if is_dir:
            icacls_reset.extend(["/T", "/C", "/Q"])

        try:
            proc_reset = subprocess.run(
                icacls_reset,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )
            if proc_reset.returncode == 0:
                logs.append("Permissões e herança NTFS redefinidas para o padrão.")
        except Exception as exc:
            logs.append(f"Falha icacls reset: {exc}")

    # 3. Conceder Controle Total ao usuário atual
    if grant_current_user:
        current_user = os.environ.get("USERNAME", "")
        if current_user:
            perm_spec = f"{current_user}:(OI)(CI)F" if is_dir else f"{current_user}:F"
            icacls_grant = ["icacls", p_str, "/grant:r", perm_spec]
            if is_dir:
                icacls_grant.extend(["/T", "/C", "/Q"])

            try:
                proc_grant = subprocess.run(
                    icacls_grant,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
                )
                if proc_grant.returncode == 0:
                    logs.append(f"Controle Total concedido para o usuário '{current_user}'.")
            except Exception as exc:
                logs.append(f"Falha icacls grant: {exc}")

    return True, "\n".join(logs)
