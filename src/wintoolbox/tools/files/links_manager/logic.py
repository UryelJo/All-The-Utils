"""
Lógica pura para auditoria, inspeção e gerenciamento de ponteiros de sistema de arquivos NTFS.
Varre links simbólicos, Directory Junctions e Hardlinks com detecção de links quebrados e remoção segura.

Zero dependências de interface gráfica ou widgets.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import _winapi
except ImportError:
    _winapi = None


def inspect_pointer(path_str: str) -> Optional[Dict[str, Any]]:
    """
    Inspeciona um caminho e verifica se é um ponteiro NTFS (Symlink, Junction ou Hardlink).
    """
    p = Path(path_str)
    try:
        # Verifica se é link simbólico ou junction
        if os.path.islink(path_str) or p.is_symlink():
            try:
                target = os.readlink(path_str)
            except OSError:
                target = "(erro ao ler alvo)"

            target_p = Path(target)
            if not target_p.is_absolute():
                target_p = (p.parent / target_p).resolve()

            is_broken = not target_p.exists()
            is_dir = p.is_dir()

            # Diferenciação entre Junction e Symlink no Windows
            link_type = "Symlink (Diretório)" if is_dir else "Symlink (Arquivo)"
            # Se for reparse point de mount point no Windows, é Junction
            try:
                st = os.lstat(path_str)
                if hasattr(st, "st_reparse_tag") and st.st_reparse_tag == 0xA0000003:  # IO_REPARSE_TAG_MOUNT_POINT
                    link_type = "Directory Junction"
            except Exception:
                pass

            return {
                "path": str(p.resolve()),
                "name": p.name,
                "type": link_type,
                "target": str(target_p),
                "is_broken": is_broken,
                "status": "Quebrado (Alvo Inexistente)" if is_broken else "Ativo (Válido)",
                "nlink": 1,
            }

        # Verifica se é Hardlink (arquivo normal com mais de uma referência de diretório)
        st = os.stat(path_str)
        if not p.is_dir() and st.st_nlink > 1:
            return {
                "path": str(p.resolve()),
                "name": p.name,
                "type": "Hardlink",
                "target": f"Ponteiro compartilhado ({st.st_nlink} referências)",
                "is_broken": False,
                "status": f"Ativo ({st.st_nlink} hardlinks)",
                "nlink": st.st_nlink,
            }

    except (OSError, ValueError):
        pass

    return None


def scan_ntfs_links(root_path: str, max_results: int = 2000) -> List[Dict[str, Any]]:
    """
    Varre recursivamente uma pasta ou unidade procurando ponteiros de arquivos NTFS.
    """
    root = Path(root_path)
    if not root.exists():
        raise FileNotFoundError(f"Caminho não encontrado: {root_path}")

    found_links: List[Dict[str, Any]] = []

    for dirpath, dirnames, filenames in os.walk(str(root)):
        if len(found_links) >= max_results:
            break

        # Verifica diretórios (pode ser Junction ou Symlink Dir)
        for dname in list(dirnames):
            dpath = os.path.join(dirpath, dname)
            info = inspect_pointer(dpath)
            if info:
                found_links.append(info)
                # Não desce recursivamente em links para evitar loops infinitos
                if os.path.islink(dpath):
                    dirnames.remove(dname)

        # Verifica arquivos
        for fname in filenames:
            if len(found_links) >= max_results:
                break
            fpath = os.path.join(dirpath, fname)
            info = inspect_pointer(fpath)
            if info:
                found_links.append(info)

    return found_links


def remove_link_safely(link_path: str) -> bool:
    """
    Remove exclusivamente o ponteiro (symlink/junction) sem apagar o diretório ou arquivo alvo.
    """
    p = Path(link_path)
    if not p.exists() and not os.path.islink(link_path):
        return False

    if os.path.islink(link_path) or p.is_symlink():
        if p.is_dir():
            os.rmdir(link_path)
        else:
            os.remove(link_path)
        return True
    elif p.is_file():
        os.remove(link_path)
        return True

    return False
