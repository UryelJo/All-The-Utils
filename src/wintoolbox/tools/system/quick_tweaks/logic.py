"""
Lógica pura para Ajustes Rápidos do Windows (Windows Quick Tweaks).
Manipula chaves de Registro de interface do Explorer e personalização sem dependência de UI.
"""
import os
import subprocess
import time
from typing import Dict, Tuple
import winreg


def get_quick_tweaks_state() -> Dict[str, bool]:
    """
    Retorna o estado atual (booleano) de cada um dos ajustes rápidos do sistema.
    """
    states = {
        "show_hidden_files": False,
        "show_file_extensions": False,
        "dark_mode_apps": True,
        "dark_mode_system": True,
        "show_this_pc_desktop": False,
        "hide_quick_access_recent": False,
    }

    # 1. Arquivos Ocultos
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced") as k:
            val, _ = winreg.QueryValueEx(k, "Hidden")
            states["show_hidden_files"] = (val == 1)
    except Exception:
        pass

    # 2. Extensões de Arquivos
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced") as k:
            val, _ = winreg.QueryValueEx(k, "HideFileExt")
            states["show_file_extensions"] = (val == 0)
    except Exception:
        pass

    # 3 & 4. Tema Escuro (Apps e Sistema)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            try:
                val_apps, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
                states["dark_mode_apps"] = (val_apps == 0)
            except Exception:
                pass
            try:
                val_sys, _ = winreg.QueryValueEx(k, "SystemUsesLightTheme")
                states["dark_mode_system"] = (val_sys == 0)
            except Exception:
                pass
    except Exception:
        pass

    # 5. Ícone "Este Computador" na Área de Trabalho
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\HideDesktopIcons\NewStartPanel") as k:
            val, _ = winreg.QueryValueEx(k, "{20D04FE0-3AEA-1069-A2D8-08002B30309D}")
            states["show_this_pc_desktop"] = (val == 0)
    except Exception:
        pass

    # 6. Histórico de Acesso Rápido
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer") as k:
            val, _ = winreg.QueryValueEx(k, "ShowRecent")
            states["hide_quick_access_recent"] = (val == 0)
    except Exception:
        pass

    return states


def apply_quick_tweak(tweak_id: str, enabled: bool) -> Tuple[bool, str]:
    """
    Grava o estado de um ajuste específico no Registro do Windows.
    """
    try:
        if tweak_id == "show_hidden_files":
            val = 1 if enabled else 2
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced") as k:
                winreg.SetValueEx(k, "Hidden", 0, winreg.REG_DWORD, val)
            return True, "Configuração de arquivos ocultos atualizada."

        elif tweak_id == "show_file_extensions":
            val = 0 if enabled else 1
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced") as k:
                winreg.SetValueEx(k, "HideFileExt", 0, winreg.REG_DWORD, val)
            return True, "Configuração de extensões de arquivos atualizada."

        elif tweak_id == "dark_mode_apps":
            val = 0 if enabled else 1
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                winreg.SetValueEx(k, "AppsUseLightTheme", 0, winreg.REG_DWORD, val)
            return True, "Tema escuro de aplicativos atualizado."

        elif tweak_id == "dark_mode_system":
            val = 0 if enabled else 1
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                winreg.SetValueEx(k, "SystemUsesLightTheme", 0, winreg.REG_DWORD, val)
            return True, "Tema escuro do sistema operacional atualizado."

        elif tweak_id == "show_this_pc_desktop":
            val = 0 if enabled else 1
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\HideDesktopIcons\NewStartPanel") as k:
                winreg.SetValueEx(k, "{20D04FE0-3AEA-1069-A2D8-08002B30309D}", 0, winreg.REG_DWORD, val)
            return True, "Visibilidade do 'Este Computador' atualizada."

        elif tweak_id == "hide_quick_access_recent":
            val = 0 if enabled else 1
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer") as k:
                winreg.SetValueEx(k, "ShowRecent", 0, winreg.REG_DWORD, val)
            return True, "Histórico do Acesso Rápido atualizado."

        return False, f"Ajuste desconhecido: {tweak_id}"
    except Exception as e:
        return False, f"Erro ao aplicar ajuste: {str(e)}"


def restart_windows_explorer() -> Tuple[bool, str]:
    """
    Reinicia o processo do Windows Explorer para que alterações visuais entrem em vigor imediatamente.
    """
    try:
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], capture_output=True, timeout=5)
        time.sleep(1)
        subprocess.Popen("explorer.exe")
        return True, "Windows Explorer reiniciado com sucesso."
    except Exception as e:
        return False, f"Falha ao reiniciar o Explorer: {str(e)}"
