"""
Lógica pura para leitura, preenchimento e achatamento (flatten) de formulários PDF AcroForm.

Zero dependências de interface gráfica ou bibliotecas de widgets.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pypdf


def get_pdf_form_fields(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Inspeciona o documento PDF e retorna a lista de todos os campos interativos de formulário.
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")

    reader = pypdf.PdfReader(pdf_path)
    raw_fields = reader.get_fields() or {}

    fields_list: List[Dict[str, Any]] = []
    for name, data in raw_fields.items():
        ftype = data.get("/FT", "Desconhecido")
        if ftype == "/Tx":
            type_label = "Texto"
        elif ftype == "/Btn":
            type_label = "Botão / Seleção"
        elif ftype == "/Ch":
            type_label = "Lista de Opções"
        else:
            type_label = str(ftype)

        curr_val = data.get("/V", "")
        if curr_val is None:
            curr_val = ""

        fields_list.append({
            "name": name,
            "type": type_label,
            "value": str(curr_val),
        })

    return fields_list


def fill_pdf_form(
    pdf_path: Path,
    field_values: Dict[str, Any],
    output_pdf_path: Path,
    flatten: bool = True,
) -> Path:
    """
    Preenche os campos interativos do formulário PDF e opcionalmente achata o documento.
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")

    output_pdf_path = Path(output_pdf_path).resolve()
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(pdf_path)
    writer = pypdf.PdfWriter(clone_from=reader)

    # Aplica os valores em todas as páginas do formulário
    for page in writer.pages:
        try:
            writer.update_page_form_field_values(page, field_values)
        except Exception:
            pass

    # Se solicitado, achata o formulário tornando o documento estático
    if flatten:
        try:
            for page in writer.pages:
                if "/Annots" in page:
                    # Remove anotações interativas de formulário
                    del page["/Annots"]
        except Exception:
            pass

    with open(output_pdf_path, "wb") as f_out:
        writer.write(f_out)

    return output_pdf_path


def export_form_values_json(field_values: Dict[str, Any], output_json_path: Path) -> Path:
    """Exporta os valores de formulário preenchidos para arquivo JSON estruturado."""
    output_json_path = Path(output_json_path).resolve()
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(field_values, f, indent=2, ensure_ascii=False)
    return output_json_path
