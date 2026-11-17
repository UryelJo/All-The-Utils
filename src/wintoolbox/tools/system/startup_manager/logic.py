"""
Lógica pura do Gerenciador de Inicialização do Windows.
Lê e gerencia programas na pasta de Inicialização e no Registro (HKCU / HKLM),
incluindo leitura e escrita do estado Ativo/Desativado em StartupApproved.
"""
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple
import winreg


REG_RUN_PATHS = [
    (
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run",
        "Registro (Usuário Atual)",
        "HKCU",
    ),
    (
        winreg.HKEY_LOCAL_MACHINE,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run",
        "Registro (Todos os Usuários)",
        "HKLM",
    ),
    (
        winreg.HKEY_LOCAL_MACHINE,
        r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32",
        "Registro 32-bit (Sistema)",
        "HKLM",
    ),
]


def extract_exe_from_command(cmd: str) -> str:
    """Extrai o caminho do arquivo executável ou atalho a partir do comando de inicialização."""
    s = os.path.expandvars((cmd or "").strip())
    if not s:
        return ""
    if s.startswith('"'):
        idx = s.find('"', 1)
        if idx > 1:
            return s[1:idx]
    m = re.match(r"^([a-zA-Z]:\\[^\r\n]*?\.(?:exe|lnk|bat|cmd))\b", s, re.IGNORECASE)
    if m:
        return m.group(1)
    return s.split()[0].strip('"') if s else ""


def _read_approved_map(root: int, approved_subkey: str) -> Dict[str, bool]:
    """
    Lê a chave StartupApproved do Windows.
    O primeiro byte par (ex: 0x02, 0x06) significa Habilitado (True).
    O primeiro byte ímpar (ex: 0x03, 0x01) significa Desabilitado pelo usuário (False).
    """
    status_map: Dict[str, bool] = {}
    try:
        with winreg.OpenKey(root, approved_subkey, 0, winreg.KEY_READ) as key:
            num_vals = winreg.QueryInfoKey(key)[1]
            for i in range(num_vals):
                try:
                    name, val, _ = winreg.EnumValue(key, i)
                    if isinstance(val, (bytes, bytearray)) and len(val) >= 1:
                        status_map[name] = (val[0] % 2 == 0)
                except Exception:
                    continue
    except Exception:
        pass
    return status_map


