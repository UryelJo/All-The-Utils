"""
Lógica pura para gerenciamento do Subsistema do Windows para Linux (WSL).

Permite listar, controlar (parar, encerrar), exportar/importar distribuições
e configurar limites de recursos (RAM, CPU, Swap) via .wslconfig.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
import configparser
from dataclasses import asdict, dataclass
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.wsl_manager.logic")


@dataclass
class WslDistro:
    name: str
    state: str
    version: int
    is_default: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def decode_wsl_output(raw_bytes: bytes) -> str:
    """
    Decodifica saída de wsl.exe tratando adequadamente UTF-16LE ou UTF-8.
    """
    if not raw_bytes:
        return ""
    if b"\x00" in raw_bytes[:10]:
        try:
            return raw_bytes.decode("utf-16le", errors="replace")
        except Exception:
            pass
    try:
        return raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        return raw_bytes.decode("latin1", errors="replace")


def parse_wsl_list_output(output_text: str) -> List[WslDistro]:
    """
    Analisa a saída tabular de 'wsl -l -v'.
    Exemplo:
      NAME            STATE           VERSION
    * Ubuntu-22.04    Running         2
      docker-desktop  Stopped         2
    """
    distros: List[WslDistro] = []
    lines = output_text.strip().splitlines()
    if not lines:
        return []

    # Ignora linha de cabeçalho
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue

        is_def = line.startswith("*")
        clean_line = line.lstrip("*").strip()
        parts = re.split(r"\s{2,}|\t+", clean_line)
        if len(parts) >= 2:
            name = parts[0].strip()
            state = parts[1].strip()
            version_str = parts[2].strip() if len(parts) >= 3 else "2"
            try:
                version = int(version_str)
            except ValueError:
                version = 2

            distros.append(WslDistro(
                name=name,
                state=state,
                version=version,
                is_default=is_def
            ))

    return distros


def get_wslconfig_path() -> Path:
    """Retorna o caminho do arquivo .wslconfig no perfil do usuário."""
    return Path.home() / ".wslconfig"


def parse_wslconfig(path: Optional[Path] = None) -> Dict[str, str]:
    """
    Lê o arquivo .wslconfig e retorna as propriedades de [wsl2].
    """
    cfg_path = path or get_wslconfig_path()
    if not cfg_path.is_file():
        return {}

    config = configparser.ConfigParser()
    try:
        config.read(cfg_path, encoding="utf-8")
        if "wsl2" in config:
            return dict(config["wsl2"])
    except Exception as e:
        _log.warning(f"Erro ao ler .wslconfig: {e}")

    return {}


def write_wslconfig(
    memory: Optional[str] = None,
    processors: Optional[int] = None,
    swap: Optional[str] = None,
    path: Optional[Path] = None
) -> Path:
    """
    Grava ou atualiza os limites de recursos em .wslconfig.
    """
    cfg_path = path or get_wslconfig_path()
    config = configparser.ConfigParser()
    if cfg_path.is_file():
        try:
            config.read(cfg_path, encoding="utf-8")
        except Exception:
            pass

    if "wsl2" not in config:
        config["wsl2"] = {}

    if memory:
        config["wsl2"]["memory"] = memory
    if processors and processors > 0:
        config["wsl2"]["processors"] = str(processors)
    if swap:
        config["wsl2"]["swap"] = swap

    with cfg_path.open("w", encoding="utf-8") as f:
        config.write(f)

    return cfg_path


def query_installed_distros() -> List[WslDistro]:
    """
    Executa 'wsl -l -v' e retorna as distribuições registradas.
    """
    try:
        proc = subprocess.run(
            ["wsl.exe", "-l", "-v"],
            capture_output=True,
            timeout=15,
            check=False
        )
        if proc.returncode == 0:
            text = decode_wsl_output(proc.stdout)
            return parse_wsl_list_output(text)
    except Exception as e:
        _log.warning(f"Erro ao consultar distribuições WSL: {e}")

    return []


def stop_distro(name: str) -> Tuple[bool, str]:
    """Interrompe a execução de uma distribuição específica (wsl -t <name>)."""
    try:
        res = subprocess.run(["wsl.exe", "-t", name], capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            return (True, f"Distribuição '{name}' finalizada com sucesso.")
        return (False, f"Erro ao finalizar '{name}': {res.stderr.strip()}")
    except Exception as e:
        return (False, f"Falha na execução: {e}")


def shutdown_all_wsl() -> Tuple[bool, str]:
    """Encerra todas as distribuições e a máquina virtual WSL2 (wsl --shutdown)."""
    try:
        res = subprocess.run(["wsl.exe", "--shutdown"], capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            return (True, "Subsistema WSL completamente encerrado.")
        return (False, f"Erro ao desligar WSL: {res.stderr.strip()}")
    except Exception as e:
        return (False, f"Falha na execução: {e}")


def set_default_distro(name: str) -> Tuple[bool, str]:
    """Define a distribuição como padrão (wsl -s <name>)."""
    try:
        res = subprocess.run(["wsl.exe", "-s", name], capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            return (True, f"'{name}' agora é a distribuição padrão.")
        return (False, f"Erro ao definir padrão: {res.stderr.strip()}")
    except Exception as e:
        return (False, f"Falha na execução: {e}")


def export_distro_tar(name: str, tar_path: Path) -> Tuple[bool, str]:
    """Exporta uma distribuição inteira para arquivo tar (wsl --export <name> <path>)."""
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        res = subprocess.run(
            ["wsl.exe", "--export", name, str(tar_path)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False
        )
        if res.returncode == 0 and tar_path.is_file():
            return (True, f"Distribuição '{name}' exportada com sucesso para {tar_path.name}.")
        return (False, f"Erro ao exportar: {res.stderr.strip()}")
    except Exception as e:
        return (False, f"Falha na exportação: {e}")
