"""
Testes de validação de efeito real para images.split_grid (logic e contrato FileTool/ItemResult).
Verifica corte, particionamento, reconstrução de mosaico bit a bit e integração com BatchEngine.
"""
from pathlib import Path
import pytest
from PIL import Image, ImageChops

from wintoolbox.core.batch import DiscoveredFile, OutputPolicy, execute_batch
from wintoolbox.core.registry import ItemResult, TaskContext
from wintoolbox.tools.images.split_grid.logic import (
    calculate_grid_boxes,
    split_image_file,
)
from wintoolbox.tools.images.split_grid.tool import SplitGridTool


def _make_ctx(cancelled: bool = False) -> TaskContext:
    return TaskContext(
        on_progress=lambda cur, tot, msg: None,
        on_log=lambda lvl, msg: None,
        is_cancelled=lambda: cancelled,
    )


def test_calculate_grid_boxes_deterministic():
    boxes = calculate_grid_boxes(width=600, height=400, rows=2, cols=3, overlap_px=0)
    assert len(boxes) == 6
    assert boxes[0] == (1, 1, 0, 0, 200, 200)
    assert boxes[1] == (1, 2, 200, 0, 400, 200)
    assert boxes[2] == (1, 3, 400, 0, 600, 200)
    assert boxes[3] == (2, 1, 0, 200, 200, 400)


def test_calculate_grid_boxes_with_overlap():
    boxes = calculate_grid_boxes(width=300, height=100, rows=1, cols=3, overlap_px=10)
    assert len(boxes) == 3
    assert boxes[0] == (1, 1, 0, 0, 110, 100)
    assert boxes[1] == (1, 2, 90, 0, 210, 100)
    assert boxes[2] == (1, 3, 190, 0, 300, 100)


def test_calculate_grid_boxes_validation_errors():
    with pytest.raises(ValueError):
        calculate_grid_boxes(100, 100, 0, 2)
    with pytest.raises(ValueError):
        calculate_grid_boxes(0, 100, 2, 2)


def test_split_image_file_black_box_and_reconstruction(tmp_path: Path):
    base = Image.new("RGB", (200, 200))
    base.paste(Image.new("RGB", (100, 100), (255, 0, 0)), (0, 0))
    base.paste(Image.new("RGB", (100, 100), (0, 255, 0)), (100, 0))
    base.paste(Image.new("RGB", (100, 100), (0, 0, 255)), (0, 100))
    base.paste(Image.new("RGB", (100, 100), (255, 255, 0)), (100, 100))

    src_file = tmp_path / "mosaic.png"
    base.save(src_file)

    out_dir = tmp_path / "parts"
    generated = split_image_file(
        input_path=src_file,
        output_dir=out_dir,
        rows=2,
        cols=2,
        overlap_px=0,
        output_format="png",
    )

    assert len(generated) == 4
    for f in generated:
        assert f.is_file()
        assert f.stat().st_size > 0

    with Image.open(generated[0]) as t1:
        assert t1.size == (100, 100)
        assert t1.getpixel((50, 50)) == (255, 0, 0)

    with Image.open(generated[1]) as t2:
        assert t2.size == (100, 100)
        assert t2.getpixel((50, 50)) == (0, 255, 0)

    with Image.open(generated[2]) as t3:
        assert t3.size == (100, 100)
        assert t3.getpixel((50, 50)) == (0, 0, 255)

    with Image.open(generated[3]) as t4:
        assert t4.size == (100, 100)
        assert t4.getpixel((50, 50)) == (255, 255, 0)

    reconstructed = Image.new("RGB", (200, 200))
    with Image.open(generated[0]) as t1:
        reconstructed.paste(t1, (0, 0))
    with Image.open(generated[1]) as t2:
        reconstructed.paste(t2, (100, 0))
    with Image.open(generated[2]) as t3:
        reconstructed.paste(t3, (0, 100))
    with Image.open(generated[3]) as t4:
        reconstructed.paste(t4, (100, 100))

    diff = ImageChops.difference(base, reconstructed)
    assert diff.getbbox() is None

    with pytest.raises(FileNotFoundError):
        split_image_file(tmp_path / "nao_existe.png", out_dir)


def test_split_grid_tool_process_and_batch_contract(tmp_path: Path):
    """Valida contrato ItemResult em SplitGridTool.process (sucesso em lote sem widgets Qt, cancelamento e erro)."""
    tool = SplitGridTool()
    src = tmp_path / "banner.png"
    Image.new("RGB", (300, 100), (80, 160, 240)).save(src, format="PNG")

    # 1. Cancelamento
    res_cancel = tool.process(src, tmp_path / "out.png", params={"rows": 1, "cols": 3}, ctx=_make_ctx(cancelled=True))
    assert isinstance(res_cancel, ItemResult)
    assert res_cancel.success is False
    assert res_cancel.source_path == src

    # 2. Falha (arquivo ausente)
    res_err = tool.process(tmp_path / "inexistente.png", tmp_path / "out.png", params={"rows": 1, "cols": 3}, ctx=_make_ctx())
    assert isinstance(res_err, ItemResult)
    assert res_err.success is False
    assert res_err.error is not None

    # 3. Execução via execute_batch (com caminho temporário .wtbx-...)
    params = {"rows": 1, "cols": 3, "overlap": 0, "format": "PNG"}
    discovered = [
        DiscoveredFile(
            source_path=src,
            root_source_dir=tmp_path,
            size_bytes=src.stat().st_size,
            extension=".png",
        )
    ]
    batch_res = execute_batch(
        files=discovered,
        output_policy=OutputPolicy(mode="subfolder", subfolder_name="fatias"),
        target_ext=tool.output_ext(params),
        process_func=tool.process,
        params=params,
        ctx=_make_ctx(),
    )
    assert batch_res.success is True
    assert batch_res.items_success == 1

    expected_dir = tmp_path / "fatias" / "banner_grid_1x3"
    assert batch_res.details[0].output_path == expected_dir
    parts = sorted(expected_dir.glob("*.png"))
    assert len(parts) == 3
    for p in parts:
        with Image.open(p) as im:
            assert im.size == (100, 100)
