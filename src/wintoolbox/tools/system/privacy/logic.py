"""
Lógica pura de controle de privacidade, telemetria e debloat do Windows 10 e 11
(inspirada no projeto Raphire/Win11Debloat).
Manipula chaves de registro do Windows (winreg) e pacotes Appx de forma segura e reversível.
Totalmente desacoplada de bibliotecas de interface visual.
"""
import json
import subprocess
import sys
from typing import Any, Dict, List, Tuple
import winreg

from wintoolbox.core.logging_setup import get_logger
from wintoolbox.core.shell import CREATE_NO_WINDOW

_log = get_logger("system.privacy")


def detect_windows_os_version() -> Dict[str, Any]:
    """
    Detecta se o sistema operacional é Windows 10 ou Windows 11 com base no número da build
    (Windows 11 inicia na build 22000).
    """
    try:
        ver = sys.getwindowsversion()
        build = int(getattr(ver, "build", 0))
    except Exception:
        build = 19045

    is_win11 = build >= 22000
    os_tag = "win11" if is_win11 else "win10"
    os_label = f"Windows 11 (Build {build})" if is_win11 else f"Windows 10 (Build {build})"
    return {
        "os_tag": os_tag,
        "is_win11": is_win11,
        "is_win10": not is_win11,
        "build": build,
        "label": os_label,
    }


