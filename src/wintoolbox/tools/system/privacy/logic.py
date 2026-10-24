"""
Lógica pura de controle de privacidade, telemetria e debloat do Windows 10 e 11.
Manipula chaves de registro do Windows (winreg) de forma estritamente segura e reversível.
Totalmente desacoplada de bibliotecas de interface visual.
"""
from typing import Any, Dict, List, Tuple
import winreg

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.privacy")

# Definições de itens de privacidade
PRIVACY_ITEMS = [
    {
        "id": "telemetry",
        "name": "Desativar Telemetria do Sistema",
        "desc": "Define AllowTelemetry = 0 nas políticas do Windows para desativar telemetria diagnóstica estendida.",
        "root": winreg.HKEY_LOCAL_MACHINE,
        "key_path": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        "value_name": "AllowTelemetry",
        "disabled_val": 0,
        "default_val": 1
    },
    {
        "id": "advertising_id",
        "name": "Desativar ID de Anúncios",
        "desc": "Impede aplicativos de usar seu identificador de publicidade para fornecer anúncios personalizados.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
        "value_name": "Enabled",
        "disabled_val": 0,
        "default_val": 1
    },
    {
        "id": "start_suggestions",
        "name": "Desativar Sugestões e Dicas no Menu Iniciar",
        "desc": "Remove sugestões de apps patrocinados e anúncios no Menu Iniciar e Configurações.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        "value_name": "SystemPaneSuggestionsEnabled",
        "disabled_val": 0,
        "default_val": 1
    },
    {
        "id": "copilot",
        "name": "Desativar Windows Copilot",
        "desc": "Desativa a integração e o botão do assistente Copilot na barra de tarefas e no sistema.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Policies\Microsoft\Windows\WindowsCopilot",
        "value_name": "TurnOffWindowsCopilot",
        "disabled_val": 1,
        "default_val": 0
    },
    {
        "id": "recall_ai",
        "name": "Desativar Análise de Dados e Recall de IA",
        "desc": "Bloqueia a captura contínua e análise de dados em segundo plano por componentes de IA do Windows.",
        "root": winreg.HKEY_LOCAL_MACHINE,
        "key_path": r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI",
        "value_name": "DisableAIDataAnalysis",
        "disabled_val": 1,
        "default_val": 0
    },
    {
        "id": "tailored_experiences",
        "name": "Desativar Experiências Personalizadas Diagnósticas",
        "desc": "Impede a Microsoft de oferecer recomendações personalizadas com base em seus dados de diagnóstico.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Policies\Microsoft\Windows\CloudContent",
        "value_name": "DisableTailoredExperiencesWithDiagnosticData",
        "disabled_val": 1,
        "default_val": 0
    }
]


def check_privacy_item_status(item: Dict[str, Any]) -> bool:
    """Verifica se a proteção de privacidade está ativa (True = Protegido/Desativada telemetria)."""
    try:
        with winreg.OpenKey(item["root"], item["key_path"], 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, item["value_name"])
            return val == item["disabled_val"]
    except Exception:
        return False


def get_all_privacy_statuses() -> List[Dict[str, Any]]:
    """Retorna a lista completa de opções de privacidade com o status atual."""
    statuses = []
    for item in PRIVACY_ITEMS:
        is_protected = check_privacy_item_status(item)
        statuses.append({
            "id": item["id"],
            "name": item["name"],
            "desc": item["desc"],
            "is_protected": is_protected
        })
    return statuses


def set_privacy_item(item_id: str, enable_protection: bool) -> Tuple[bool, str]:
    """Aplica ou reverte um ajuste de privacidade no Registro."""
    target_item = None
    for it in PRIVACY_ITEMS:
        if it["id"] == item_id:
            target_item = it
            break

    if not target_item:
        return False, f"Item {item_id} não encontrado."

    val_to_set = target_item["disabled_val"] if enable_protection else target_item["default_val"]

    try:
        # Cria ou abre a chave com permissão de escrita
        with winreg.CreateKeyEx(target_item["root"], target_item["key_path"], 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, target_item["value_name"], 0, winreg.REG_DWORD, val_to_set)
        return True, f"'{target_item['name']}' atualizado com sucesso."
    except PermissionError:
        return False, "Requer privilégios de Administrador para modificar esta chave de registro."
    except Exception as exc:
        return False, f"Falha ao alterar registro: {exc}"
