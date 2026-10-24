"""
Lógica pura de restauração do Menu de Contexto Clássico do Windows 11 e gestão de entradas do Explorer.
Opera na colmeia HKCU do usuário sem necessitar de privilégios de administrador.
Totalmente desacoplada de bibliotecas de interface visual.
"""
import subprocess
import time
from typing import Tuple
import winreg

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.context_menu")

CLSID_KEY_PATH = r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"


def is_classic_context_menu_enabled() -> bool:
    """Verifica se o Menu de Contexto Clássico (Windows 10) está ativado no Windows 11."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLSID_KEY_PATH, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, "")
            return val == ""
    except Exception:
        return False


def set_classic_context_menu(enable: bool) -> Tuple[bool, str]:
    """Ativa ou desativa o Menu de Contexto Clássico."""
    if enable:
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, CLSID_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "")
            return True, "Menu de contexto clássico ativado no Registro."
        except Exception as exc:
            return False, f"Falha ao gravar no Registro: {exc}"
    else:
        try:
            # Apaga a chave InprocServer32 e depois a chave pai {86ca1aa0-...}
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, CLSID_KEY_PATH)
            parent_path = r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, parent_path)
            return True, "Menu de contexto moderno do Windows 11 restaurado."
        except FileNotFoundError:
            return True, "Menu moderno já é o padrão."
        except Exception as exc:
            return False, f"Falha ao remover chave de registro: {exc}"


def restart_explorer() -> Tuple[bool, str]:
    """Finaliza e reinicia o processo Windows Explorer para aplicar as alterações de menu."""
    try:
        subprocess.run(
            ["taskkill", "/f", "/im", "explorer.exe"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )
        time.sleep(1)
        subprocess.Popen("explorer.exe")
        return True, "Windows Explorer reiniciado com sucesso."
    except Exception as exc:
        return False, f"Erro ao reiniciar Explorer: {exc}"
