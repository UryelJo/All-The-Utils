"""
Lógica pura para geração e exportação de representações de árvores de diretórios.
Suporta formatos ASCII/Unicode, Markdown com listas aninhadas, planilhas CSV e relatórios HTML.

Zero dependências de interface gráfica ou widgets.
"""
import csv
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


def format_file_size(size: int) -> str:
    """Formata tamanho de bytes."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"


def build_directory_tree(
    root_path: str,
    max_depth: int = 5,
    include_files: bool = True,
    ignored_names: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Constrói representação hierárquica recursiva de uma pasta até 'max_depth'.
    """
    root = Path(root_path)
    if not root.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {root_path}")

    ignored = ignored_names or {".git", ".svn", "__pycache__", "node_modules", ".venv"}

    def _walk_dir(current_path: Path, current_depth: int) -> Dict[str, Any]:
        node: Dict[str, Any] = {
            "name": current_path.name or str(current_path),
            "is_dir": True,
            "size": 0,
            "children": [],
        }

        if current_depth > max_depth:
            return node

        try:
            entries = sorted(list(current_path.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return node

        total_size = 0
        for entry in entries:
            if entry.name in ignored:
                continue

            if entry.is_dir():
                sub_node = _walk_dir(entry, current_depth + 1)
                total_size += sub_node.get("size", 0)
                node["children"].append(sub_node)
            elif include_files:
                try:
                    fsize = entry.stat().st_size
                except OSError:
                    fsize = 0
                total_size += fsize
                node["children"].append({
                    "name": entry.name,
                    "is_dir": False,
                    "size": fsize,
                    "children": [],
                })

        node["size"] = total_size
        return node

    return _walk_dir(root, 1)


def export_ascii_tree(tree_node: Dict[str, Any], show_size: bool = True) -> str:
    """Exporta a árvore no formato Unicode/ASCII clássico (├──, └──, │)."""
    lines: List[str] = []

    root_size_str = f" ({format_file_size(tree_node['size'])})" if show_size else ""
    lines.append(f"{tree_node['name']}/{root_size_str}")

    def _format_children(children: List[Dict[str, Any]], prefix: str = "") -> None:
        count = len(children)
        for i, child in enumerate(children):
            is_last = (i == count - 1)
            connector = "└── " if is_last else "├── "
            extension_prefix = "    " if is_last else "│   "

            name_suffix = "/" if child["is_dir"] else ""
            size_suffix = f" ({format_file_size(child['size'])})" if show_size and not child["is_dir"] else ""

            lines.append(f"{prefix}{connector}{child['name']}{name_suffix}{size_suffix}")

            if child["is_dir"] and child.get("children"):
                _format_children(child["children"], prefix + extension_prefix)

    _format_children(tree_node.get("children", []))
    return "\n".join(lines)


def export_markdown_tree(tree_node: Dict[str, Any], show_size: bool = True) -> str:
    """Exporta a árvore como lista com marcadores Markdown aninhada."""
    lines: List[str] = []

    def _format_node(node: Dict[str, Any], depth: int) -> None:
        indent = "  " * depth
        if node["is_dir"]:
            lines.append(f"{indent}- 📁 **{node['name']}/**")
            for ch in node.get("children", []):
                _format_node(ch, depth + 1)
        else:
            size_str = f" *({format_file_size(node['size'])})*" if show_size else ""
            lines.append(f"{indent}- 📄 `{node['name']}`{size_str}")

    _format_node(tree_node, 0)
    return "\n".join(lines)


def export_csv_tree(tree_node: Dict[str, Any]) -> str:
    """Exporta os arquivos e pastas da árvore em formato CSV tabular."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["Nível", "Tipo", "Nome", "Tamanho (Bytes)", "Tamanho Formatado", "Caminho Relativo"])

    def _walk_flat(node: Dict[str, Any], depth: int, rel_path: str) -> None:
        ntype = "Pasta" if node["is_dir"] else "Arquivo"
        writer.writerow([
            depth,
            ntype,
            node["name"],
            node["size"],
            format_file_size(node["size"]),
            rel_path,
        ])
        for ch in node.get("children", []):
            child_rel = f"{rel_path}/{ch['name']}" if rel_path else ch["name"]
            _walk_flat(ch, depth + 1, child_rel)

    _walk_flat(tree_node, 1, tree_node["name"])
    return out.getvalue()


def export_html_tree(tree_node: Dict[str, Any], show_size: bool = True) -> str:
    """Exporta a árvore como documento HTML colapsável usando tags <details> e <summary>."""
    lines = [
        "<!DOCTYPE html>",
        "<html lang='pt-br'>",
        "<head>",
        "  <meta charset='utf-8'>",
        f"  <title>Árvore: {tree_node['name']}</title>",
        "  <style>",
        "    body { font-family: Segoe UI, sans-serif; background: #1f1f1f; color: #f0f0f0; padding: 20px; }",
        "    details { margin-left: 16px; margin-top: 4px; }",
        "    summary { cursor: pointer; font-weight: 600; color: #4daafc; }",
        "    .file { margin-left: 20px; margin-top: 2px; color: #e0e0e0; }",
        "    .size { color: #888888; font-size: 12px; margin-left: 6px; }",
        "  </style>",
        "</head>",
        "<body>",
        f"  <h2>📁 {tree_node['name']}</h2>",
    ]

    def _render_html(node: Dict[str, Any]) -> None:
        if node["is_dir"]:
            lines.append(f"  <details open><summary>📁 {node['name']}</summary>")
            for ch in node.get("children", []):
                _render_html(ch)
            lines.append("  </details>")
        else:
            size_str = f"<span class='size'>({format_file_size(node['size'])})</span>" if show_size else ""
            lines.append(f"    <div class='file'>📄 {node['name']} {size_str}</div>")

    for child in tree_node.get("children", []):
        _render_html(child)

    lines.extend(["</body>", "</html>"])
    return "\n".join(lines)
