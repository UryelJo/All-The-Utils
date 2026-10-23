"""
Lógica pura de geração de comandos e automação para PyInstaller.
Isolada de interface gráfica e acoplamento direto com a UI.
"""
from pathlib import Path
import shutil
import sys
from typing import Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("dev.pyinstaller_wrapper")


def check_pyinstaller_available() -> Tuple[bool, str]:
    """Verifica se o PyInstaller está disponível no ambiente Python atual ou no PATH."""
    try:
        import PyInstaller
        version = getattr(PyInstaller, "__version__", "desconhecida")
        return True, f"PyInstaller v{version} instalado no ambiente Python ({sys.executable})."
    except ImportError:
        which_path = shutil.which("pyinstaller")
        if which_path:
            return True, f"PyInstaller encontrado no sistema: {which_path}"
        return False, "PyInstaller não encontrado. Instale com: pip install pyinstaller"


def build_pyinstaller_command(
    script_path: str,
    app_name: Optional[str] = None,
    onefile: bool = True,
    windowed: bool = True,
    icon_path: Optional[str] = None,
    add_data: Optional[List[str]] = None,
    hidden_imports: Optional[List[str]] = None,
    clean: bool = True,
    dist_dir: Optional[str] = None,
    work_dir: Optional[str] = None,
    use_python_module: bool = True
) -> List[str]:
    """
    Constrói a lista de argumentos para executar o PyInstaller de forma robusta.
    Por padrão usa [sys.executable, "-m", "PyInstaller"] para garantir o interpretador correto.
    """
    if use_python_module:
        cmd = [sys.executable, "-m", "PyInstaller"]
    else:
        cmd = ["pyinstaller"]

    # Modo de pacote
    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # Janela de console
    if windowed:
        cmd.append("--windowed")
    else:
        cmd.append("--console")

    # Limpeza de cache anterior
    if clean:
        cmd.append("--clean")

    # Sobrescrever saída sem perguntar
    cmd.append("--noconfirm")

    # Nome do aplicativo
    if app_name and app_name.strip():
        cmd.extend(["--name", app_name.strip()])

    # Ícone
    if icon_path and icon_path.strip():
        cmd.extend(["--icon", icon_path.strip()])

    # Diretórios de saída
    if dist_dir and dist_dir.strip():
        cmd.extend(["--distpath", dist_dir.strip()])
    if work_dir and work_dir.strip():
        cmd.extend(["--workpath", work_dir.strip()])

    # Hidden imports
    if hidden_imports:
        for imp in hidden_imports:
            imp_clean = imp.strip()
            if imp_clean:
                cmd.extend(["--hidden-import", imp_clean])

    # Add data (no Windows usa ponto e vírgula ';')
    if add_data:
        for item in add_data:
            item_clean = item.strip()
            if item_clean:
                cmd.extend(["--add-data", item_clean])

    # Script principal
    cmd.append(script_path.strip())
    return cmd


def build_batch_script(cmd_args: List[str], project_dir: Optional[str] = None) -> str:
    """Gera um script batch (.bat) para Windows executável com 1 clique ou via CI/CD."""
    lines = [
        "@echo off",
        "chcp 65001 > nul",
        "echo ==================================================",
        "echo    Compilação com PyInstaller via WinToolbox",
        "echo ==================================================",
        ""
    ]

    if project_dir:
        lines.append(f'cd /d "{project_dir}"')
        lines.append("")

    # Formata argumentos protegendo caminhos com espaços
    formatted_args = []
    for arg in cmd_args:
        if " " in arg and not arg.startswith('"'):
            formatted_args.append(f'"{arg}"')
        else:
            formatted_args.append(arg)

    lines.append(" ".join(formatted_args))
    lines.extend([
        "",
        "if %ERRORLEVEL% EQU 0 (",
        '    echo [SUCESSO] Compilação concluída com êxito!',
        ") else (",
        '    echo [ERRO] Ocorreu uma falha durante a compilação.',
        ")",
        "pause"
    ])
    return "\n".join(lines)


def validate_compilation_inputs(script_path: str, icon_path: Optional[str] = None) -> List[str]:
    """Valida se os caminhos dos arquivos existem e são válidos."""
    errors = []
    if not script_path or not script_path.strip():
        errors.append("O caminho do script principal Python (.py) é obrigatório.")
    else:
        p = Path(script_path.strip())
        if not p.is_file():
            errors.append(f"O script principal não foi encontrado: {script_path}")
        elif p.suffix.lower() not in (".py", ".pyw"):
            errors.append("O arquivo principal deve possuir extensão .py ou .pyw.")

    if icon_path and icon_path.strip():
        ip = Path(icon_path.strip())
        if not ip.is_file():
            errors.append(f"O arquivo de ícone não foi encontrado: {icon_path}")
        elif ip.suffix.lower() != ".ico":
            errors.append("O ícone deve possuir formato .ico para compilação Windows.")

    return errors
