"""
Lógica pura para gerenciamento e criação de planos de energia e agendamento de desligamento do Windows.
Isolada de interface gráfica.
"""
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple
import psutil

from wintoolbox.core.shell import CONSOLE_ENCODING, CREATE_NO_WINDOW

BUILTIN_PLAN_GUIDS = {
    "381b4222-f694-41f0-9685-ff5bb260df2e",  # Equilibrado
    "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",  # Alto desempenho
    "a1841308-3541-4fab-bc81-f71556f20b4a",  # Economia de energia
}

ULTIMATE_PERFORMANCE_GUID = "e9a42b02-d5df-448d-aa00-03f14749eb61"


def get_power_plans() -> List[Dict[str, Any]]:
    """
    Lista todos os esquemas/planos de energia disponíveis no Windows e indica qual está ativo.
    """
    plans: List[Dict[str, Any]] = []
    try:
        res = subprocess.run(
            ["powercfg", "/list"],
            capture_output=True, text=True, encoding=CONSOLE_ENCODING,
            errors="replace", timeout=10, creationflags=CREATE_NO_WINDOW
        )
        if res.returncode == 0:
            lines = res.stdout.splitlines()
            guid_pattern = r"([0-9a-fA-F\-]{36})\s+\((.*?)\)(\s*\*?)"
            for line in lines:
                m = re.search(guid_pattern, line)
                if m:
                    guid = m.group(1).lower()
                    name = m.group(2)
                    is_active = "*" in line
                    plans.append({
                        "guid": guid,
                        "name": name,
                        "is_active": is_active,
                        "is_builtin": guid in BUILTIN_PLAN_GUIDS,
                    })
    except Exception:
        pass

    return plans


def set_active_power_plan(plan_guid: str) -> Tuple[bool, str]:
    """
    Define o plano de energia ativo pelo GUID via 'powercfg /setactive'.
    """
    plan_guid = plan_guid.strip()
    if not plan_guid:
        return False, "GUID do plano inválido."

    try:
        res = subprocess.run(
            ["powercfg", "/setactive", plan_guid],
            capture_output=True, text=True, encoding=CONSOLE_ENCODING,
            errors="replace", timeout=10, creationflags=CREATE_NO_WINDOW
        )
        if res.returncode == 0:
            return True, "Plano de energia ativado com sucesso."
        return False, f"Falha ao alterar plano: {res.stderr or res.stdout}"
    except Exception as e:
        return False, f"Erro ao executar powercfg: {str(e)}"


def create_custom_power_plan(
    name: str,
    description: str = "",
    base_guid: str = "381b4222-f694-41f0-9685-ff5bb260df2e",
    monitor_ac_min: int = 15,
    monitor_dc_min: int = 5,
    standby_ac_min: int = 30,
    standby_dc_min: int = 15,
    activate: bool = True,
) -> Tuple[bool, str, Optional[str]]:
    """
    Cria um novo plano de energia clonando um plano base via 'powercfg /duplicatescheme',
    renomeia com 'powercfg /changename' e configura os tempos de vídeo/suspensão.
    Retorna (sucesso, mensagem, novo_guid).
    """
    clean_name = (name or "").strip()
    if not clean_name:
        return False, "Informe um nome para o novo plano de energia.", None

    clean_desc = (description or "").strip() or f"Plano personalizado criado pelo All the Utils ({clean_name})"
    base = (base_guid or "381b4222-f694-41f0-9685-ff5bb260df2e").strip()

    try:
        res = subprocess.run(
            ["powercfg", "/duplicatescheme", base],
            capture_output=True, text=True, encoding=CONSOLE_ENCODING,
            errors="replace", timeout=15, creationflags=CREATE_NO_WINDOW
        )
        if res.returncode != 0:
            return False, f"Falha ao duplicar esquema base: {res.stderr or res.stdout}", None

        m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", res.stdout)
        if not m:
            return False, "Não foi possível obter o GUID do novo plano criado.", None

        new_guid = m.group(1).lower()

        # Renomeia o plano recém-criado
        subprocess.run(
            ["powercfg", "/changename", new_guid, clean_name, clean_desc],
            capture_output=True, text=True, encoding=CONSOLE_ENCODING,
            errors="replace", timeout=10, creationflags=CREATE_NO_WINDOW
        )

        # Se devemos ativar ou ajustar timeouts (powercfg /change opera sobre o plano ativo)
        # Guardamos o plano anteriormente ativo caso activate=False
        prev_active = None
        if not activate:
            for p in get_power_plans():
                if p.get("is_active"):
                    prev_active = p["guid"]
                    break

        subprocess.run(["powercfg", "/setactive", new_guid], creationflags=CREATE_NO_WINDOW, timeout=10)

        timeouts = [
            ("monitor-timeout-ac", max(0, int(monitor_ac_min))),
            ("monitor-timeout-dc", max(0, int(monitor_dc_min))),
            ("standby-timeout-ac", max(0, int(standby_ac_min))),
            ("standby-timeout-dc", max(0, int(standby_dc_min))),
        ]
        for setting, minutes in timeouts:
            subprocess.run(
                ["powercfg", "/change", setting, str(minutes)],
                capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=10
            )

        if not activate and prev_active:
            subprocess.run(["powercfg", "/setactive", prev_active], creationflags=CREATE_NO_WINDOW, timeout=10)

        status_msg = "e definido como ativo" if activate else "com sucesso"
        return True, f"Plano '{clean_name}' criado {status_msg}!", new_guid
    except Exception as e:
        return False, f"Erro ao criar plano de energia: {str(e)}", None