def list_startup_items() -> List[Dict[str, Any]]:
    """
    Retorna todos os itens configurados para iniciar com o Windows, incluindo se estão Ativos ou Desativados.
    """
    items: List[Dict[str, Any]] = []

    # 1. Registro do Windows (Run)
    for root, subkey, approved_subkey, loc_name, root_code in REG_RUN_PATHS:
        approved = _read_approved_map(root, approved_subkey)
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as key:
                num_vals = winreg.QueryInfoKey(key)[1]
                for i in range(num_vals):
                    try:
                        name, val, _ = winreg.EnumValue(key, i)
                        cmd_str = str(val)
                        is_enabled = approved.get(name, True)
                        uid = f"reg|{root_code}|{subkey}|{name}"
                        items.append({
                            "uid": uid,
                            "name": name,
                            "command": cmd_str,
                            "exe_path": extract_exe_from_command(cmd_str),
                            "location": loc_name,
                            "type": "registry",
                            "root": root_code,
                            "subkey": subkey,
                            "approved_subkey": approved_subkey,
                            "approved_name": name,
                            "is_enabled": is_enabled,
                            "status_label": "Ativo" if is_enabled else "Desativado",
                        })
                    except Exception:
                        continue
        except Exception:
            pass

    # 2. Pasta Inicializar do Usuário
    user_startup = Path(os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))
    user_approved_subkey = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"
    user_approved = _read_approved_map(winreg.HKEY_CURRENT_USER, user_approved_subkey)
    if user_startup.exists():
        for p in user_startup.iterdir():
            if p.is_file() and not p.name.lower().startswith("desktop.ini"):
                is_enabled = user_approved.get(p.name, True)
                items.append({
                    "uid": f"folder|HKCU|{p}",
                    "name": p.stem,
                    "command": str(p),
                    "exe_path": str(p),
                    "location": "Pasta Inicializar (Usuário)",
                    "type": "folder",
                    "root": "HKCU",
                    "file_path": str(p),
                    "approved_subkey": user_approved_subkey,
                    "approved_name": p.name,
                    "is_enabled": is_enabled,
                    "status_label": "Ativo" if is_enabled else "Desativado",
                })

    # 3. Pasta Inicializar de Todos os Usuários
    common_startup = Path(os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\Startup"))
    common_approved_subkey = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"
    common_approved = _read_approved_map(winreg.HKEY_LOCAL_MACHINE, common_approved_subkey)
    if common_startup.exists():
        for p in common_startup.iterdir():
            if p.is_file() and not p.name.lower().startswith("desktop.ini"):
                is_enabled = common_approved.get(p.name, True)
                items.append({
                    "uid": f"folder|HKLM|{p}",
                    "name": p.stem,
                    "command": str(p),
                    "exe_path": str(p),
                    "location": "Pasta Inicializar (Sistema)",
                    "type": "folder",
                    "root": "HKLM",
                    "file_path": str(p),
                    "approved_subkey": common_approved_subkey,
                    "approved_name": p.name,
                    "is_enabled": is_enabled,
                    "status_label": "Ativo" if is_enabled else "Desativado",
                })

    return items


def set_startup_item_enabled(item: Dict[str, Any], enabled: bool) -> Tuple[bool, str]:
    """
    Ativa ou desativa um programa de inicialização gravando em StartupApproved
    (mesmo padrão utilizado pelo Gerenciador de Tarefas do Windows).
    """
    root_code = item.get("root", "HKCU")
    root = winreg.HKEY_CURRENT_USER if root_code == "HKCU" else winreg.HKEY_LOCAL_MACHINE
    approved_subkey = item.get(
        "approved_subkey",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run",
    )
    approved_name = item.get("approved_name") or item.get("name", "")
    if not approved_name:
        return False, "Item inválido para alteração de status."

    # 12 bytes padrão do StartupApproved: 0x02 = Ativo, 0x03 = Desativado
    payload = b"\x02" + (b"\x00" * 11) if enabled else b"\x03" + (b"\x00" * 11)
    try:
        with winreg.CreateKeyEx(root, approved_subkey, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, approved_name, 0, winreg.REG_BINARY, payload)
        state_str = "ativado" if enabled else "desativado"
        return True, f"'{item.get('name', approved_name)}' foi {state_str} na inicialização."
    except PermissionError:
        return False, f"Permissão negada ao alterar '{item.get('name')}'. Execute como Administrador."
    except Exception as e:
        return False, f"Erro ao alterar status de '{item.get('name')}': {str(e)}"


def set_multiple_startup_items_enabled(items: List[Dict[str, Any]], enabled: bool) -> Tuple[bool, str]:
    """Ativa ou desativa vários itens de inicialização em lote."""
    if not items:
        return False, "Nenhum item selecionado."
    if len(items) == 1:
        return set_startup_item_enabled(items[0], enabled)

    ok_count = 0
    errors: List[str] = []
    for it in items:
        ok, msg = set_startup_item_enabled(it, enabled)
        if ok:
            ok_count += 1
        else:
            errors.append(msg)

    action_word = "ativado(s)" if enabled else "desativado(s)"
    if ok_count > 0 and not errors:
        return True, f"{ok_count} programa(s) {action_word} com sucesso."
    elif ok_count > 0 and errors:
        return True, f"{ok_count} {action_word}, mas {len(errors)} falharam:\n" + "\n".join(errors[:4])
    else:
        return False, "Não foi possível alterar os itens selecionados:\n" + "\n".join(errors[:4])


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
            clean_cmd = f'"{executable_path}"' if " " in executable_path and not executable_path.startswith('"') else executable_path
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, clean_cmd)
        return True, f"'{name}' adicionado à inicialização com sucesso."
    except PermissionError:
        return False, "Permissão negada. Para gravar em 'Todos os Usuários' execute como Administrador."
    except Exception as e:
        return False, f"Erro ao adicionar ao registro: {str(e)}"
