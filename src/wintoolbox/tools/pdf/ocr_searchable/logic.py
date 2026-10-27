"""
Lógica pura para conversão de PDFs digitalizados (scans/imagens) em PDFs pesquisáveis (Searchable PDF).
Combina reconhecimento óptico de caracteres (OCR) com geração de camadas de texto invisíveis/pesquisáveis
compatíveis com Adobe Acrobat, Foxit, navegadores e indexadores do Windows.

Zero dependências de interface gráfica.
"""
import io
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Dict, List, Optional
from PIL import Image
import pypdf
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas

from wintoolbox.tools.images.ocr.logic import perform_ocr_on_image


def create_searchable_page_pdf(
    image: Image.Image,
    recognized_text: str,
    output_pdf_path: Path,
) -> None:
    """
    Gera um PDF de página única onde a imagem de fundo é desenhada e o texto
    reconhecido por OCR é embutido em camada transparente/pesquisável sobreposta.
    """
    img_width, img_height = image.size

    # Salva a imagem em buffer temporário PNG
    img_bytes_io = io.BytesIO()
    image.save(img_bytes_io, format="PNG")
    img_bytes_io.seek(0)

    # Cria canvas reportlab com o tamanho exato da imagem em pontos
    c = canvas.Canvas(str(output_pdf_path), pagesize=(img_width, img_height))

    # Desenha a imagem de fundo original
    from reportlab.lib.utils import ImageReader
    reader = ImageReader(img_bytes_io)
    c.drawImage(reader, 0, 0, width=img_width, height=img_height)

    # Sobrepõe o texto com cor invisível (alpha = 0) para permitir busca (Ctrl+F) e seleção
    if recognized_text:
        c.setFillColor(Color(0, 0, 0, alpha=0.0))
        c.setFont("Helvetica", 11)

        lines = recognized_text.splitlines()
        # Inicia do topo da página e desce linha por linha
        y_pos = img_height - 20
        line_height = 14

        for line in lines:
            cleaned_line = line.strip()
            if cleaned_line and y_pos > 10:
                # Sanitiza caracteres que possam quebrar a fonte padrão
                safe_line = cleaned_line.encode("latin-1", "replace").decode("latin-1")
                c.drawString(20, y_pos, safe_line)
                y_pos -= line_height

    c.save()


def convert_scanned_pdf_to_searchable(
    input_file: Path,
    output_pdf_path: Path,
    ocr_fn: Optional[Callable[[Image.Image], str]] = None,
) -> Dict[str, Any]:
    """
    Converte um documento PDF digitalizado ou arquivo de imagem em um Searchable PDF completo.
    """
    src = Path(input_file).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Arquivo de origem não encontrado: {src}")

    out_pdf = Path(output_pdf_path).resolve()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    ocr_runner = ocr_fn or (lambda img: _default_ocr_on_pil(img))

    pages_text: List[str] = []
    temp_page_pdfs: List[Path] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)

        # Se a entrada for imagem direta (PNG, JPEG, etc.)
        if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"):
            with Image.open(src) as img:
                img_rgb = img.convert("RGB")
                text = ocr_runner(img_rgb)
                pages_text.append(text)

                page_pdf = tmp_dir_path / "page_0.pdf"
                create_searchable_page_pdf(img_rgb, text, page_pdf)
                temp_page_pdfs.append(page_pdf)

        else:
            # Entrada é um PDF existente
            reader = pypdf.PdfReader(str(src))
            for page_idx, page in enumerate(reader.pages):
                # Tenta extrair imagem embutida na página ou gera imagem básica
                page_img = None
                if page.images:
                    # Pega a primeira imagem de fundo da página
                    img_data = page.images[0]
                    page_img = Image.open(io.BytesIO(img_data.data)).convert("RGB")
                else:
                    # Se não possui imagem direta, cria canvas em branco de 595x842 (A4)
                    page_img = Image.new("RGB", (595, 842), color=(255, 255, 255))

                text = ocr_runner(page_img)
                pages_text.append(text)

                page_pdf = tmp_dir_path / f"page_{page_idx}.pdf"
                create_searchable_page_pdf(page_img, text, page_pdf)
                temp_page_pdfs.append(page_pdf)

        # Junta todas as páginas geradas em um único PDF final
        writer = pypdf.PdfWriter()
        for p_pdf in temp_page_pdfs:
            p_reader = pypdf.PdfReader(str(p_pdf))
            for p in p_reader.pages:
                writer.add_page(p)

        with open(out_pdf, "wb") as f_out:
            writer.write(f_out)

    total_words = sum(len(txt.split()) for txt in pages_text)

    return {
        "output_path": str(out_pdf),
        "total_pages": len(pages_text),
        "total_words": total_words,
        "extracted_text": "\n\n--- Página ---\n\n".join(pages_text),
    }


def _default_ocr_on_pil(img: Image.Image) -> str:
    """Executa o OCR padrão do WinToolbox salvando em arquivo temporário."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        img.save(tmp_path, format="PNG")
        res = perform_ocr_on_image(tmp_path)
        return res.get("text", "") if isinstance(res, dict) else str(res)
    finally:
        tmp_path.unlink(missing_ok=True)
