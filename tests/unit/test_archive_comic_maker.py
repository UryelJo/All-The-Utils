"""
Testes unitários e de validação de efeito real para archive.comic_maker.
"""
from pathlib import Path
import zipfile

from wintoolbox.tools.archive.comic_maker.logic import (
    create_cbz_archive,
    extract_cbz_archive,
    natural_sort_key,
)


def test_natural_sort_key():
    """Testa se a ordenação natural coloca p2 antes de p10."""
    files = ["p10.jpg", "p2.jpg", "p1.jpg", "p20.jpg"]
    sorted_files = sorted(files, key=natural_sort_key)
    assert sorted_files == ["p1.jpg", "p2.jpg", "p10.jpg", "p20.jpg"]


def test_create_and_extract_cbz(tmp_path: Path):
    """Testa criação e extração de CBZ com validação física de dados."""
    src_folder = tmp_path / "meu_manga"
    src_folder.mkdir()

    # Cria páginas de teste fora de ordem
    (src_folder / "page_10.jpg").write_bytes(b"IMAGEM_10")
    (src_folder / "page_2.jpg").write_bytes(b"IMAGEM_2")
    (src_folder / "page_1.jpg").write_bytes(b"IMAGEM_1")

    out_cbz = tmp_path / "saida" / "meu_manga.cbz"

    created = create_cbz_archive(
        source_folder_or_files=[src_folder],
        output_cbz_path=out_cbz,
        title="Meu Manga Legal",
        issue="42",
        compress=True,
        generate_xml=True,
    )

    assert created.is_file()
    assert created.name == "meu_manga.cbz"

    # Valida estrutura interna do CBZ real via leitor zipfile
    with zipfile.ZipFile(created, "r") as zf:
        namelist = zf.namelist()
        assert "ComicInfo.xml" in namelist
        assert "page_1.jpg" in namelist
        assert "page_2.jpg" in namelist
        assert "page_10.jpg" in namelist

        # Verifica XML
        xml_text = zf.read("ComicInfo.xml").decode("utf-8")
        assert "<Title>Meu Manga Legal</Title>" in xml_text
        assert "<Number>42</Number>" in xml_text
        assert "<PageCount>3</PageCount>" in xml_text

        # Verifica ordem de gravação das páginas
        image_entries = [name for name in namelist if name.endswith(".jpg")]
        assert image_entries == ["page_1.jpg", "page_2.jpg", "page_10.jpg"]

    # Agora testa a extração de volta para pasta
    dest_dir = tmp_path / "extraido"
    extracted_folder = extract_cbz_archive(created, dest_dir)

    assert extracted_folder.is_dir()
    assert (extracted_folder / "page_1.jpg").read_bytes() == b"IMAGEM_1"
    assert (extracted_folder / "page_2.jpg").read_bytes() == b"IMAGEM_2"
    assert (extracted_folder / "page_10.jpg").read_bytes() == b"IMAGEM_10"