def unlock_ultimate_performance_plan() -> Tuple[bool, str]:
    """Desbloqueia o plano oculto 'Desempenho Máximo' (Ultimate Performance) do Windows 10/11."""
    try:
        res = subprocess.run(
            ["powercfg", "-duplicatescheme", ULTIMATE_PERFORMANCE_GUID],
            capture_output=True, text=True, encoding=CONSOLE_ENCODING,
            errors="replace", timeout=15, creationflags=CREATE_NO_WINDOW
        )
        if res.returncode == 0:
            return True, "Plano 'Desempenho Máximo' (Ultimate Performance) desbloqueado e adicionado à lista!"
        return False, f"Falha ao desbloquear plano: {res.stderr or res.stdout}"
    except Exception as e:
        return False, f"Erro ao executar powercfg: {str(e)}"


def delete_power_plan(plan_guid: str) -> Tuple[bool, str]:
    """Exclui um plano de energia personalizado (impede exclusão de planos nativos ou do plano ativo)."""
    g = (plan_guid or "").strip().lower()
    if not g:
        return False, "GUID inválido."
    if g in BUILTIN_PLAN_GUIDS:
        return False, "Os planos padrões de fábrica do Windows não podem ser excluídos."

    plans = get_power_plans()
    for p in plans:
        if p["guid"].lower() == g and p.get("is_active"):
            return False, "Não é possível excluir o plano que está ativo no momento. Ative outro plano antes de excluir."

    try:
        res = subprocess.run(
            ["powercfg", "/delete", g],
            capture_output=True, text=True, encoding=CONSOLE_ENCODING,
            errors="replace", timeout=10, creationflags=CREATE_NO_WINDOW
        )
        if res.returncode == 0:
            return True, "Plano de energia personalizado excluído com sucesso."
        return False, f"Erro ao excluir plano: {res.stderr or res.stdout}"
    except Exception as e:
        return False, f"Erro ao executar powercfg: {str(e)}"


def schedule_system_action(action: str, delay_seconds: int) -> Tuple[bool, str]:
    """
    Agenda uma ação do sistema: 'shutdown', 'restart', 'sleep', 'lock'.
    """
    action = action.lower()
    try:
        if action == "shutdown":
            cmd = ["shutdown", "/s", "/t", str(max(0, delay_seconds))]
            subprocess.run(cmd, check=True, creationflags=CREATE_NO_WINDOW)
            mins = round(delay_seconds / 60, 1)
            return True, f"Desligamento agendado para daqui a {mins} minutos."

        elif action == "restart":
            cmd = ["shutdown", "/r", "/t", str(max(0, delay_seconds))]
            subprocess.run(cmd, check=True, creationflags=CREATE_NO_WINDOW)
            mins = round(delay_seconds / 60, 1)
            return True, f"Reinício agendado para daqui a {mins} minutos."

        elif action == "lock":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], creationflags=CREATE_NO_WINDOW)
            return True, "Estação de trabalho bloqueada com sucesso."

        elif action == "sleep":
            import ctypes
            if not ctypes.windll.powrprof.SetSuspendState(False, False, False):
                return False, "O Windows recusou a suspensão (verifique as políticas de energia)."
            return True, "Modo de suspensão ativado."

        return False, f"Ação desconhecida: {action}"
    except Exception as e:
        return False, f"Erro ao executar ação: {str(e)}"


def cancel_scheduled_shutdown() -> Tuple[bool, str]:
    """Cancela qualquer desligamento ou reinício previamente agendado no Windows."""
    try:
        res = subprocess.run(
            ["shutdown", "/a"],
            capture_output=True, text=True, encoding=CONSOLE_ENCODING,
            errors="replace", creationflags=CREATE_NO_WINDOW
        )
        if res.returncode == 0:
            return True, "Desligamento/reinício agendado cancelado com sucesso."
        return False, "Nenhum desligamento agendado estava ativo."
    except Exception as e:
        return False, f"Erro ao cancelar: {str(e)}"


def get_battery_info() -> Optional[Dict[str, Any]]:
    """Retorna o status da bateria do dispositivo caso exista."""
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return None

        secs = battery.secsleft
        time_left_str = "Calculando..."
        if secs == psutil.POWER_TIME_UNLIMITED:
            time_left_str = "Conectado à tomada (Carregando / Cheio)"
        elif secs == psutil.POWER_TIME_UNKNOWN:
            time_left_str = "Desconhecido"
        elif secs > 0:
            hrs = secs // 3600
            mins = (secs % 3600) // 60
            time_left_str = f"{hrs}h {mins}m restantes"

        return {
            "percent": round(battery.percent, 1),
            "power_plugged": battery.power_plugged,
            "time_left": time_left_str,
        }
    except Exception:
        return None
