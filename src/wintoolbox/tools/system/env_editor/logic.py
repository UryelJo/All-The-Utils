"""
Lógica pura para leitura e edição de variáveis de ambiente do Windows (Usuário e Sistema).
Inclui suporte especializado para a variável PATH e notificação broadcast via WM_SETTINGCHANGE.
"""
import ctypes
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple
import winreg


REG_USER_ENV = (winreg.HKEY_CURRENT_USER, r"Environment")
REG_SYSTEM_ENV = (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")

HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x001A
SMTO_ABORTIFHUNG = 0x0002


def notify_system_environment_change():
    """
    Notifica todas as janelas do sistema operacional sobre a alteração das variáveis de ambiente.
    Evita a necessidade de reiniciar o computador ou deslogar na maioria dos casos.
    """
    try:
        user32 = ctypes.windll.user32
        result = ctypes.c_ulong()
        user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            5000,
            ctypes.byref(result)
        )
    except Exception:
        pass


def get_environment_variables(scope: str = "user") -> Dict[str, str]:
    """
    Retorna um dicionário com todas as variáveis de ambiente do escopo ('user' ou 'system').
    """
    root, subkey = REG_USER_ENV if scope == "user" else REG_SYSTEM_ENV
    variables: Dict[str, str] = {}

    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as key:
            num_vals = winreg.QueryInfoKey(key)[1]
            for i in range(num_vals):
                try:
                    name, val, _ = winreg.EnumValue(key, i)
                    variables[name] = str(val)
                except Exception:
                    continue
    except Exception:
        pass

    return variables


def set_environment_variable(name: str, value: str, scope: str = "user") -> Tuple[bool, str]:
    """
    Cria ou atualiza uma variável de ambiente no Registro e faz o broadcast da mudança.
    """
    name = name.strip()
    if not name:
        return False, "O nome da variável não pode ser vazio."

    root, subkey = REG_USER_ENV if scope == "user" else REG_SYSTEM_ENV
    val_type = winreg.REG_EXPAND_SZ if "%" in value else winreg.REG_SZ

    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, val_type, value)
        notify_system_environment_change()
        return True, f"Variável '{name}' salva com sucesso no escopo {scope}."
    except PermissionError:
        return False, "Permissão negada. Para alterar variáveis do Sistema é necessário privilégio de Administrador."
    except Exception as e:
        return False, f"Erro ao salvar variável: {str(e)}"


def delete_environment_variable(name: str, scope: str = "user") -> Tuple[bool, str]:
    """
    Remove uma variável de ambiente do Registro.
    """
    name = name.strip()
    root, subkey = REG_USER_ENV if scope == "user" else REG_SYSTEM_ENV

    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
        notify_system_environment_change()
        return True, f"Variável '{name}' excluída com sucesso."
    except FileNotFoundError:
        return False, "Variável não encontrada."
    except PermissionError:
        return False, "Permissão negada ao excluir variável de sistema."
    except Exception as e:
        return False, f"Erro ao remover: {str(e)}"


def get_path_entries(scope: str = "user") -> List[Dict[str, Any]]:
    """
    Lê a variável PATH do escopo fornecido, separando em entradas individuais com status de existência.
    """
    vars_dict = get_environment_variables(scope)
    # Procura 'Path' ou 'PATH'
    raw_path = ""
    for k, v in vars_dict.items():
        if k.upper() == "PATH":
            raw_path = v
            break

    entries: List[Dict[str, Any]] = []
    if not raw_path:
        return entries

    for part in raw_path.split(";"):
        p_str = part.strip()
        if not p_str:
            continue
        expanded = os.path.expandvars(p_str)
        exists = os.path.exists(expanded)
        entries.append({
            "raw_path": p_str,
            "expanded_path": expanded,
            "exists": exists,
        })

    return entries


def save_path_entries(entries: List[str], scope: str = "user") -> Tuple[bool, str]:
    """
    Recompõe a lista de caminhos em string separada por ponto-e-vírgula e salva no PATH.
    """
    clean_entries = [p.strip() for p in entries if p.strip()]
    joined_path = ";".join(clean_entries)

    vars_dict = get_environment_variables(scope)
    path_key_name = "Path"
    for k in vars_dict.keys():
        if k.upper() == "PATH":
            path_key_name = k
            break

    return set_environment_variable(path_key_name, joined_path, scope=scope)
