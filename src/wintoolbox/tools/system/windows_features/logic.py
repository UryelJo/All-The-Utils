"""
Lógica pura para consulta e gerenciamento de recursos opcionais do Windows.

Permite listar, habilitar e desabilitar recursos do sistema operacional (ex.: Hyper-V,
Windows Sandbox, WSL, Telnet, SMB 1.0) utilizando DISM e PowerShell.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
from dataclasses import asdict, dataclass
import json
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.windows_features.logic")


@dataclass
class WindowsFeature:
    name: str
    display_name: str
    state: str  # "Enabled", "Disabled", "EnablePending", "DisablePending"
    description: str = ""

    @property
    def is_enabled(self) -> bool:
        return self.state.lower() in ("enabled", "enablepending")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_features_json(json_str: str) -> List[WindowsFeature]:
    """
    Analisa a saída JSON de Get-WindowsOptionalFeature.
    """
    if not json_str.strip():
        return []

    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            data = [data]
    except Exception as e:
        _log.warning(f"Erro ao decodificar JSON de recursos: {e}")
        return []

    features: List[WindowsFeature] = []
    for item in data:
        raw_name = str(item.get("FeatureName") or item.get("name") or "").strip()
        if not raw_name:
            continue

        raw_state = str(item.get("State") or "Disabled").strip()
        display = str(item.get("DisplayName") or raw_name).strip()
        desc = str(item.get("Description") or "").strip()

        features.append(WindowsFeature(
            name=raw_name,
            display_name=display,
            state=raw_state,
            description=desc
        ))

    return features


def parse_dism_text_output(dism_text: str) -> List[WindowsFeature]:
    """
    Analisa saída de texto puro de 'dism /online /get-features'.
    """
    features: List[WindowsFeature] = []
    current_name: Optional[str] = None
    current_state: Optional[str] = None

    for line in dism_text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Feature Name : Microsoft-Hyper-V-All
        # State : Enabled
        m_name = re.match(r"^(?:Nome do recurso|Feature Name)\s*:\s*(.+)$", line, re.IGNORECASE)
        if m_name:
            current_name = m_name.group(1).strip()
            continue

        m_state = re.match(r"^(?:Estado|State)\s*:\s*(.+)$", line, re.IGNORECASE)
        if m_state and current_name:
            current_state = m_state.group(1).strip()
            # Mapeia português/inglês
            norm_state = "Enabled" if "habilit" in current_state.lower() or "enable" in current_state.lower() else "Disabled"
            features.append(WindowsFeature(
                name=current_name,
                display_name=current_name,
                state=norm_state,
                description=""
            ))
            current_name = None
            current_state = None

    return features


def query_windows_features() -> List[WindowsFeature]:
    """
    Consulta a lista de recursos opcionais do Windows via PowerShell.
    """
    ps_cmd = (
        "Get-WindowsOptionalFeature -Online | "
        "Select-Object FeatureName, State, DisplayName, Description | "
        "ConvertTo-Json -Depth 2 -Compress"
    )

    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=25,
            check=False
        )
        if res.returncode == 0 and res.stdout.strip():
            return parse_features_json(res.stdout)
    except Exception as e:
        _log.warning(f"Falha ao consultar recursos opcionais via PowerShell: {e}")

    # Fallback DISM rápido
    try:
        res_dism = subprocess.run(
            ["dism.exe", "/online", "/get-features"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False
        )
        if res_dism.stdout.strip():
            return parse_dism_text_output(res_dism.stdout)
    except Exception as e:
        _log.warning(f"Falha no fallback DISM: {e}")

    return []


def set_windows_feature_state(feature_name: str, enable: bool) -> Tuple[bool, str]:
    """
    Ativa ou desativa um recurso do Windows com elevação UAC.
    """
    action = "Enable-WindowsOptionalFeature" if enable else "Disable-WindowsOptionalFeature"
    ps_arg = f"{action} -Online -FeatureName '{feature_name}' -NoRestart"

    # Executa com elevação sob demanda (runAs)
    elevated_cmd = f"Start-Process powershell -Verb runAs -Wait -ArgumentList \"-NoProfile -Command {ps_arg}\""

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", elevated_cmd],
            capture_output=True,
            text=True,
            timeout=60,
            check=False
        )
        if proc.returncode == 0:
            status_text = "habilitado" if enable else "desabilitado"
            return (True, f"Recurso '{feature_name}' {status_text} com sucesso. Pode ser necessário reiniciar.")
        else:
            return (False, f"Erro ao alterar recurso (código {proc.returncode}): {proc.stderr.strip()}")
    except Exception as e:
        return (False, f"Falha na execução: {e}")
