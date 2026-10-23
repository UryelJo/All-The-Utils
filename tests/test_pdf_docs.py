"""
Testes unitários e de integração para as ferramentas da Fase 4: PDF e Documentos.
Valida criação, divisão, junção, rotação, compressão, proteção, extração e conversão de Markdown.
"""
from pathlib import Path
import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter

from wintoolbox.tools.pdf.split_merge.logic import (
    get_pdf_info, merge_pdfs, parse_page_ranges, split_pdf
)
from wintoolbox.tools.pdf.images_to_pdf.logic import convert_images_to_pdf
from wintoolbox.tools.pdf.extract.logic import (
    extract_images_from_pdf, extract_text_from_pdf
)
from wintoolbox.tools.pdf.compress.logic import compress_pdf_file
from wintoolbox.tools.pdf.rotate.logic import rotate_pdf
from wintoolbox.tools.pdf.security.logic import protect_pdf, unlock_pdf
from wintoolbox.tools.data.doc_converter.logic import markdown_to_html


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Cria um PDF de 3 páginas com texto para testes."""
    pdf_path = tmp_path / "teste_orig.pdf"
    writer = PdfWriter()
    for i in range(3):
        # Cria uma página em branco com anotação ou texto básico
        page = writer.add_blank_page(width=595, height=842)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


@pytest.fixture
def sample_images(tmp_path: Path) -> list[Path]:
    """Cria imagens PNG e JPG para teste de conversão em PDF."""
    imgs = []
    for i in range(2):
        img_p = tmp_path / f"img_{i}.png"
        img = Image.new("RGB", (200, 200), color=(50 * i, 100, 150))
        img.save(img_p)
        imgs.append(img_p)
    return imgs


def test_parse_page_ranges():
    # Testa "1-2, 3" em PDF de 5 páginas
    ranges = parse_page_ranges("1-2, 4", 5)
    assert ranges == [[0, 1], [3]]

    # Limites inválidos ou em branco
    assert parse_page_ranges("", 3) == [[0, 1, 2]]


def test_pdf_info_and_split_all(sample_pdf: Path, tmp_path: Path):
    info = get_pdf_info(sample_pdf)
    assert info["pages"] == 3
    assert info["is_encrypted"] is False

    # Divide todas as páginas individuais
    out_dir = tmp_path / "split_all"
    generated = split_pdf(sample_pdf, out_dir, split_mode="all")
    assert len(generated) == 3
    for p in generated:
        assert p.is_file()
        reader = PdfReader(str(p))
        assert len(reader.pages) == 1


def test_pdf_split_range_and_each_n(sample_pdf: Path, tmp_path: Path):
    out_dir_range = tmp_path / "split_range"
    gen_range = split_pdf(sample_pdf, out_dir_range, split_mode="range", range_str="1-2, 3")
    assert len(gen_range) == 2

    reader1 = PdfReader(str(gen_range[0]))
    assert len(reader1.pages) == 2
    reader2 = PdfReader(str(gen_range[1]))
    assert len(reader2.pages) == 1

    out_dir_each = tmp_path / "split_each"
    gen_each = split_pdf(sample_pdf, out_dir_each, split_mode="each_n", each_n=2)
    assert len(gen_each) == 2  # páginas 1-2 e página 3


def test_pdf_merge(sample_pdf: Path, tmp_path: Path):
    out_dir = tmp_path / "merge_split"
    parts = split_pdf(sample_pdf, out_dir, split_mode="all")

    merged_out = tmp_path / "merged_final.pdf"
    merge_pdfs(parts, merged_out, add_bookmarks=True)
    assert merged_out.is_file()

    reader = PdfReader(str(merged_out))
    assert len(reader.pages) == 3


def test_images_to_pdf(sample_images: list[Path], tmp_path: Path):
    out_pdf = tmp_path / "fotos_doc.pdf"
    res = convert_images_to_pdf(sample_images, out_pdf, page_size_name="A4", orientation="portrait")
    assert res.is_file()

    reader = PdfReader(str(out_pdf))
    assert len(reader.pages) == 2


def test_pdf_compress(sample_pdf: Path, tmp_path: Path):
    compressed_pdf = tmp_path / "comprimido.pdf"
    res = compress_pdf_file(sample_pdf, compressed_pdf, compress_streams=True, remove_metadata=True)
    assert compressed_pdf.is_file()
    assert res["dst_size"] > 0
    assert "saved_pct" in res


def test_pdf_rotate(sample_pdf: Path, tmp_path: Path):
    rotated_pdf = tmp_path / "rotacionado.pdf"
    res = rotate_pdf(sample_pdf, rotated_pdf, angle=90, pages_mode="all")
    assert res.is_file()

    reader = PdfReader(str(rotated_pdf))
    for page in reader.pages:
        assert page.rotation == 90


def test_pdf_security_protect_and_unlock(sample_pdf: Path, tmp_path: Path):
    protected_pdf = tmp_path / "protegido.pdf"
    pwd = "MinhaSenhaSecreta123"

    # 1. Proteger
    protect_pdf(sample_pdf, protected_pdf, user_password=pwd)
    assert protected_pdf.is_file()

    reader_enc = PdfReader(str(protected_pdf))
    assert reader_enc.is_encrypted is True

    # 2. Desbloquear
    unlocked_pdf = tmp_path / "desbloqueado.pdf"
    unlock_pdf(protected_pdf, unlocked_pdf, password=pwd)
    assert unlocked_pdf.is_file()

    reader_dec = PdfReader(str(unlocked_pdf))
    assert reader_dec.is_encrypted is False
    assert len(reader_dec.pages) == 3

    # 3. Senha incorreta deve falhar
    bad_pdf = tmp_path / "bad.pdf"
    with pytest.raises(ValueError):
        unlock_pdf(protected_pdf, bad_pdf, password="SenhaErrada")


def test_doc_converter_markdown():
    md = "# Titulo Teste\n\nEste e um paragrafo com **negrito**.\n\n| Col1 | Col2 |\n| --- | --- |\n| A | B |"
    html = markdown_to_html(md, title="Teste de Markdown", full_html=True)
    assert "<!DOCTYPE html>" in html
    assert "Titulo Teste" in html
    assert "Col1" in html
    assert "Segoe UI" in html
