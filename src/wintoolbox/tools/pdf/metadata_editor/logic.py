"""
Lógica pura para leitura, edição e higienização/anonimização de metadados em arquivos PDF.
Compatível com especificações ISO 32000-1 (PDF Standard Document Information Dictionary).

Zero dependências de interface gráfica.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pypdf


def read_pdf_metadata(pdf_path: Path) -> Dict[str, Any]:
    """
    Lê os metadados padrão do PDF e retorna um dicionário estruturado.
    """
    path = Path(pdf_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {path}")

    reader = pypdf.PdfReader(str(path))
    meta = reader.metadata

    if not meta:
        return {
            "title": "",
            "author": "",
            "subject": "",
            "keywords": "",
            "creator": "",
            "producer": "",
            "creation_date": "",
            "mod_date": "",
            "total_pages": len(reader.pages),
        }

    return {
        "title": meta.title or "",
        "author": meta.author or "",
        "subject": meta.subject or "",
        "keywords": meta.get("/Keywords", "") or "",
        "creator": meta.creator or "",
        "producer": meta.producer or "",
        "creation_date": str(meta.get("/CreationDate", "") or ""),
        "mod_date": str(meta.get("/ModDate", "") or ""),
        "total_pages": len(reader.pages),
    }


def update_pdf_metadata(
    pdf_path: Path,
    output_path: Path,
    new_metadata: Optional[Dict[str, Optional[str]]] = None,
    clean_all: bool = False,
) -> Dict[str, Any]:
    """
    Grava um novo PDF com metadados atualizados ou completamente higienizados (clean_all=True).
    """
    src = Path(pdf_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {src}")

    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(str(src))
    writer = pypdf.PdfWriter()

    # Copia todas as páginas
    for page in reader.pages:
        writer.add_page(page)

    if clean_all:
        # Higienização de privacidade: remove todos os metadados
        writer.add_metadata({})
    else:
        meta_dict: Dict[str, str] = {}
        # Preserva metadados anteriores se não alterados
        old_meta = reader.metadata or {}
        key_mapping = {
            "title": "/Title",
            "author": "/Author",
            "subject": "/Subject",
            "keywords": "/Keywords",
            "creator": "/Creator",
            "producer": "/Producer",
        }

        for attr, pdf_key in key_mapping.items():
            if new_metadata and attr in new_metadata:
                val = new_metadata[attr]
                if val is not None:
                    meta_dict[pdf_key] = val
            elif pdf_key in old_meta and old_meta[pdf_key]:
                meta_dict[pdf_key] = str(old_meta[pdf_key])

        now_str = datetime.now().strftime("D:%Y%m%d%H%M%S")
        meta_dict["/ModDate"] = now_str
        writer.add_metadata(meta_dict)

    with open(out, "wb") as f_out:
        writer.write(f_out)

    return {
        "output_path": str(out),
        "file_size": out.stat().st_size,
        "clean_all": clean_all,
    }


def batch_sanitize_metadata(
    pdf_files: List[Path],
    output_dir: Path,
) -> List[Dict[str, Any]]:
    """
    Higieniza em lote múltiplos PDFs removendo todos os metadados de rastreamento.
    """
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []

    for pdf in pdf_files:
        src = Path(pdf)
        dest = out_dir / f"limpo_{src.name}"
        try:
            res = update_pdf_metadata(src, dest, clean_all=True)
            results.append({
                "status": "OK",
                "filename": src.name,
                "output_path": str(dest),
                "error": None,
            })
        except Exception as exc:
            results.append({
                "status": "ERRO",
                "filename": src.name,
                "output_path": "-",
                "error": str(exc),
            })

    return results