# Definições de itens de privacidade e debloat (inspirados no Win11Debloat)
# supported_os: ["win10", "win11"], ["win11"] ou ["win10"]
PRIVACY_ITEMS: List[Dict[str, Any]] = [
    # --- Telemetria e Privacidade ---
    {
        "id": "telemetry",
        "category": "Privacidade e Telemetria",
        "name": "Desativar Telemetria e Coleta de Dados Diagnósticos",
        "desc": "Define AllowTelemetry = 0 nas políticas do Windows para bloquear envio de telemetria estendida.",
        "root": winreg.HKEY_LOCAL_MACHINE,
        "key_path": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        "value_name": "AllowTelemetry",
        "disabled_val": 0,
        "default_val": 1,
        "supported_os": ["win10", "win11"],
        "requires_admin": True,
    },
    {
        "id": "advertising_id",
        "category": "Privacidade e Telemetria",
        "name": "Desativar ID de Anúncios e Rastreamento Publicitário",
        "desc": "Impede que aplicativos usem seu identificador de publicidade para perfis de anúncios.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
        "value_name": "Enabled",
        "disabled_val": 0,
        "default_val": 1,
        "supported_os": ["win10", "win11"],
        "requires_admin": False,
    },
    {
        "id": "activity_history",
        "category": "Privacidade e Telemetria",
        "name": "Desativar Histórico de Atividades e Sincronização de Linha do Tempo",
        "desc": "Impede o Windows de coletar e enviar histórico de atividades e aplicativos abertos para a nuvem.",
        "root": winreg.HKEY_LOCAL_MACHINE,
        "key_path": r"SOFTWARE\Policies\Microsoft\Windows\System",
        "value_name": "PublishUserActivities",
        "disabled_val": 0,
        "default_val": 1,
        "supported_os": ["win10", "win11"],
        "requires_admin": True,
    },
    {
        "id": "app_launch_tracking",
        "category": "Privacidade e Telemetria",
        "name": "Desativar Rastreamento de Inicialização de Aplicativos",
        "desc": "Impede o Windows de monitorar quais programas você abre com mais frequência.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        "value_name": "Start_TrackProgs",
        "disabled_val": 0,
        "default_val": 1,
        "supported_os": ["win10", "win11"],
        "requires_admin": False,
    },
    {
        "id": "tailored_experiences",
        "category": "Privacidade e Telemetria",
        "name": "Desativar Experiências Personalizadas com Dados de Diagnóstico",
        "desc": "Bloqueia recomendações e dicas personalizadas da Microsoft baseadas em seus dados.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Policies\Microsoft\Windows\CloudContent",
        "value_name": "DisableTailoredExperiencesWithDiagnosticData",
        "disabled_val": 1,
        "default_val": 0,
        "supported_os": ["win10", "win11"],
        "requires_admin": False,
    },
    # --- Inteligência Artificial, Busca e Sugestões ---
    {
        "id": "start_suggestions",
        "category": "IA, Busca e Anúncios",
        "name": "Desativar Sugestões, Dicas e Apps Patrocinados no Menu Iniciar",
        "desc": "Remove sugestões de aplicativos promovidos e anúncios no Menu Iniciar e Configurações.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        "value_name": "SystemPaneSuggestionsEnabled",
        "disabled_val": 0,
        "default_val": 1,
        "supported_os": ["win10", "win11"],
        "requires_admin": False,
    },
    {
        "id": "silent_installed_apps",
        "category": "IA, Busca e Anúncios",
        "name": "Bloquear Instalação Silenciosa de Bloatware (SilentInstalledApps)",
        "desc": "Impede o Windows de baixar e instalar automaticamente jogos e apps patrocinados em segundo plano.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager",
        "value_name": "SilentInstalledAppsEnabled",
        "disabled_val": 0,
        "default_val": 1,
        "supported_os": ["win10", "win11"],
        "requires_admin": False,
    },
    {
        "id": "bing_search",
        "category": "IA, Busca e Anúncios",
        "name": "Desativar Busca Web (Bing) e Resultados de Internet no Menu Iniciar",
        "desc": "Faz com que a pesquisa do Menu Iniciar busque apenas arquivos e aplicativos locais (mais rápido e privado).",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Policies\Microsoft\Windows\Explorer",
        "value_name": "DisableSearchBoxSuggestions",
        "disabled_val": 1,
        "default_val": 0,
        "supported_os": ["win10", "win11"],
        "requires_admin": False,
    },
    {
        "id": "copilot",
        "category": "IA, Busca e Anúncios",
        "name": "Desativar Windows Copilot",
        "desc": "Desativa o assistente Windows Copilot na barra de tarefas e no sistema.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Policies\Microsoft\Windows\WindowsCopilot",
        "value_name": "TurnOffWindowsCopilot",
        "disabled_val": 1,
        "default_val": 0,
        "supported_os": ["win10", "win11"],
        "requires_admin": False,
    },
    {
        "id": "recall_ai",
        "category": "IA, Busca e Anúncios",
        "name": "Desativar Windows Recall e Análise de Dados por IA (Windows 11)",
        "desc": "Bloqueia a captura contínua de snapshots de tela e análise de dados pelo recurso Recall AI.",
        "root": winreg.HKEY_LOCAL_MACHINE,
        "key_path": r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI",
        "value_name": "DisableAIDataAnalysis",
        "disabled_val": 1,
        "default_val": 0,
        "supported_os": ["win11"],
        "requires_admin": True,
    },
    # --- Barra de Tarefas e Interface (Win11Debloat) ---
    {
        "id": "taskbar_widgets_w11",
        "category": "Interface e Barra de Tarefas",
        "name": "Ocultar Painel de Widgets e Notícias da Barra de Tarefas (Windows 11)",
        "desc": "Desativa o botão e o serviço de Widgets (clima/notícias MSN) na barra de tarefas do Windows 11.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        "value_name": "TaskbarDa",
        "disabled_val": 0,
        "default_val": 1,
        "supported_os": ["win11"],
        "requires_admin": False,
    },
    {
        "id": "taskbar_chat_w11",
        "category": "Interface e Barra de Tarefas",
        "name": "Ocultar Ícone de Chat (Microsoft Teams Pessoal) na Barra de Tarefas (Windows 11)",
        "desc": "Remove o atalho nativo de Chat/Teams da barra de tarefas do Windows 11.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        "value_name": "TaskbarMn",
        "disabled_val": 0,
        "default_val": 1,
        "supported_os": ["win11"],
        "requires_admin": False,
    },
    {
        "id": "taskbar_align_left_w11",
        "category": "Interface e Barra de Tarefas",
        "name": "Alinhar Ícones da Barra de Tarefas à Esquerda (Windows 11)",
        "desc": "Muda o alinhamento do Menu Iniciar do centro para o canto esquerdo clássico.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        "value_name": "TaskbarAl",
        "disabled_val": 0,
        "default_val": 1,
        "supported_os": ["win11"],
        "requires_admin": False,
    },
    {
        "id": "news_and_interests_w10",
        "category": "Interface e Barra de Tarefas",
        "name": "Desativar 'Notícias e Interesses' na Barra de Tarefas (Windows 10)",
        "desc": "Oculta o widget de clima e notícias do feed MSN na barra de tarefas do Windows 10.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Microsoft\Windows\CurrentVersion\Feeds",
        "value_name": "ShellFeedsTaskbarViewMode",
        "disabled_val": 2,
        "default_val": 0,
        "supported_os": ["win10"],
        "requires_admin": False,
    },
    {
        "id": "explorer_launch_this_pc",
        "category": "Interface e Barra de Tarefas",
        "name": "Abrir Explorador de Arquivos diretamente em 'Este Computador'",
        "desc": "Faz o Windows Explorer abrir na visão de discos ('Este Computador') em vez de 'Início / Acesso Rápido'.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        "value_name": "LaunchTo",
        "disabled_val": 1,
        "default_val": 2,
        "supported_os": ["win10", "win11"],
        "requires_admin": False,
    },
    {
        "id": "hide_task_view",
        "category": "Interface e Barra de Tarefas",
        "name": "Ocultar Botão 'Visão de Tarefas' (Task View) da Barra de Tarefas",
        "desc": "Oculta o ícone de alternância de áreas de trabalho virtuais na barra de tarefas.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
        "value_name": "ShowTaskViewButton",
        "disabled_val": 0,
        "default_val": 1,
        "supported_os": ["win10", "win11"],
        "requires_admin": False,
    },
    {
        "id": "disable_game_dvr",
        "category": "Desempenho e Jogos",
        "name": "Desativar Gravação em Segundo Plano (Xbox Game DVR)",
        "desc": "Melhora o FPS e reduz engasgos em jogos desativando a captura de vídeo contínua do Game DVR.",
        "root": winreg.HKEY_CURRENT_USER,
        "key_path": r"System\GameConfigStore",
        "value_name": "GameDVR_Enabled",
        "disabled_val": 0,
        "default_val": 1,
        "supported_os": ["win10", "win11"],
        "requires_admin": False,
    },
]


