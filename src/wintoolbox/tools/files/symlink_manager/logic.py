"""
Lógica pura para criação, auditoria e gerenciamento de Links Simbólicos,
Directory Junctions (mklink /J) e Hard Links no Windows NTFS.
Verifica integridade de alvos, links órfãos/quebrados e remoção segura sem apagar alvos.

Zero dependências de interface gráfica.
"""
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# No Windows, _winapi possui CreateJunction nativo
try:
    import _winapi
except ImportError:
    _winapi = None


def create_link(
    link_path: Path,
    target_path: Path,
    link_type: str = "junction",
) -> Dict[str, Any]:
    """
    Cria um link no sistema de arquivos.
    :param link_type: 'junction' (Directory Junction), 'symlink_dir', 'symlink_file' ou 'hardlink'.
    """
    link = Path(link_path).resolve()
    target = Path(target_path).resolve()

    if link.exists():
        raise FileExistsError(f"O caminho do link já existe: {link}")

    if not target.exists():
        raise FileNotFoundError(f"O alvo do link não existe: {target}")

    link.parent.mkdir(parents=True, exist_ok=True)
    ltype = link_type.lower().strip()

    if ltype == "junction":
        if not target.is_dir():
            raise ValueError(f"O alvo de uma Directory Junction deve ser uma pasta: {target}")
        if _winapi and hasattr(_winapi, "CreateJunction"):
            _winapi.CreateJunction(str(target), str(link))
        else:
            # Fallback em sistemas compatíveis
            os.symlink(target, link, target_is_directory=True)

    elif ltype == "symlink_dir":
        if not target.is_dir():
            raise ValueError(f"O alvo de um Symlink de diretório deve ser uma pasta: {target}")
        os.symlink(target, link, target_is_directory=True)

    elif ltype == "symlink_file":
        if not target.is_file():
            raise ValueError(f"O alvo de um Symlink de arquivo deve ser um arquivo: {target}")
        os.symlink(target, link, target_is_directory=False)

    elif ltype == "hardlink":
        if not target.is_file():
            raise ValueError(f"Hard links só podem ser criados para arquivos: {target}")
        os.link(target, link)

    else:
        raise ValueError(f"Tipo de link não suportado: {link_type}")

    return {
        "link_path": str(link),
        "target_path": str(target),
        "link_type": ltype,
        "created": True,
    }


def scan_links_in_directory(search_dir: Path, recursive: bool = True) -> List[Dict[str, Any]]:
    """
    Varre um diretório procurando por symlinks e directory junctions.
    Identifica se o link está ativo ou quebrado (alvo não encontrado).
    """
    root = Path(search_dir).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Caminho não é um diretório: {root}")

    found_links: List[Dict[str, Any]] = []

    def _inspect_entry(path_obj: Path):
        try:
            st = os.lstat(path_obj)
            is_reparse = bool(getattr(st, "st_file_attributes", 0) & 0x400)
            is_symlink = path_obj.is_symlink()

            if is_symlink or is_reparse:
                try:
                    target_str = os.readlink(path_obj)
                    clean_target = target_str.removeprefix("\\\\?\\")
                    target_path = Path(clean_target)
                    if not target_path.is_absolute():
                        target_path = path_obj.parent / target_path
                    is_active = target_path.exists()
                except Exception:
                    clean_target = "Desconhecido"
                    is_active = False

                link_type_name = "Directory Junction" if is_reparse and not is_symlink else ("Symlink Arquivo" if path_obj.is_file() else "Symlink Pasta")
                found_links.append({
                    "name": path_obj.name,
                    "path": str(path_obj),
                    "target": clean_target,
                    "type": link_type_name,
                    "status": "ATIVO" if is_active else "QUEBRADO",
                    "details": "Alvo acessível" if is_active else "Alvo ausente ou inacessível",
                })
                return True
        except (PermissionError, OSError):
            return False
        return False

    if recursive:
        for current_root, dirs, files in os.walk(root, followlinks=False):
            curr_p = Path(current_root)
            for d in list(dirs):
                d_path = curr_p / d
                if _inspect_entry(d_path):
                    # Não desce em junções recursivas para evitar loops infinitos
                    dirs.remove(d)
            for f in files:
                f_path = curr_p / f
                _inspect_entry(f_path)
    else:
        for entry in os.scandir(root):
            _inspect_entry(Path(entry.path))

    return found_links


def remove_link_safely(link_path: Path) -> bool:
    """
    Remove de forma segura APENAS o link simbólico ou junção,
    sem jamais apagar o conteúdo do diretório ou arquivo alvo.
    """
    link = Path(link_path)
    if not link.is_symlink() and not link.is_file():
        # No Windows, Directory Junctions podem ser removidas com rmdir sem /s
        try:
            os.rmdir(link)
            return True
        except Exception:
            pass

    if link.is_dir():
        # rmdir em um link/junction apaga apenas o ponteiro do reparse point
        os.rmdir(link)
    else:
        link.unlink(missing_ok=True)

    return True
