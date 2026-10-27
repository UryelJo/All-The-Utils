"""
Testes unitários rigorosos para files.tree_export.logic.
Garante construção determinística da árvore de diretórios e exportação precisa em ASCII, Markdown, CSV e HTML.
"""
from pathlib import Path
import pytest
from wintoolbox.tools.files.tree_export.logic import (
    build_directory_tree,
    export_ascii_tree,
    export_csv_tree,
    export_html_tree,
    export_markdown_tree,
)


def _setup_test_hierarchy(root: Path) -> None:
    src = root / "src"
    docs = root / "docs"
    git = root / ".git"

    src.mkdir(parents=True)
    docs.mkdir(parents=True)
    git.mkdir(parents=True)

    (src / "main.py").write_text("print('olá')", encoding="utf-8")
    (docs / "guia.md").write_text("# Guia de Uso", encoding="utf-8")
    (git / "config").write_text("ignore-me", encoding="utf-8")
    (root / "README.txt").write_text("projeto exemplo", encoding="utf-8")


def test_build_tree_and_ignore_patterns(tmp_path: Path):
    root = tmp_path / "meu_projeto"
    root.mkdir()
    _setup_test_hierarchy(root)

    tree = build_directory_tree(str(root), max_depth=3, include_files=True)

    assert tree["name"] == "meu_projeto"
    assert tree["is_dir"] is True
    assert tree["size"] > 0

    child_names = [c["name"] for c in tree["children"]]
    assert "src" in child_names
    assert "docs" in child_names
    assert "README.txt" in child_names
    # Garante que .git foi ignorado
    assert ".git" not in child_names


def test_export_ascii_tree(tmp_path: Path):
    root = tmp_path / "app"
    root.mkdir()
    _setup_test_hierarchy(root)

    tree = build_directory_tree(str(root), max_depth=3)
    ascii_out = export_ascii_tree(tree, show_size=True)

    assert "app/" in ascii_out
    assert "src/" in ascii_out
    assert "main.py" in ascii_out
    assert ("├── " in ascii_out) or ("└── " in ascii_out)


def test_export_markdown_tree(tmp_path: Path):
    root = tmp_path / "app"
    root.mkdir()
    _setup_test_hierarchy(root)

    tree = build_directory_tree(str(root), max_depth=3)
    md_out = export_markdown_tree(tree, show_size=False)

    assert "- 📁 **app/**" in md_out
    assert "- 📁 **src/**" in md_out
    assert "- 📄 `main.py`" in md_out


def test_export_csv_and_html_tree(tmp_path: Path):
    root = tmp_path / "app"
    root.mkdir()
    _setup_test_hierarchy(root)

    tree = build_directory_tree(str(root), max_depth=3)

    # CSV
    csv_out = export_csv_tree(tree)
    assert "Nível;Tipo;Nome;Tamanho (Bytes);Tamanho Formatado;Caminho Relativo" in csv_out
    assert ";Pasta;src;" in csv_out
    assert ";Arquivo;README.txt;" in csv_out

    # HTML
    html_out = export_html_tree(tree, show_size=True)
    assert "<!DOCTYPE html>" in html_out
    assert "<details open><summary>📁" in html_out
    assert "<div class='file'>📄" in html_out


def test_tree_nonexistent_directory():
    with pytest.raises(FileNotFoundError, match="não encontrado"):
        build_directory_tree("C:/caminho/falso/para/arvore_xyz")