# Catálogo curado de Bloatware (baseado no Raphire/Win11Debloat)
BLOATWARE_APPX_CATALOG: List[Dict[str, str]] = [
    {"pattern": "Clipchamp.Clipchamp", "name": "Microsoft Clipchamp", "desc": "Editor de vídeo pré-instalado"},
    {"pattern": "Microsoft.549981C3F5F10", "name": "Cortana", "desc": "Assistente de voz legado da Microsoft"},
    {"pattern": "Microsoft.BingNews", "name": "Microsoft Notícias (Bing News)", "desc": "Portal de notícias MSN"},
    {"pattern": "Microsoft.BingWeather", "name": "MSN Clima (Bing Weather)", "desc": "Previsão do tempo"},
    {"pattern": "Microsoft.BingFinance", "name": "MSN Dinheiro (Bing Finance)", "desc": "Notícias financeiras"},
    {"pattern": "Microsoft.BingSports", "name": "MSN Esportes (Bing Sports)", "desc": "Notícias esportivas"},
    {"pattern": "Microsoft.GamingApp", "name": "Aplicativo Xbox", "desc": "Cliente da loja Xbox"},
    {"pattern": "Microsoft.XboxGamingOverlay", "name": "Xbox Game Bar", "desc": "Overlay de jogos Xbox"},
    {"pattern": "Microsoft.GetHelp", "name": "Obter Ajuda (Get Help)", "desc": "Assistente de suporte da Microsoft"},
    {"pattern": "Microsoft.Getstarted", "name": "Dicas do Windows (Tips)", "desc": "Sugestões e tutoriais do sistema"},
    {"pattern": "Microsoft.MicrosoftSolitaireCollection", "name": "Microsoft Solitaire Collection", "desc": "Jogos de paciência pré-instalados"},
    {"pattern": "Microsoft.MicrosoftStickyNotes", "name": "Notas Autoadesivas (Sticky Notes)", "desc": "Lembretes na área de trabalho"},
    {"pattern": "Microsoft.MixedReality.Portal", "name": "Portal de Realidade Misturada", "desc": "Componentes de VR/Realidade Mista"},
    {"pattern": "Microsoft.People", "name": "Microsoft Pessoas (People)", "desc": "Integração de contatos na barra de tarefas"},
    {"pattern": "Microsoft.PowerAutomateDesktop", "name": "Power Automate Desktop", "desc": "Automação corporativa pré-instalada"},
    {"pattern": "Microsoft.Todos", "name": "Microsoft To Do", "desc": "Gerenciador de listas de tarefas"},
    {"pattern": "Microsoft.WindowsAlarms", "name": "Relógio e Alarmes do Windows", "desc": "Temporizador e alarmes"},
    {"pattern": "Microsoft.WindowsFeedbackHub", "name": "Hub de Feedback", "desc": "Envio de opiniões e telemetria para a Microsoft"},
    {"pattern": "Microsoft.WindowsMaps", "name": "Mapas do Windows", "desc": "Visualizador de mapas offline/Bing"},
    {"pattern": "Microsoft.WindowsSoundRecorder", "name": "Gravador de Voz", "desc": "Gravador de áudio simples"},
    {"pattern": "Microsoft.YourPhone", "name": "Vincular ao Celular (Phone Link)", "desc": "Sincronização com smartphone"},
    {"pattern": "Microsoft.ZuneVideo", "name": "Filmes e TV", "desc": "Reprodutor e loja de vídeos"},
    {"pattern": "Microsoft.Microsoft3DViewer", "name": "Visualizador 3D", "desc": "Visualizador de objetos 3D"},
    {"pattern": "Microsoft.SkypeApp", "name": "Skype", "desc": "Comunicador de voz e vídeo"},
    {"pattern": "MicrosoftTeams", "name": "Microsoft Teams (Pessoal)", "desc": "Cliente de chat integrado ao Windows 11"},
    {"pattern": "Microsoft.OutlookForWindows", "name": "Novo Outlook para Windows", "desc": "Cliente de e-mail web empacotado"},
]


