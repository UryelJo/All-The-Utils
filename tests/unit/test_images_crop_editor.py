"""
Testes unitários rigorosos para a lógica de images.crop_editor.

Segue as diretrizes Anti-Gambiarra com validação de efeito real,
abertura de arquivos gerados e conferência de dimensões determinísticas.
"""
from pathlib import Path
import pytest
from PIL import Image

from wintoolbox.tools.images.crop_editor.logic import (
    apply_crop_and_rotation,
    calculate_aspect_box,
    process_image_file,
)


def test_calculate_aspect_box_deterministic():
    """Valida cálculo de caixas para proporções padrão."""
    # 1:1 em imagem 1000x1000 com margem 0.9 -> caixa 900x900 centrada
    box = calculate_aspect_box(1000, 1000, (1, 1), margin_ratio=0.9)
    assert box == (50, 50, 950, 950)

    # 16:9 em imagem 1920x1080 com margem 1.0 -> 1920x1080 completo
    box_16_9 = calculate_aspect_box(1920, 1080, (16, 9), margin_ratio=1.0)
    assert box_16_9 == (0, 0, 1920, 1080)

    # Livre (None) em 800x600 com margem 0.8 -> 640x480 centrado
    box_free = calculate_aspect_box(800, 600, None, margin_ratio=0.8)
    assert box_free == (80, 60, 720, 540)

    # Erro em dimensões inválidas
    with pytest.raises(ValueError, match="positivas"):
        calculate_aspect_box(0, 100, (1, 1))


def test_apply_crop_and_rotation_real_effect(tmp_path: Path):
    """Valida que o recorte corta as dimensões exatas e a rotação preserva o modo."""
    img = Image.new("RGBA", (200, 200), (255, 0, 0, 255))
    cropped = apply_crop_and_rotation(img, (20, 30, 120, 150), rotation_angle=0.0)

    # Largura: 120 - 20 = 100, Altura: 150 - 30 = 120
    assert cropped.size == (100, 120)
    assert cropped.mode == "RGBA"

    # Teste de rotação
    rotated_cropped = apply_crop_and_rotation(img, (10, 10, 90, 90), rotation_angle=15.0)
    assert rotated_cropped.size == (80, 80)


def test_process_image_file_black_box(tmp_path: Path):
    """Valida o efeito real de gravação em disco e reabertura com leitor PIL."""
    src = tmp_path / "original.png"
    dst = tmp_path / "recortada.png"

    img = Image.new("RGB", (400, 300), color=(0, 128, 255))
    img.save(src)

    out = process_image_file(src, dst, (50, 50, 250, 150), rotation_angle=0.0)
    assert out.is_file()

    # Black-Box: abre o arquivo resultante e valida os dados
    with Image.open(out) as result_img:
        assert result_img.size == (200, 100)
        # Amostra de pixel central deve ser azul
        assert result_img.getpixel((100, 50)) == (0, 128, 255)


def test_process_image_file_not_found(tmp_path: Path):
    """Cenário de falha: arquivo de origem inexistente deve disparar FileNotFoundError."""
    src = tmp_path / "inexistente.jpg"
    dst = tmp_path / "saida.jpg"
    with pytest.raises(FileNotFoundError):
        process_image_file(src, dst, (0, 0, 50, 50))
