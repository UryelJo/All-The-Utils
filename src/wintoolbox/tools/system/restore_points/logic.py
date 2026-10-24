"""
Lógica pura de gerenciamento de Pontos de Restauração do Windows (System Restore).
Totalmente desacoplada de bibliotecas de interface visual.
"""
import json
import os
import subprocess
from typing import Any, Dict, List, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.restore_points")


def is_system_restore_enabled() -> bool:
    """Verifica se a Proteção do Sistema está ativada na unidade C:."""
    ps_cmd = "(Get-WmiObject -Class Win32_ShadowCopy -List) -ne $null"
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=10
        )
        return "True" in proc.stdout
    except Exception:
        return True


def list_restore_points() -> List[Dict[str, Any]]:
    """Consulta os pontos de restauração existentes no Windows."""
    points: List[Dict[str, Any]] = []

    ps_cmd = (
        "Get-ComputerRestorePoint | Select-Object SequenceNumber, Description, "
        "RestorePointType, CreationTime | ConvertTo-Json -Compress"
    )

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=20
        )
        stdout = proc.stdout.strip()
        if not stdout:
            return []

        raw = json.loads(stdout)
        items = [raw] if isinstance(raw, dict) else raw

        for p in items:
            seq = int(p.get("SequenceNumber", 0))
            desc = str(p.get("Description", "Sem descrição"))
            rtype = str(p.get("RestorePointType", ""))
            ctime = str(p.get("CreationTime", ""))

            # Traduz tipos de ponto
            type_map = {
                "0": "Instalação de Aplicativo",
                "1": "Desinstalação de Aplicativo",
                "10": "Instalação de Driver",
                "12": "Modificação de Configurações",
                "13": "Ponto de Restauração Manual"
            }
            type_str = type_map.get(rtype, rtype or "Configuração do Sistema")

            points.append({
                "sequence_number": seq,
                "description": desc,
                "type": type_str,
                "creation_time": ctime
            })
    except Exception as exc:
        _log.warning("Falha ao consultar pontos de restauração: %s", exc)

    return points


def create_restore_point(description: str) -> Tuple[bool, str]:
    """Cria um novo ponto de restauração do sistema."""
    desc_clean = description.strip() or "WinToolbox Restore Point"
    # Escapa aspas para PowerShell
    desc_escaped = desc_clean.replace('"', '`"')

    ps_cmd = f'Checkpoint-Computer -Description "{desc_escaped}" -RestorePointType "MODIFY_SETTINGS" -ErrorAction Stop'

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=40
        )
        if proc.returncode == 0:
            return True, f"Ponto de restauração '{desc_clean}' criado com sucesso."
        else:
            err = proc.stderr.strip()
            if "privilege" in err.lower() or "administrator" in err.lower() or "permiss" in err.lower():
                return False, "Esta operação requer privilégios de Administrador. Execute o WinToolbox como Administrador."
            elif "frequency" in err.lower():
                return False, "O Windows limita a criação de pontos a um intervalo mínimo (geralmente a cada 24 horas)."
            return False, f"Falha ao criar ponto: {err or proc.stdout.strip()}"
    except Exception as exc:
        return False, f"Erro na chamada do sistema: {exc}"


def launch_restore_wizard() -> Tuple[bool, str]:
    """Abre o assistente gráfico nativo de restauração do Windows (rstrui.exe)."""
    try:
        os.startfile("rstrui.exe")
        return True, "Assistente de Restauração do Sistema aberto."
    except Exception as exc:
        return False, f"Não foi possível abrir o rstrui.exe: {exc}"
