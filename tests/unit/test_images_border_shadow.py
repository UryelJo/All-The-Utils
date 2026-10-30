"""
Testes de validação de efeito real para images.border_shadow (logic e contrato FileTool/ItemResult).
"""
from pathlib import Path
import pytest
from PIL import Image

from wintoolbox.core.batch import DiscoveredFile, OutputPolicy, execute_batch
from wintoolbox.core.registry import ItemResult, TaskContext
from wintoolbox.tools.images.border_shadow.logic import (
    parse_hex_color,
    round_corners,
    compose_mockup,
    process_image_border_shadow,
)
from wintoolbox.tools.images.border_shadow.tool import BorderShadowTool


def _make_ctx(cancelled: bool = False) -> TaskContext:
    return TaskContext(
        on_progress=lambda cur, tot, msg: None,
        on_log=lambda lvl, msg: None,
        is_cancelled=lambda: cancelled,
    )


def test_parse_hex_color_deterministic():
    assert parse_hex_color("#fff") == (255, 255, 255, 255)
    assert parse_hex_color("#102030") == (16, 32, 48, 255)
    assert parse_hex_color("#10203080") == (16, 32, 48, 128)
    assert parse_hex_color("invalido", alpha=100) == (255, 255, 255, 100)


def test_round_corners_real_effect():
    base = Image.new("RGB", (100, 100), (255, 0, 0))
    rounded = round_corners(base, radius=20)

    assert rounded.mode == "RGBA"
    assert rounded.size == (100, 100)

    corner_pixel = rounded.getpixel((0, 0))
    assert corner_pixel[3] == 0

    center_pixel = rounded.getpixel((50, 50))
    assert center_pixel[0] == 255
    assert center_pixel[3] == 255


def test_compose_mockup_dimensions_and_layers():
    base = Image.new("RGBA", (200, 100), (50, 150, 250, 255))
    mockup = compose_mockup(
        image=base,
        corner_radius=10,
        border_width=2,
        shadow_blur=10,
        shadow_offset_y=8,
        shadow_opacity=0.5,
        padding=20,
        background_mode="transparent",
    )

    assert mockup.width > 200
    assert mockup.height > 100
    assert mockup.mode == "RGBA"


def test_process_image_border_shadow_black_box(tmp_path: Path):
    src_file = tmp_path / "screenshot.png"
    src_img = Image.new("RGB", (300, 200), (30, 40, 50))
    src_img.save(src_file)

    out_file = tmp_path / "mockup_output.png"
    res = process_image_border_shadow(
        input_path=src_file,
        output_path=out_file,
        corner_radius=16,
        border_width=1,
        shadow_blur=20,
        shadow_offset_y=10,
        shadow_opacity=0.4,
        padding=30,
        background_mode="gradient",
        gradient_preset="slate",
    )

    assert res.is_file()
    assert res == out_file
    assert res.stat().st_size > 0

    with Image.open(res) as img:
        assert img.format == "PNG"
        assert img.size[0] > 300
        assert img.size[1] > 200

    with pytest.raises(FileNotFoundError):
        process_image_border_shadow(tmp_path / "nao_existe.png", tmp_path / "out.png")


def test_border_shadow_tool_process_and_batch_contract(tmp_path: Path):
    """Valida contrato ItemResult em BorderShadowTool.process (sucesso, cancelamento, falha e lote real)."""
    tool = BorderShadowTool()
    src_jpg = tmp_path / "captura.jpg"
    Image.new("RGB", (120, 80), (10, 120, 220)).save(src_jpg, format="JPEG")

    # 1. Cancelamento deve retornar ItemResult válido com success=False
    dst_cancel = tmp_path / "cancelado.png"
    res_cancel = tool.process(src_jpg, dst_cancel, params={}, ctx=_make_ctx(cancelled=True))
    assert isinstance(res_cancel, ItemResult)
    assert res_cancel.success is False
    assert res_cancel.source_path == src_jpg
    assert res_cancel.error == "Operação cancelada pelo usuário"
    assert not dst_cancel.exists()

    # 2. Falha (arquivo ausente) deve retornar ItemResult válido com success=False
    res_err = tool.process(tmp_path / "ausente.png", tmp_path / "falha.png", params={}, ctx=_make_ctx())
    assert isinstance(res_err, ItemResult)
    assert res_err.success is False
    assert res_err.error is not None and "ausente.png" in res_err.error

    # 3. Happy Path integrado ao execute_batch real (entrada .jpg -> saída limpa .png com transparência)
    params = {
        "radius": 12,
        "border_width": 2,
        "shadow_blur": 10,
        "shadow_opacity": 0.4,
        "padding": 20,
        "bg_text": "Transparente",
    }
    discovered = [
        DiscoveredFile(
            source_path=src_jpg,
            root_source_dir=tmp_path,
            size_bytes=src_jpg.stat().st_size,
            extension=".jpg",
        )
    ]
    policy = OutputPolicy(mode="subfolder", subfolder_name="mockups")
    batch_res = execute_batch(
        files=discovered,
        output_policy=policy,
        target_ext=tool.output_ext(params),
        process_func=tool.process,
        params=params,
        ctx=_make_ctx(),
    )
    assert batch_res.success is True
    assert batch_res.items_success == 1
    assert batch_res.items_failed == 0

    item_res = batch_res.details[0]
    assert item_res.success is True
    assert item_res.source_path == src_jpg
    expected_out = tmp_path / "mockups" / "captura.png"
    assert item_res.output_path == expected_out
    assert expected_out.is_file()
    assert item_res.bytes_in == src_jpg.stat().st_size
    assert item_res.bytes_out > 0

    with Image.open(expected_out) as out_im:
        assert out_im.format == "PNG"
        assert out_im.mode == "RGBA"
        assert out_im.size == (120 + (20 + 20) * 2, 80 + (20 + 20 + 12) * 2)
        assert out_im.getpixel((0, 0))[3] == 0
