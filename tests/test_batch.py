"""
Testes unitários do motor de lote (Batch Engine).
Valida descoberta de arquivos, recursão, resolução de conflitos e execução.
"""
from pathlib import Path
from wintoolbox.core.batch import (
    DiscoveredFile, OutputPolicy, SourceItem, calculate_destination_path,
    discover_files, execute_batch
)
from wintoolbox.core.registry import ItemResult, TaskContext

def test_discover_files_recursive_and_non_recursive(tmp_path: Path):
    # Cria estrutura de pastas de teste:
    # tmp/
    #   a.png
    #   sub/
    #     b.png
    #     c.txt
    (tmp_path / "a.png").write_text("dummy")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.png").write_text("dummy")
    (sub / "c.txt").write_text("dummy")

    # 1. Sem recursão (deve achar apenas a.png)
    src_non_rec = [SourceItem(path=tmp_path, is_dir=True, recursive=False)]
    found = discover_files(src_non_rec, allowed_extensions={".png"})
    assert len(found) == 1
    assert found[0].source_path.name == "a.png"

    # 2. Com recursão (deve achar a.png e b.png, ignorando c.txt)
    src_rec = [SourceItem(path=tmp_path, is_dir=True, recursive=True)]
    found_rec = discover_files(src_rec, allowed_extensions={".png"})
    assert len(found_rec) == 2
    names = {f.source_path.name for f in found_rec}
    assert names == {"a.png", "b.png"}

def test_calculate_destination_path_subfolder(tmp_path: Path):
    src = tmp_path / "foto.png"
    src.write_text("x")
    item = DiscoveredFile(source_path=src, root_source_dir=tmp_path)
    policy = OutputPolicy(mode="subfolder", subfolder_name="saida", conflict="rename")

    dest = calculate_destination_path(item, policy, target_ext=".webp")
    assert dest.parent == tmp_path / "saida"
    assert dest.name == "foto.webp"

def test_calculate_destination_path_conflict_rename(tmp_path: Path):
    src = tmp_path / "foto.png"
    src.write_text("x")
    dest_dir = tmp_path / "saida"
    dest_dir.mkdir()
    # Já existe foto.webp
    (dest_dir / "foto.webp").write_text("existente")

    item = DiscoveredFile(source_path=src, root_source_dir=tmp_path)
    policy = OutputPolicy(mode="subfolder", subfolder_name="saida", conflict="rename")

    dest = calculate_destination_path(item, policy, target_ext=".webp")
    assert dest.name == "foto (1).webp"

def test_execute_batch_mock(tmp_path: Path):
    src1 = tmp_path / "f1.png"
    src2 = tmp_path / "f2.png"
    src1.write_text("1")
    src2.write_text("2")

    items = [
        DiscoveredFile(source_path=src1, root_source_dir=tmp_path),
        DiscoveredFile(source_path=src2, root_source_dir=tmp_path),
    ]
    policy = OutputPolicy(mode="subfolder", subfolder_name="out")

    def mock_process(src: Path, dst: Path, params: dict, ctx: TaskContext):
        dst.write_text("converted")
        return ItemResult(success=True, source_path=src, output_path=dst)

    ctx = TaskContext(
        on_progress=lambda c, t, m: None,
        on_log=lambda l, m: None,
        is_cancelled=lambda: False
    )

    res = execute_batch(
        files=items,
        output_policy=policy,
        target_ext=".webp",
        process_func=mock_process,
        params={},
        ctx=ctx
    )

    assert res.success
    assert res.items_total == 2
    assert res.items_success == 2
    assert (tmp_path / "out" / "f1.webp").exists()
    assert (tmp_path / "out" / "f2.webp").exists()
