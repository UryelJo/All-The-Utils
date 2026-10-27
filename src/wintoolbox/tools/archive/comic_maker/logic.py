"""
Lógica pura do Conversor de Histórias em Quadrinhos Digitais (CBZ).
Ordenação natural numérica de páginas, empacotamento CBZ e extração para imagens.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable, Dict, List, Optional
import zipfile

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}


def natural_sort_key(filename: str) -> List[Any]:
    """
    Gera chave de ordenação natural para que 'p2.jpg' venha antes de 'p10.jpg'.
    """
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split(r"(\d+)", filename)
    ]


def generate_comic_info_xml(
    title: str,
    issue: Optional[str] = None,
    page_count: int = 0,
) -> str:
    """
    Gera o conteúdo XML do manifesto ComicInfo.xml padrão do setor.
    """
    clean_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    clean_issue = (issue or "1").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
        f"  <Title>{clean_title}</Title>\n"
        f"  <Number>{clean_issue}</Number>\n"
        f"  <PageCount>{page_count}</PageCount>\n"
        "</ComicInfo>\n"
    )


def create_cbz_archive(
    source_folder_or_files: List[Path],
    output_cbz_path: Path,
    title: Optional[str] = None,
    issue: Optional[str] = None,
    compress: bool = True,
    generate_xml: bool = True,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Compacta uma lista de imagens ou pasta em um arquivo de história em quadrinhos .cbz.
    """
    image_paths: List[Path] = []
    for item in source_folder_or_files:
        p = Path(item).resolve()
        if p.is_dir():
            for root, _, files in os.walk(p):
                for f in files:
                    fp = Path(root) / f
                    if fp.suffix.lower() in IMAGE_EXTENSIONS:
                        image_paths.append(fp)
        elif p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
            image_paths.append(p)

    if not image_paths:
        raise ValueError("Nenhuma imagem válida encontrada para gerar o quadrinho CBZ.")

    # Ordenação natural das páginas
    image_paths.sort(key=lambda p: natural_sort_key(p.name))

    output_cbz_path = Path(output_cbz_path).resolve()
    output_cbz_path.parent.mkdir(parents=True, exist_ok=True)

    compression_mode = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    total = len(image_paths)

    comic_title = title or output_cbz_path.stem

    with zipfile.ZipFile(output_cbz_path, "w", compression=compression_mode) as zf:
        # Grava ComicInfo.xml se solicitado
        if generate_xml:
            xml_content = generate_comic_info_xml(
                title=comic_title,
                issue=issue or "1",
                page_count=total,
            )
            zf.writestr("ComicInfo.xml", xml_content)

        # Grava cada imagem com nome padronizado ou nome original preservado
        for idx, img_path in enumerate(image_paths):
            arcname = img_path.name
            zf.write(img_path, arcname=arcname)

            if progress_cb and total > 0:
                progress_cb(int(((idx + 1) / total) * 100))

    return output_cbz_path


def extract_cbz_archive(
    cbz_path: Path,
    output_dir: Path,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Descompacta um arquivo .cbz (ou .zip de quadrinhos) em uma pasta contendo as imagens ordenadas.
    """
    cbz_path = Path(cbz_path).resolve()
    if not cbz_path.is_file():
        raise FileNotFoundError(f"Arquivo CBZ não encontrado: {cbz_path}")

    dest_folder = (output_dir / cbz_path.stem).resolve()
    dest_folder.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(cbz_path, "r") as zf:
        members = zf.infolist()
        total = len(members)

        for idx, member in enumerate(members):
            target = (dest_folder / member.filename).resolve()
            # Proteção Zip Slip
            try:
                if not target.is_relative_to(dest_folder):
                    continue
            except AttributeError:
                if not str(target).startswith(str(dest_folder)):
                    continue

            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member, "r") as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

            if progress_cb and total > 0:
                progress_cb(int(((idx + 1) / total) * 100))

    return dest_folder
