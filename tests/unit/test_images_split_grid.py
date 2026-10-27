"""
Testes de validação de efeito real para images.split_grid.logic.
Verifica corte, particionamento e reconstrução de mosaico bit a bit.
"""
from pathlib import Path
import pytest
from PIL import Image, ImageChops

from wintoolbox.tools.images.split_grid.logic import (
    calculate_grid_boxes,
    split_image,
    split_image_file,
)


def test_calculate_grid_boxes_deterministic():
    # Grade 2x3 em 600x400
    boxes = calculate_grid_boxes(width=600, height=400, rows=2, cols=3, overlap_px=0)
    assert len(boxes) == 6

    # Primeiro tile (r1, c1)
    assert boxes[0] == (1, 1, 0, 0, 200, 200)
    # Segundo tile (r1, c2)
    assert boxes[1] == (1, 2, 200, 0, 400, 200)
    # Terceiro tile (r1, c3)
    assert boxes[2] == (1, 3, 400, 0, 600, 200)
    # Quarto tile (r2, c1)
    assert boxes[3] == (2, 1, 0, 200, 200, 400)


def test_calculate_grid_boxes_with_overlap():
    boxes = calculate_grid_boxes(width=300, height=100, rows=1, cols=3, overlap_px=10)
    assert len(boxes) == 3
    # Tile 1: 0 a 110 (100 + overlap)
    assert boxes[0] == (1, 1, 0, 0, 110, 100)
    # Tile 2: 90 a 210 (200 - overlap e 200 + overlap)
    assert boxes[1] == (1, 2, 90, 0, 210, 100)
    # Tile 3: 190 a 300
    assert boxes[2] == (1, 3, 190, 0, 300, 100)


def test_calculate_grid_boxes_validation_errors():
    with pytest.raises(ValueError):
        calculate_grid_boxes(100, 100, 0, 2)
    with pytest.raises(ValueError):
        calculate_grid_boxes(0, 100, 2, 2)


def test_split_image_file_black_box_and_reconstruction(tmp_path: Path):
    # Cria uma imagem 200x200 com 4 quadrantes de cores puras
    base = Image.new("RGB", (200, 200))
    # Quadrante superior esquerdo: Vermelho
    base.paste(Image.new("RGB", (100, 100), (255, 0, 0)), (0, 0))
    # Quadrante superior direito: Verde
    base.paste(Image.new("RGB", (100, 100), (0, 255, 0)), (100, 0))
    # Quadrante inferior esquerdo: Azul
    base.paste(Image.new("RGB", (100, 100), (0, 0, 255)), (0, 100))
    # Quadrante inferior direito: Amarelo
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
        output_format="png"
    )

    assert len(generated) == 4
    for f in generated:
        assert f.is_file()
        assert f.stat().st_size > 0

    # Abre cada fatia e valida dimensões e cores
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

    # Reconstrução da imagem completa a partir dos arquivos salvos
    reconstructed = Image.new("RGB", (200, 200))
    with Image.open(generated[0]) as t1:
        reconstructed.paste(t1, (0, 0))
    with Image.open(generated[1]) as t2:
        reconstructed.paste(t2, (100, 0))
    with Image.open(generated[2]) as t3:
        reconstructed.paste(t3, (0, 100))
    with Image.open(generated[3]) as t4:
        reconstructed.paste(t4, (100, 100))

    # Comprova que a diferença de pixels é zero
    diff = ImageChops.difference(base, reconstructed)
    assert diff.getbbox() is None

    # Falha se arquivo de origem não existe
    with pytest.raises(FileNotFoundError):
        split_image_file(tmp_path / "nao_existe.png", out_dir)
