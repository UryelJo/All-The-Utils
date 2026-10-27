"""
Testes unitários para dev.project_cleaner.
Valida varredura real em disco de pastas de compilação e exclusão segura.
"""
import pytest
from pathlib import Path

from wintoolbox.tools.dev.project_cleaner.logic import (
    delete_cleanable_items,
    get_dir_size_and_count,
    scan_cleanable_items,
)


@pytest.fixture
def mock_project_tree(tmp_path: Path) -> Path:
    """Cria uma estrutura de projeto simulando repositórios reais com pastas descartáveis."""
    # Projeto Node
    p_node = tmp_path / "app_node"
    p_node.mkdir()
    node_modules = p_node / "node_modules" / "pacote_a"
    node_modules.mkdir(parents=True)
    (node_modules / "index.js").write_text("console.log('teste');", encoding="utf-8")
    (p_node / "package.json").write_text("{}", encoding="utf-8")

    # Projeto Python
    p_py = tmp_path / "app_python"
    p_py.mkdir()
    pycache = p_py / "__pycache__"
    pycache.mkdir()
    (pycache / "module.cpython-312.pyc").write_bytes(b"BYTECODE1234")
    (p_py / "main.py").write_text("print('hello')", encoding="utf-8")

    # Projeto Rust
    p_rust = tmp_path / "app_rust"
    p_rust.mkdir()
    target = p_rust / "target" / "debug"
    target.mkdir(parents=True)
    (target / "app.exe").write_bytes(b"EXEBINARY0000")
    (p_rust / "Cargo.toml").write_text("[package]\nname='teste'", encoding="utf-8")

    return tmp_path


def test_get_dir_size_and_count(mock_project_tree: Path):
    """Valida cálculo recursivo exato de bytes e contagem de arquivos."""
    target_dir = mock_project_tree / "app_rust" / "target"
    sz, count = get_dir_size_and_count(target_dir)
    assert count == 1
    assert sz == len(b"EXEBINARY0000")


def test_scan_cleanable_items(mock_project_tree: Path):
    """Testa localização e classificação de pastas alvo de múltiplos ecossistemas."""
    items = scan_cleanable_items(mock_project_tree)
    found_types = {item.category for item in items}
    assert "node" in found_types
    assert "python" in found_types
    assert "rust" in found_types
    assert len(items) == 3

    # Confere caminhos
    paths = [i.path.name for i in items]
    assert "node_modules" in paths
    assert "__pycache__" in paths
    assert "target" in paths


def test_delete_cleanable_items(mock_project_tree: Path):
    """Testa exclusão física real de pastas de compilação."""
    node_modules = mock_project_tree / "app_node" / "node_modules"
    assert node_modules.is_dir()

    deleted_count, freed_bytes = delete_cleanable_items([node_modules], dry_run=False)
    assert deleted_count == 1
    assert freed_bytes > 0
    assert not node_modules.exists()


def test_scan_cleanable_items_not_found(tmp_path: Path):
    """Valida erro para diretório inexistente."""
    with pytest.raises(FileNotFoundError):
        scan_cleanable_items(tmp_path / "diretorio_fantasma")
