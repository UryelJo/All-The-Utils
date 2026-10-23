"""
Lógica pura para listagem e desinstalação de programas instalados no Windows via Registro.
Isolada de interface gráfica.
"""
import subprocess
from typing import Any, Dict, List, Tuple
import winreg


UNINSTALL_ROOTS = [
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "Sistema (64-bit)"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall", "Sistema (32-bit)"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", "Usuário"),
]


def list_installed_programs(filter_text: str = "") -> List[Dict[str, Any]]:
    """
    Varre as chaves de desinstalação do Windows e retorna a lista de programas instalados.
    """
    filter_norm = filter_text.strip().lower()
    programs: List[Dict[str, Any]] = []
    seen_names = set()

    for root, subkey, arch in UNINSTALL_ROOTS:
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as main_key:
                num_subkeys = winreg.QueryInfoKey(main_key)[0]
                for i in range(num_subkeys):
                    try:
                        app_guid = winreg.EnumKey(main_key, i)
                        with winreg.OpenKey(main_key, app_guid, 0, winreg.KEY_READ) as app_key:
                            def _val(val_name):
                                try:
                                    v, _ = winreg.QueryValueEx(app_key, val_name)
                                    return str(v)
                                except Exception:
                                    return ""

                            # Ignora atualizações do Windows e componentes de sistema
                            is_system = _val("SystemComponent")
                            parent_key = _val("ParentKeyName")
                            if is_system == "1" or parent_key:
                                continue

                            display_name = _val("DisplayName").strip()
                            if not display_name:
                                continue

                            # Evita duplicatas idênticas entre raízes
                            dedup_key = (display_name.lower(), _val("DisplayVersion"))
                            if dedup_key in seen_names:
                                continue
                            seen_names.add(dedup_key)

                            publisher = _val("Publisher")
                            version = _val("DisplayVersion")
                            install_date = _val("InstallDate")
                            uninstall_str = _val("UninstallString")
                            quiet_uninstall_str = _val("QuietUninstallString")

                            # Tamanho estimado em KB para MB
                            raw_size = _val("EstimatedSize")
                            size_mb = 0.0
                            if raw_size and raw_size.isdigit():
                                size_mb = round(int(raw_size) / 1024, 1)

                            # Filtro de texto
                            if filter_norm:
                                if filter_norm not in display_name.lower() and filter_norm not in publisher.lower():
                                    continue

                            programs.append({
                                "name": display_name,
                                "version": version or "-",
                                "publisher": publisher or "-",
                                "install_date": install_date or "-",
                                "size_mb": size_mb,
                                "uninstall_string": uninstall_str,
                                "quiet_uninstall_string": quiet_uninstall_str,
                                "arch": arch,
                                "key_id": app_guid,
                            })
                    except Exception:
                        continue
        except Exception:
            pass

    programs.sort(key=lambda p: p["name"].lower())
    return programs


def run_uninstaller(uninstall_cmd: str) -> Tuple[bool, str]:
    """
    Dispara o desinstalador associado ao aplicativo de forma desanexada.
    """
    cmd = uninstall_cmd.strip()
    if not cmd:
        return False, "Comando de desinstalação não disponível para este aplicativo."

    try:
        # Se for msiexec com /I ou /X, executa normalmente
        subprocess.Popen(cmd, shell=True)
        return True, "Assistente de desinstalação iniciado com sucesso."
    except Exception as e:
        return False, f"Falha ao executar desinstalador: {str(e)}"
