"""
Integração com o Menu de Contexto do Windows (Enviar Para / SendTo).
Permite selecionar arquivos/pastas no Windows Explorer e enviá-los ao WinToolbox.
"""
import os
import sys
from pathlib import Path

def get_sendto_dir() -> Path:
    """Retorna o caminho da pasta SendTo do usuário no Windows."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        p = Path(appdata) / "Microsoft" / "Windows" / "SendTo"
        if p.exists():
            return p
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "SendTo"

def get_sendto_shortcut_path() -> Path:
    return get_sendto_dir() / "WinToolbox.cmd"

def is_sendto_installed() -> bool:
    """Verifica se o atalho na pasta 'Enviar para' está presente."""
    return get_sendto_shortcut_path().exists()

def install_sendto() -> bool:
    """
    Cria um script wrapper .cmd no diretório SendTo do usuário.
    Não requer privilégios de Administrador pois atua no perfil do usuário atual.
    """
    try:
        sendto_dir = get_sendto_dir()
        sendto_dir.mkdir(parents=True, exist_ok=True)
        shortcut_file = get_sendto_shortcut_path()

        python_exe = sys.executable
        # Localiza o main.py na raiz do repositório
        main_script = Path(__file__).resolve().parent.parent.parent.parent / "main.py"

        cmd_content = f'@echo off\nstart "" "{python_exe}" "{main_script}" %*\n'
        with open(shortcut_file, "w", encoding="utf-8") as fp:
            fp.write(cmd_content)
        return True
    except Exception:
        return False

def uninstall_sendto() -> bool:
    """Remove o atalho da pasta 'Enviar para'."""
    try:
        shortcut_file = get_sendto_shortcut_path()
        if shortcut_file.exists():
            shortcut_file.unlink()
        return True
    except Exception:
        return False
