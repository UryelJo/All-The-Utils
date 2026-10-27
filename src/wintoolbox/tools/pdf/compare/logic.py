"""
Lógica pura para comparação diferencial entre duas versões de documentos PDF.
Analisa similaridade de texto, diferenças linha a linha e páginas alteradas.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
import difflib
from pathlib import Path
from typing import Any, Dict, List, Optional
import pypdf


def compare_pdf_documents(pdf_a_path: Path, pdf_b_path: Path) -> Dict[str, Any]:
    """
    Compara dois arquivos PDF e retorna um relatório comparativo detalhado por página.
    """
    pdf_a_path = Path(pdf_a_path).resolve()
    pdf_b_path = Path(pdf_b_path).resolve()

    if not pdf_a_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF A não encontrado: {pdf_a_path}")
    if not pdf_b_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF B não encontrado: {pdf_b_path}")

    reader_a = pypdf.PdfReader(pdf_a_path)
    reader_b = pypdf.PdfReader(pdf_b_path)

    pages_a_count = len(reader_a.pages)
    pages_b_count = len(reader_b.pages)
    max_pages = max(pages_a_count, pages_b_count)

    pages_comparison: List[Dict[str, Any]] = []
    identical_count = 0
    modified_count = 0

    for idx in range(max_pages):
        page_num = idx + 1
        text_a = reader_a.pages[idx].extract_text() if idx < pages_a_count else None
        text_b = reader_b.pages[idx].extract_text() if idx < pages_b_count else None

        if text_a is None:
            # Página adicionada exclusivamente no PDF B
            pages_comparison.append({
                "page": page_num,
                "status": "APENAS_NO_B",
                "similarity": 0.0,
                "diff_lines": [f"+ {l}" for l in (text_b or "").splitlines()],
                "text_a": "",
                "text_b": text_b or "",
            })
            modified_count += 1
        elif text_b is None:
            # Página removida no PDF B
            pages_comparison.append({
                "page": page_num,
                "status": "APENAS_NO_A",
                "similarity": 0.0,
                "diff_lines": [f"- {l}" for l in text_a.splitlines()],
                "text_a": text_a,
                "text_b": "",
            })
            modified_count += 1
        else:
            matcher = difflib.SequenceMatcher(None, text_a, text_b)
            similarity = round(matcher.ratio(), 4)

            lines_a = text_a.splitlines()
            lines_b = text_b.splitlines()

            diff_generator = difflib.unified_diff(
                lines_a,
                lines_b,
                fromfile=f"PDF A - Pág {page_num}",
                tofile=f"PDF B - Pág {page_num}",
                lineterm="",
            )
            diff_lines = list(diff_generator)

            if similarity == 1.0 or not diff_lines:
                status = "IDENTICO"
                identical_count += 1
            else:
                status = "MODIFICADO"
                modified_count += 1

            pages_comparison.append({
                "page": page_num,
                "status": status,
                "similarity": similarity,
                "diff_lines": diff_lines,
                "text_a": text_a,
                "text_b": text_b,
            })

    return {
        "pdf_a_name": pdf_a_path.name,
        "pdf_b_name": pdf_b_path.name,
        "pages_a": pages_a_count,
        "pages_b": pages_b_count,
        "total_pages_compared": max_pages,
        "identical_pages": identical_count,
        "modified_pages": modified_count,
        "pages": pages_comparison,
    }