def check_privacy_item_status(item: Dict[str, Any]) -> bool:
    """Verifica se a proteção de privacidade está ativa (True = Protegido/Desativada telemetria)."""
    try:
        with winreg.OpenKey(item["root"], item["key_path"], 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, item["value_name"])
            return val == item["disabled_val"]
    except Exception:
        return False


def get_all_privacy_statuses(filter_by_os: bool = False) -> List[Dict[str, Any]]:
    """
    Retorna a lista de opções de privacidade com o status atual.
    Se filter_by_os=True, retorna apenas os itens compatíveis com a versão do Windows detectada.
    """
    os_info = detect_windows_os_version()
    current_os = os_info["os_tag"]
    statuses = []
    for item in PRIVACY_ITEMS:
        supported = item.get("supported_os", ["win10", "win11"])
        if filter_by_os and current_os not in supported:
            continue
        is_protected = check_privacy_item_status(item)
        statuses.append({
            "id": item["id"],
            "category": item.get("category", "Geral"),
            "name": item["name"],
            "desc": item["desc"],
            "is_protected": is_protected,
            "supported_os": supported,
            "requires_admin": item.get("requires_admin", False),
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
        with winreg.CreateKeyEx(target_item["root"], target_item["key_path"], 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, target_item["value_name"], 0, winreg.REG_DWORD, val_to_set)
        return True, f"'{target_item['name']}' atualizado com sucesso."
    except PermissionError:
        return False, f"Requer privilégios de Administrador para modificar '{target_item['name']}'."
    except Exception as exc:
        return False, f"Falha ao alterar registro: {exc}"


def list_installed_bloatware_apps() -> List[Dict[str, Any]]:
    """
    Consulta quais pacotes Appx do catálogo de bloatware (Win11Debloat) estão instalados no usuário/sistema.
    """
    ps_cmd = "Get-AppxPackage | Select-Object Name, PackageFullName | ConvertTo-Json -Compress"
    installed_names: Dict[str, str] = {}
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
            timeout=25,
        )
        stdout = proc.stdout.strip()
        if stdout:
            data = json.loads(stdout)
            pkg_list = [data] if isinstance(data, dict) else data
            for p in pkg_list:
                n = str(p.get("Name") or "").strip()
                fn = str(p.get("PackageFullName") or "").strip()
                if n:
                    installed_names[n.lower()] = fn
    except Exception as exc:
        _log.warning("Falha ao listar pacotes Appx: %s", exc)

    results: List[Dict[str, Any]] = []
    for entry in BLOATWARE_APPX_CATALOG:
        pat = entry["pattern"].lower()
        matched_full = ""
        for inst_name, full_name in installed_names.items():
            if pat in inst_name:
                matched_full = full_name
                break
        results.append({
            "pattern": entry["pattern"],
            "name": entry["name"],
            "desc": entry["desc"],
            "is_installed": bool(matched_full),
            "status_label": "Instalado" if matched_full else "Não instalado / Já removido",
            "package_full_name": matched_full,
        })
    return results


def remove_bloatware_packages(patterns: List[str]) -> Tuple[bool, str, int]:
    """
    Remove em lote os pacotes Appx correspondentes aos padrões selecionados.
    """
    if not patterns:
        return False, "Nenhum aplicativo selecionado para remoção.", 0

    removed = 0
    errors: List[str] = []
    for pat in patterns:
        safe_pat = pat.replace("'", "").strip()
        if not safe_pat:
            continue
        ps_cmd = f"Get-AppxPackage '*{safe_pat}*' | Remove-AppxPackage -ErrorAction Stop"
        try:
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
                timeout=45,
            )
            if proc.returncode == 0:
                removed += 1
            else:
                errors.append(f"{safe_pat}: {proc.stderr.strip() or 'Falha ao remover'}")
        except Exception as e:
            errors.append(f"{safe_pat}: {e}")

    if removed > 0 and not errors:
        return True, f"{removed} aplicativo(s) nativo(s) (bloatware) removido(s) com sucesso!", removed
    elif removed > 0 and errors:
        return True, f"{removed} removido(s), mas {len(errors)} apresentaram falha:\n" + "\n".join(errors[:3]), removed
    else:
        return False, "Não foi possível remover os pacotes selecionados:\n" + "\n".join(errors[:3]), 0
