"""
Lógica pura para localização e higienização em lote de diretórios vazios,
arquivos de 0 byte e atalhos (.lnk) com caminhos quebrados.

Zero dependências de interface gráfica ou widgets.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import send2trash


def resolve_lnk_target(lnk_path: str) -> Optional[str]:
    """
    Resolve o caminho de destino de um atalho do Windows (.lnk).
    Tenta COM nativo (WScript.Shell) ou extração de strings de caminhos binários.
    """
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(lnk_path)
        target = shortcut.TargetPath
        if target:
            return target
    except Exception:
        pass

    # Fallback: inspeção binária rápida de caminho Windows C:\...
    try:
        with open(lnk_path, "rb") as f:
            content = f.read(2048)
            # Procura padrões de caminho drive letter ex: C:\ ou D:\
            import re
            m = re.search(rb"[A-Za-z]:\\[^<>\":/\\|?*\0\r\n]+", content)
            if m:
                return m.group(0).decode("ascii", errors="replace")
    except Exception:
        pass

    return None


def scan_cleanup_candidates(
    root_path: str,
    find_empty_dirs: bool = True,
    find_zero_byte_files: bool = True,
    find_broken_shortcuts: bool = True,
) -> List[Dict[str, Any]]:
    """
    Varre um diretório e identifica pastas vazias, arquivos de 0 byte e atalhos quebrados.
    """
    root = Path(root_path)
    if not root.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {root_path}")

    candidates: List[Dict[str, Any]] = []

    # 1. Arquivos de 0 Byte e Atalhos Quebrados
    empty_dirs_candidates: List[str] = []

    for dirpath, dirnames, filenames in os.walk(str(root), topdown=False):
        # Verifica arquivos
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                st = os.stat(fpath)
                # 0 byte
                if find_zero_byte_files and st.st_size == 0:
                    candidates.append({
                        "path": fpath,
                        "name": fname,
                        "type": "Arquivo 0 Byte",
                        "size": 0,
                        "detail": "Arquivo sem conteúdo (0 byte)",
                    })

                # Atalhos .lnk
                if find_broken_shortcuts and fname.lower().endswith(".lnk"):
                    target = resolve_lnk_target(fpath)
                    if target and not os.path.exists(target):
                        candidates.append({
                            "path": fpath,
                            "name": fname,
                            "type": "Atalho Quebrado",
                            "size": st.st_size,
                            "detail": f"Alvo inexistente: {target}",
                        })
            except OSError:
                pass

        # Pastas vazias (de baixo para cima - bottom-up)
        if find_empty_dirs:
            try:
                # Se após eventual limpeza o diretório estiver sem itens
                current_contents = os.listdir(dirpath)
                if not current_contents and os.path.abspath(dirpath) != os.path.abspath(str(root)):
                    candidates.append({
                        "path": dirpath,
                        "name": os.path.basename(dirpath),
                        "type": "Pasta Vazia",
                        "size": 0,
                        "detail": "Nenhum arquivo ou subpasta presente",
                    })
            except OSError:
                pass

    return candidates


def execute_cleanup(
    items: List[Dict[str, Any]],
    use_trash: bool = True,
) -> Dict[str, Any]:
    """
    Remove os itens selecionados (arquivos ou pastas), enviando para a lixeira ou deletando definitivamente.
    """
    success_count = 0
    failed_items: List[Dict[str, str]] = []

    # Ordena para deletar arquivos primeiro e diretórios depois (maior profundidade primeiro)
    sorted_items = sorted(
        items,
        key=lambda x: (x.get("type") == "Pasta Vazia", -len(x.get("path", "")))
    )

    for item in sorted_items:
        p_str = item.get("path", "")
        if not os.path.exists(p_str):
            continue

        try:
            if use_trash:
                send2trash.send2trash(p_str)
            else:
                if os.path.isdir(p_str):
                    os.rmdir(p_str)
                else:
                    os.remove(p_str)
            success_count += 1
        except Exception as exc:
            failed_items.append({"path": p_str, "error": str(exc)})

    return {
        "total_requested": len(items),
        "success_count": success_count,
        "failed_count": len(failed_items),
        "failed_items": failed_items,
        "used_trash": use_trash,
    }
