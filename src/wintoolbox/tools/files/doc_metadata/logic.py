"""
Lógica pura para inspeção e higienização/remoção de metadados em lote de documentos
de escritório (Microsoft Word .docx, Excel .xlsx, PowerPoint .pptx e PDF).

Zero dependências de interface gráfica ou widgets.
"""
from pathlib import Path
import re
import shutil
from typing import Any, Dict, Optional
import xml.etree.ElementTree as ET
import zipfile
import pypdf


def inspect_office_xml(file_path: str) -> Dict[str, Any]:
    """Inspeciona metadados de arquivos Office Open XML (.docx, .xlsx, .pptx)."""
    meta: Dict[str, Any] = {
        "author": "",
        "last_modified_by": "",
        "title": "",
        "subject": "",
        "company": "",
        "created": "",
        "modified": "",
        "raw_properties": {},
    }

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            # docProps/core.xml
            if "docProps/core.xml" in zf.namelist():
                xml_data = zf.read("docProps/core.xml")
                root = ET.fromstring(xml_data)
                for elem in root:
                    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    text = elem.text or ""
                    meta["raw_properties"][tag] = text
                    if tag == "creator":
                        meta["author"] = text
                    elif tag == "lastModifiedBy":
                        meta["last_modified_by"] = text
                    elif tag == "title":
                        meta["title"] = text
                    elif tag == "subject":
                        meta["subject"] = text
                    elif tag == "created":
                        meta["created"] = text
                    elif tag == "modified":
                        meta["modified"] = text

            # docProps/app.xml
            if "docProps/app.xml" in zf.namelist():
                xml_data = zf.read("docProps/app.xml")
                root = ET.fromstring(xml_data)
                for elem in root:
                    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    text = elem.text or ""
                    meta["raw_properties"][tag] = text
                    if tag == "Company":
                        meta["company"] = text
    except Exception:
        pass

    return meta


def strip_office_xml(file_path: str, output_path: str) -> bool:
    """
    Remove metadados pessoais de arquivos Office Open XML (.docx, .xlsx, .pptx).
    Sobrescreve docProps/core.xml e docProps/app.xml com versões limpas.
    """
    clean_core_xml = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        b'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        b'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
        b'<dc:title></dc:title>\n'
        b'<dc:creator></dc:creator>\n'
        b'<cp:lastModifiedBy></cp:lastModifiedBy>\n'
        b'</cp:coreProperties>'
    )

    clean_app_xml = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">\n'
        b'<Company></Company>\n'
        b'</Properties>'
    )

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(file_path, "r") as zin:
        with zipfile.ZipFile(output_path, "w", compression=zin.compression) as zout:
            for item in zin.infolist():
                if item.filename == "docProps/core.xml":
                    zout.writestr(item, clean_core_xml)
                elif item.filename == "docProps/app.xml":
                    zout.writestr(item, clean_app_xml)
                else:
                    zout.writestr(item, zin.read(item.filename))

    return True


def inspect_pdf_metadata(file_path: str) -> Dict[str, Any]:
    """Inspeciona metadados de arquivos PDF."""
    meta: Dict[str, Any] = {
        "author": "",
        "creator": "",
        "producer": "",
        "title": "",
        "subject": "",
        "creation_date": "",
        "mod_date": "",
    }
    try:
        reader = pypdf.PdfReader(file_path)
        doc_info = reader.metadata
        if doc_info:
            meta["author"] = str(doc_info.get("/Author", "") or "")
            meta["creator"] = str(doc_info.get("/Creator", "") or "")
            meta["producer"] = str(doc_info.get("/Producer", "") or "")
            meta["title"] = str(doc_info.get("/Title", "") or "")
            meta["subject"] = str(doc_info.get("/Subject", "") or "")
            meta["creation_date"] = str(doc_info.get("/CreationDate", "") or "")
            meta["mod_date"] = str(doc_info.get("/ModDate", "") or "")
    except Exception:
        pass

    return meta


def strip_pdf_metadata(file_path: str, output_path: str) -> bool:
    """Higieniza documento PDF expurgando metadados de autoria."""
    reader = pypdf.PdfReader(file_path)
    writer = pypdf.PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    # Define metadados vazios/anônimos
    writer.add_metadata({})

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)

    return True


def inspect_document(file_path: str) -> Dict[str, Any]:
    """Inspeciona metadados de qualquer documento de escritório suportado."""
    ext = Path(file_path).suffix.lower()
    if ext in (".docx", ".xlsx", ".pptx"):
        data = inspect_office_xml(file_path)
        data["format"] = f"Office Open XML ({ext})"
        return data
    elif ext == ".pdf":
        data = inspect_pdf_metadata(file_path)
        data["format"] = "PDF Document"
        return data

    return {"format": "Desconhecido", "author": ""}


def clean_document(file_path: str, output_path: str) -> bool:
    """Higieniza metadados do documento salvando na saída."""
    ext = Path(file_path).suffix.lower()
    if ext in (".docx", ".xlsx", ".pptx"):
        return strip_office_xml(file_path, output_path)
    elif ext == ".pdf":
        return strip_pdf_metadata(file_path, output_path)

    # Fallback copia
    shutil.copy2(file_path, output_path)
    return True
