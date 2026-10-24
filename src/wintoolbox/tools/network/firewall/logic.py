"""
Lógica pura de consulta e configuração de regras do Firewall do Windows (netsh e Get-NetFirewallRule).
Totalmente desacoplada de bibliotecas de interface visual.
"""
import json
import subprocess
from typing import Any, Dict, List, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("network.firewall")


def list_firewall_rules(direction: str = "Inbound", max_rules: int = 150) -> List[Dict[str, Any]]:
    """Consulta regras ativas do Firewall do Windows via PowerShell."""
    rules: List[Dict[str, Any]] = []
    dir_filter = "Inbound" if direction.lower() in ("in", "inbound", "entrada") else "Outbound"

    ps_cmd = (
        f"Get-NetFirewallRule -Direction {dir_filter} -Enabled True | "
        f"Select-Object -First {max_rules} Name, DisplayName, Direction, Action, Profile | "
        "ConvertTo-Json -Compress"
    )

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            timeout=25
        )
        stdout = proc.stdout.strip()
        if not stdout:
            return []

        raw = json.loads(stdout)
        items = [raw] if isinstance(raw, dict) else raw

        for r in items:
            name = str(r.get("DisplayName") or r.get("Name", "Regra"))
            action = "Bloquear" if str(r.get("Action", "")) in ("2", "Block") else "Permitir"
            d_str = "Entrada" if str(r.get("Direction", "")) in ("1", "Inbound") else "Saída"
            prof = str(r.get("Profile", "Todos"))

            rules.append({
                "id": str(r.get("Name", "")),
                "name": name,
                "action": action,
                "direction": d_str,
                "profile": prof
            })
    except Exception as exc:
        _log.warning("Falha ao listar regras do firewall: %s", exc)

    return rules


def block_application_firewall(rule_name: str, exe_path: str, block_in: bool = True, block_out: bool = True) -> Tuple[bool, str]:
    """Cria regras no Firewall do Windows para bloquear o tráfego do executável."""
    name_clean = rule_name.strip() or "Bloqueio WinToolbox"
    p_clean = exe_path.strip()

    if not p_clean:
        return False, "Caminho do executável não informado."

    success_msgs = []
    errors = []

    # Bloqueio de Entrada
    if block_in:
        r_name_in = f"{name_clean} (Entrada)"
        cmd_in = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={r_name_in}", "dir=in", "action=block",
            f"program={p_clean}", "enable=yes"
        ]
        try:
            proc = subprocess.run(
                cmd_in, capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )
            if proc.returncode == 0:
                success_msgs.append("Entrada bloqueada")
            else:
                errors.append(f"Erro Entrada: {proc.stderr.strip() or proc.stdout.strip()}")
        except Exception as exc:
            errors.append(str(exc))

    # Bloqueio de Saída
    if block_out:
        r_name_out = f"{name_clean} (Saída)"
        cmd_out = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={r_name_out}", "dir=out", "action=block",
            f"program={p_clean}", "enable=yes"
        ]
        try:
            proc = subprocess.run(
                cmd_out, capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )
            if proc.returncode == 0:
                success_msgs.append("Saída bloqueada")
            else:
                errors.append(f"Erro Saída: {proc.stderr.strip() or proc.stdout.strip()}")
        except Exception as exc:
            errors.append(str(exc))

    if success_msgs and not errors:
        return True, f"Regra aplicada com sucesso ({', '.join(success_msgs)})."
    elif success_msgs and errors:
        return True, f"Parcialmente aplicado: {', '.join(success_msgs)}. Falhas: {', '.join(errors)}"
    return False, f"Falha ao criar regra (Requer privilégios de Administrador): {'; '.join(errors)}"


def delete_firewall_rule(rule_name: str) -> Tuple[bool, str]:
    """Exclui uma regra do Firewall pelo nome."""
    cmd = ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name.strip()}"]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )
        if proc.returncode == 0:
            return True, f"Regra '{rule_name}' removida com sucesso."
        return False, f"Falha ao excluir regra: {proc.stderr.strip() or proc.stdout.strip()}"
    except Exception as exc:
        return False, f"Erro: {exc}"
