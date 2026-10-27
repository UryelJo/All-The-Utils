"""
Lógica pura para gerenciamento, inspeção e instalação de fontes tipográficas (TTF/OTF).

Permite instalar fontes sem privilégios de administrador gravando em
%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts e registrando no HKCU do Windows.
Zero dependências de interface gráfica ou bibliotecas de UI.
"""
import ctypes
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
import sys
import winreg
from typing import Any, Dict, List, Optional, Tuple

from fontTools.ttLib import TTFont
from wintoolbox.core.logging_setup import get_logger

_log = get_logger("system.fonts_manager.logic")


@dataclass
class FontInfo:
    family: str
    subfamily: str
    file_path: str
    file_name: str
    format_type: str
    is_user_font: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_user_fonts_dir() -> Path:
    """Retorna o diretório de fontes do usuário atual no Windows."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        p = Path(local_app_data) / "Microsoft" / "Windows" / "Fonts"
    else:
        p = Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_system_fonts_dir() -> Path:
    """Retorna o diretório de fontes global do Windows."""
    win_dir = os.environ.get("WINDIR") or "C:\\Windows"
    return Path(win_dir) / "Fonts"


def extract_font_metadata(font_path: Path) -> FontInfo:
    """
    Lê o cabeçalho TTF/OTF usando fontTools e extrai o nome da família e estilo.
    """
    if not font_path.is_file():
        raise FileNotFoundError(f"Arquivo de fonte não encontrado: {font_path}")

    ext = font_path.suffix.lower().lstrip(".")
    fmt = "OpenType" if ext == "otf" else "TrueType"

    family = font_path.stem
    subfamily = "Regular"

    try:
        tt = TTFont(str(font_path), fontNumber=0, lazy=True)
        name_table = tt.get("name")
        if name_table:
            for record in name_table.names:
                # 1 = Font Family name, 2 = Font Subfamily name
                # 16 = Typographic Family, 17 = Typographic Subfamily
                try:
                    string_val = record.toUnicode()
                except Exception:
                    continue

                if record.nameID in (1, 16) and string_val.strip():
                    family = string_val.strip()
                elif record.nameID in (2, 17) and string_val.strip():
                    subfamily = string_val.strip()

        tt.close()
    except Exception as e:
        _log.warning(f"Erro ao extrair metadados de {font_path.name}: {e}")

    user_dir = get_user_fonts_dir()
    is_user = str(font_path).lower().startswith(str(user_dir).lower())

    return FontInfo(
        family=family,
        subfamily=subfamily,
        file_path=str(font_path),
        file_name=font_path.name,
        format_type=fmt,
        is_user_font=is_user
    )


def install_font_for_current_user(source_path: Path) -> Tuple[bool, str]:
    """
    Instala uma fonte no perfil do usuário atual (não requer privilégios de administrador).
    """
    if not source_path.is_file():
        return (False, f"Arquivo de fonte não encontrado: {source_path}")

    ext = source_path.suffix.lower()
    if ext not in (".ttf", ".otf"):
        return (False, f"Formato não suportado: {ext}. Utilize arquivos .ttf ou .otf.")

    try:
        meta = extract_font_metadata(source_path)
    except Exception as e:
        return (False, f"Falha ao ler fonte: {e}")

    user_dir = get_user_fonts_dir()
    target_path = user_dir / source_path.name

    try:
        shutil.copy2(source_path, target_path)

        # Registra no HKCU\Software\Microsoft\Windows NT\CurrentVersion\Fonts
        font_entry_name = f"{meta.family} ({meta.subfamily}) (TrueType)" if meta.format_type == "TrueType" else f"{meta.family} ({meta.subfamily}) (OpenType)"
        reg_key_path = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_key_path) as key:
            winreg.SetValueEx(key, font_entry_name, 0, winreg.REG_SZ, str(target_path))

        # Notifica a API do GDI do Windows
        if sys.platform == "win32":
            ctypes.windll.gdi32.AddFontResourceW(str(target_path))

        return (True, f"Fonte '{meta.family}' instalada com sucesso para o usuário atual!")
    except Exception as e:
        return (False, f"Erro durante a instalação da fonte: {e}")


def list_installed_fonts_summary(max_limit: int = 150) -> List[FontInfo]:
    """
    Lista uma amostra de fontes instaladas (priorizando as do usuário em AppData e principais do Windows).
    """
    results: List[FontInfo] = []
    seen_files = set()

    # 1. Fontes do usuário
    user_dir = get_user_fonts_dir()
    if user_dir.is_dir():
        for f in user_dir.glob("*.[tT][tT][fF]"):
            if len(results) >= max_limit:
                break
            try:
                results.append(extract_font_metadata(f))
                seen_files.add(f.name.lower())
            except Exception:
                continue

    # 2. Fontes do sistema
    sys_dir = get_system_fonts_dir()
    if sys_dir.is_dir():
        for f in sys_dir.glob("*.[tT][tT][fF]"):
            if len(results) >= max_limit:
                break
            if f.name.lower() in seen_files:
                continue
            try:
                results.append(extract_font_metadata(f))
                seen_files.add(f.name.lower())
            except Exception:
                continue

    return results
