"""
Verificação e elevação de privilégios de Administrador (UAC) no Windows.
"""
import sys
import ctypes
from pathlib import Path

def is_admin() -> bool:
    """Verifica se o processo atual possui privilégios de administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def request_elevation(extra_args: str = "") -> bool:
    """
    Solicita elevação UAC para reiniciar o processo atual como Administrador.
    Preserva aspas em caminhos com espaços.
    """
    if is_admin():
        return True

    try:
        executable = sys.executable
        # Monta a linha de comando garantindo aspas
        script = Path(sys.argv[0]).resolve()
        params = f'"{script}" {extra_args}'.strip()

        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            params,
            None,
            1  # SW_SHOWNORMAL
        )
        if ret > 32:
            sys.exit(0)
        return False
    except Exception:
        return False
