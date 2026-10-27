"""
Testes unitários e de validação de efeito real para pdf.form_filler.
"""
import json
from pathlib import Path
import pypdf
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from wintoolbox.tools.pdf.form_filler.logic import (
    get_pdf_form_fields,
    fill_pdf_form,
    export_form_values_json,
)


def _create_interactive_pdf_form(path: Path) -> None:
    """Cria programaticamente um PDF válido contendo formulário AcroForm."""
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=595, height=842)

    # Cria campo de texto
    field = DictionaryObject({
        NameObject("/FT"): NameObject("/Tx"),
        NameObject("/T"): TextStringObject("nome_cliente"),
        NameObject("/V"): TextStringObject(""),
        NameObject("/Rect"): ArrayObject([
            NumberObject(100),
            NumberObject(700),
            NumberObject(300),
            NumberObject(720),
        ]),
        NameObject("/Subtype"): NameObject("/Widget"),
    })

    field_ref = writer._add_object(field)

    # Cria AcroForm no catálogo
    acro_form = DictionaryObject({
        NameObject("/Fields"): ArrayObject([field_ref]),
    })
    writer._root_object.update({NameObject("/AcroForm"): writer._add_object(acro_form)})
    page[NameObject("/Annots")] = ArrayObject([field_ref])

    with open(path, "wb") as f:
        writer.write(f)


def test_form_filler_read_and_fill(tmp_path: Path):
    """Testa leitura de campos e preenchimento com achatamento (flatten)."""
    form_in = tmp_path / "formulario.pdf"
    form_out = tmp_path / "formulario_preenchido.pdf"
    json_out = tmp_path / "dados.json"

    _create_interactive_pdf_form(form_in)

    # 1. Lê campos
    fields = get_pdf_form_fields(form_in)
    assert len(fields) == 1
    assert fields[0]["name"] == "nome_cliente"
    assert fields[0]["type"] == "Texto"

    # 2. Preenche campos
    fill_data = {"nome_cliente": "Carlos Eduardo Pereira"}
    fill_pdf_form(form_in, fill_data, form_out, flatten=True)

    assert form_out.is_file()

    # Validação do efeito real no disco
    reader = pypdf.PdfReader(form_out)
    assert len(reader.pages) == 1

    # 3. Testa exportação JSON
    export_form_values_json(fill_data, json_out)
    assert json_out.is_file()
    loaded = json.loads(json_out.read_text(encoding="utf-8"))
    assert loaded["nome_cliente"] == "Carlos Eduardo Pereira"
