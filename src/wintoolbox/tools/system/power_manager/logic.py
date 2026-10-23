"""
Lógica pura para gerenciamento de planos de energia e agendamento de desligamento do Windows.
Isolada de interface gráfica.
"""
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple
import psutil

from wintoolbox.core.shell import CONSOLE_ENCODING, CREATE_NO_WINDOW


def get_power_plans() -> List[Dict[str, Any]]:
    """
    Lista todos os esquemas/planos de energia disponíveis no Windows e indica qual está ativo.
    """
    plans: List[Dict[str, Any]] = []
    try:
        res = subprocess.run(["powercfg", "/list"], capture_output=True, text=True, encoding=CONSOLE_ENCODING, errors="replace", timeout=10, creationflags=CREATE_NO_WINDOW)
        if res.returncode == 0:
            lines = res.stdout.splitlines()
            # Padrão: GUID do Esquema de Energia: 381b4222-f694-41f0-9685-ff5bb260df2e  (Equilibrado) *
            # ou Power Scheme GUID: 381b4222-... (Balanced) *
            guid_pattern = r"([0-9a-fA-F\-]{36})\s+\((.*?)\)(\s*\*?)"
            for line in lines:
                m = re.search(guid_pattern, line)
                if m:
                    guid = m.group(1)
                    name = m.group(2)
                    is_active = "*" in line
                    plans.append({
                        "guid": guid,
                        "name": name,
                        "is_active": is_active,
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
        res = subprocess.run(["powercfg", "/setactive", plan_guid], capture_output=True, text=True, encoding=CONSOLE_ENCODING, errors="replace", timeout=10, creationflags=CREATE_NO_WINDOW)
        if res.returncode == 0:
            return True, "Plano de energia ativado com sucesso."
        return False, f"Falha ao alterar plano: {res.stderr or res.stdout}"
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
            # rundll32 não repassa os argumentos de SetSuspendState e o PC hiberna quando a
            # hibernação/Inicialização Rápida está ativa; a chamada direta garante suspensão (S3)
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
        res = subprocess.run(["shutdown", "/a"], capture_output=True, text=True, encoding=CONSOLE_ENCODING, errors="replace", creationflags=CREATE_NO_WINDOW)
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
