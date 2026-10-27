"""
Lógica pura para conversão bidirecional entre XML e JSON.
Trata atributos XML (prefixo @), texto misto (#text), listas aninhadas,
namespaces e indentação semântica elegante.

Zero dependências de interface gráfica.
"""
import json
from typing import Any, Dict, List, Optional, Union
import xml.etree.ElementTree as ET


def _element_to_dict(elem: ET.Element, attr_prefix: str = "@", text_key: str = "#text") -> Any:
    """
    Converte recursivamente um elemento XML em dicionário Python ou valor primitivo.
    """
    res: Dict[str, Any] = {}

    # Adiciona atributos
    for attr_name, attr_val in elem.attrib.items():
        res[f"{attr_prefix}{attr_name}"] = attr_val

    # Adiciona filhos
    children = list(elem)
    if children:
        child_dict: Dict[str, List[Any]] = {}
        for child in children:
            tag = child.tag
            # Remove namespace se presente: {uri}tag -> tag
            if "}" in tag:
                tag = tag.split("}", 1)[1]

            val = _element_to_dict(child, attr_prefix=attr_prefix, text_key=text_key)
            if tag not in child_dict:
                child_dict[tag] = []
            child_dict[tag].append(val)

        for tag, items in child_dict.items():
            if len(items) == 1:
                res[tag] = items[0]
            else:
                res[tag] = items

    # Texto do nó
    text = (elem.text or "").strip()
    if text:
        if not res:
            # Se não há atributos nem filhos, retorna diretamente o texto
            return text
        else:
            res[text_key] = text

    return res if res else ""


def xml_to_dict(xml_str: str, attr_prefix: str = "@", text_key: str = "#text") -> Dict[str, Any]:
    """
    Converte uma string XML em um dicionário Python estruturado.
    """
    cleaned = xml_str.strip()
    if not cleaned:
        raise ValueError("O XML de entrada está vazio.")

    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError as exc:
        raise ValueError(f"Erro de sintaxe no XML: {exc}") from exc

    tag = root.tag
    if "}" in tag:
        tag = tag.split("}", 1)[1]

    return {tag: _element_to_dict(root, attr_prefix=attr_prefix, text_key=text_key)}


def xml_to_json(xml_str: str, indent: int = 2) -> str:
    """
    Converte diretamente uma string XML em JSON formatado.
    """
    d = xml_to_dict(xml_str)
    return json.dumps(d, indent=indent, ensure_ascii=False)


def _dict_to_element(
    tag: str,
    data: Any,
    attr_prefix: str = "@",
    text_key: str = "#text",
) -> ET.Element:
    """
    Converte recursivamente um nó de dicionário ou lista em elemento XML.
    """
    elem = ET.Element(tag)

    if isinstance(data, dict):
        for k, v in data.items():
            if k.startswith(attr_prefix):
                attr_name = k[len(attr_prefix):]
                elem.set(attr_name, str(v))
            elif k == text_key:
                elem.text = str(v)
            elif isinstance(v, list):
                for item in v:
                    elem.append(_dict_to_element(k, item, attr_prefix=attr_prefix, text_key=text_key))
            else:
                elem.append(_dict_to_element(k, v, attr_prefix=attr_prefix, text_key=text_key))
    elif isinstance(data, list):
        for item in data:
            elem.append(_dict_to_element("item", item, attr_prefix=attr_prefix, text_key=text_key))
    else:
        elem.text = str(data)

    return elem


def dict_to_xml(
    data: Dict[str, Any],
    root_name: Optional[str] = None,
    attr_prefix: str = "@",
    text_key: str = "#text",
    include_declaration: bool = True,
) -> str:
    """
    Converte um dicionário Python em XML formatado com indentação.
    """
    if not data:
        raise ValueError("Os dados de entrada para o XML estão vazios.")

    if len(data) == 1 and not root_name:
        root_tag = list(data.keys())[0]
        root_val = data[root_tag]
        root_elem = _dict_to_element(root_tag, root_val, attr_prefix=attr_prefix, text_key=text_key)
    else:
        root_tag = root_name or "root"
        root_elem = _dict_to_element(root_tag, data, attr_prefix=attr_prefix, text_key=text_key)

    ET.indent(root_elem, space="  ")
    xml_body = ET.tostring(root_elem, encoding="utf-8").decode("utf-8")

    if include_declaration:
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_body
    return xml_body


def json_to_xml(
    json_str: str,
    root_name: Optional[str] = None,
    include_declaration: bool = True,
) -> str:
    """
    Converte diretamente uma string JSON para XML formatado.
    """
    cleaned = json_str.strip()
    if not cleaned:
        raise ValueError("O JSON de entrada está vazio.")

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Erro de sintaxe no JSON: {exc}") from exc

    if not isinstance(data, dict):
        data = {"root": data}

    return dict_to_xml(data, root_name=root_name, include_declaration=include_declaration)
