"""
Lógica pura do Gerenciador de Inicialização do Windows.
Lê e gerencia programas na pasta de Inicialização e no Registro (HKCU / HKLM).
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple
import winreg


REG_RUN_PATHS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "Registro (Usuário Atual)"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "Registro (Todos os Usuários)"),
]

REG_DISABLED_PATHS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run", "Registro (Usuário)"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run", "Registro (Sistema)"),
]


def list_startup_items() -> List[Dict[str, Any]]:
    """
    Retorna todos os itens configurados para iniciar com o Windows.
    """
    items: List[Dict[str, Any]] = []

    # 1. Registro do Windows (Run)
    for root, subkey, loc_name in REG_RUN_PATHS:
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as key:
                num_vals = winreg.QueryInfoKey(key)[1]
                for i in range(num_vals):
                    try:
                        name, val, val_type = winreg.EnumValue(key, i)
                        items.append({
                            "name": name,
                            "command": str(val),
                            "location": loc_name,
                            "type": "registry",
                            "root": "HKCU" if root == winreg.HKEY_CURRENT_USER else "HKLM",
                            "subkey": subkey,
                            "is_enabled": True,
                        })
                    except Exception:
                        continue
        except Exception:
            pass

    # 2. Pasta Inicializar do Usuário
    user_startup = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))
    if user_startup.exists():
        for p in user_startup.iterdir():
            if p.is_file() and not p.name.lower().startswith("desktop.ini"):
                items.append({
                    "name": p.stem,
                    "command": str(p),
                    "location": "Pasta Inicializar (Usuário)",
                    "type": "folder",
                    "file_path": str(p),
                    "is_enabled": True,
                })

    # 3. Pasta Inicializar de Todos os Usuários
    common_startup = Path(os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))
    if common_startup.exists():
        for p in common_startup.iterdir():
            if p.is_file() and not p.name.lower().startswith("desktop.ini"):
                items.append({
                    "name": p.stem,
                    "command": str(p),
                    "location": "Pasta Inicializar (Sistema)",
                    "type": "folder",
                    "file_path": str(p),
                    "is_enabled": True,
                })

    return items


def remove_startup_item(item: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Remove uma entrada de inicialização do Registro ou apaga o atalho da pasta.
    """
    try:
        item_type = item.get("type")
        if item_type == "registry":
            root_code = item.get("root")
            root = winreg.HKEY_CURRENT_USER if root_code == "HKCU" else winreg.HKEY_LOCAL_MACHINE
            subkey = item.get("subkey", r"Software\Microsoft\Windows\CurrentVersion\Run")
            name = item.get("name", "")

            with winreg.OpenKey(root, subkey, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
            return True, f"Entrada '{name}' removida do registro com sucesso."

        elif item_type == "folder":
            f_path = Path(item.get("file_path", ""))
            if f_path.exists():
                f_path.unlink()
                return True, f"Atalho '{f_path.name}' removido da pasta de inicialização."
            return False, "Arquivo não encontrado."

        return False, "Tipo de item não suportado."
    except PermissionError:
        return False, "Permissão insuficiente para remover este item. Execute como Administrador."
    except Exception as e:
        return False, f"Erro ao remover: {str(e)}"


def add_registry_startup_item(name: str, executable_path: str, all_users: bool = False) -> Tuple[bool, str]:
    """
    Adiciona um novo programa à inicialização do Windows via Registro.
    """
    name = name.strip()
    executable_path = executable_path.strip()
    if not name or not executable_path:
        return False, "Nome e comando/caminho são obrigatórios."

    root = winreg.HKEY_LOCAL_MACHINE if all_users else winreg.HKEY_CURRENT_USER
    subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"

    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_SET_VALUE) as key:
            # Envolve em aspas se contiver espaços
            clean_cmd = f'"{executable_path}"' if " " in executable_path and not executable_path.startswith('"') else executable_path
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, clean_cmd)
        return True, f"'{name}' adicionado à inicialização com sucesso."
    except PermissionError:
        return False, "Permissão negada. Para gravar em 'Todos os Usuários' execute como Administrador."
    except Exception as e:
        return False, f"Erro ao adicionar ao registro: {str(e)}"
