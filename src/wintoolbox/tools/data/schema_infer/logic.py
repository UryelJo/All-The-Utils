"""
Lógica pura para inferência automática de esquemas e modelos de tipagem a partir de dados JSON.
Gera JSON Schema (Draft 7/2020), contratos Pydantic v2, Python Dataclasses e interfaces TypeScript.

Zero dependências de interface gráfica ou widgets.
"""
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple


def _sanitize_identifier(name: str) -> str:
    """Sanitiza string para identificador de código válido."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if not clean or clean[0].isdigit():
        clean = f"item_{clean}"
    return clean


def _to_pascal_case(name: str) -> str:
    """Converte nome para PascalCase (ex: 'itens_pedido' -> 'ItensPedido')."""
    words = re.split(r"[_\s\-]+", name)
    return "".join(w.capitalize() for w in words if w) or "Model"


def infer_json_schema(data: Any, title: str = "RootSchema") -> Dict[str, Any]:
    """
    Infere um JSON Schema a partir de um dado de exemplo.
    """
    def _infer_node(node: Any) -> Dict[str, Any]:
        if node is None:
            return {"type": "null"}
        if isinstance(node, bool):
            return {"type": "boolean"}
        if isinstance(node, int):
            return {"type": "integer"}
        if isinstance(node, float):
            return {"type": "number"}
        if isinstance(node, str):
            return {"type": "string"}
        if isinstance(node, list):
            if not node:
                return {"type": "array", "items": {}}
            # Unifica esquemas dos itens do array
            item_schema = _infer_node(node[0])
            return {"type": "array", "items": item_schema}
        if isinstance(node, dict):
            props = {}
            required = []
            for k, v in node.items():
                props[str(k)] = _infer_node(v)
                required.append(str(k))
            return {
                "type": "object",
                "properties": props,
                "required": required,
            }
        return {"type": "string"}

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": title,
    }
    schema.update(_infer_node(data))
    return schema


def generate_pydantic_v2(data: Any, root_name: str = "RootModel") -> str:
    """
    Gera código Python Pydantic v2 a partir de uma estrutura JSON.
    """
    models: List[str] = []
    generated_names: Set[str] = set()

    def _type_for_value(val: Any, field_name: str) -> str:
        if val is None:
            return "Optional[Any]"
        if isinstance(val, bool):
            return "bool"
        if isinstance(val, int):
            return "int"
        if isinstance(val, float):
            return "float"
        if isinstance(val, str):
            return "str"
        if isinstance(val, list):
            if not val:
                return "List[Any]"
            elem_type = _type_for_value(val[0], f"{field_name}_item")
            return f"List[{elem_type}]"
        if isinstance(val, dict):
            sub_model_name = _to_pascal_case(field_name)
            if sub_model_name not in generated_names:
                _build_model(val, sub_model_name)
            return sub_model_name
        return "Any"

    def _build_model(d: Dict[str, Any], class_name: str) -> None:
        generated_names.add(class_name)
        lines = [f"class {class_name}(BaseModel):"]
        if not d:
            lines.append("    pass")
        else:
            for k, v in d.items():
                ident = _sanitize_identifier(k)
                field_type = _type_for_value(v, k)
                if ident != k:
                    lines.append(f'    {ident}: {field_type} = Field(alias="{k}")')
                else:
                    lines.append(f"    {ident}: {field_type}")
        models.append("\n".join(lines))

    if isinstance(data, dict):
        _build_model(data, root_name)
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        item_name = f"{root_name}Item"
        _build_model(data[0], item_name)
        models.append(f"class {root_name}(RootModel[List[{item_name}]]):\n    pass")
    else:
        models.append(f"class {root_name}(RootModel[Any]):\n    pass")

    header = (
        "from typing import Any, List, Optional\n"
        "from pydantic import BaseModel, Field, RootModel\n\n"
    )
    # Coloca os modelos em ordem de dependência (filhos primeiro)
    return header + "\n\n\n".join(models) + "\n"


def generate_dataclass(data: Any, root_name: str = "RootData") -> str:
    """
    Gera código Python com @dataclass a partir de uma estrutura JSON.
    """
    models: List[str] = []
    generated_names: Set[str] = set()

    def _type_for_value(val: Any, field_name: str) -> str:
        if val is None:
            return "Optional[Any]"
        if isinstance(val, bool):
            return "bool"
        if isinstance(val, int):
            return "int"
        if isinstance(val, float):
            return "float"
        if isinstance(val, str):
            return "str"
        if isinstance(val, list):
            if not val:
                return "List[Any]"
            elem_type = _type_for_value(val[0], f"{field_name}_item")
            return f"List[{elem_type}]"
        if isinstance(val, dict):
            sub_model_name = _to_pascal_case(field_name)
            if sub_model_name not in generated_names:
                _build_dataclass(val, sub_model_name)
            return sub_model_name
        return "Any"

    def _build_dataclass(d: Dict[str, Any], class_name: str) -> None:
        generated_names.add(class_name)
        lines = ["@dataclass", f"class {class_name}:"]
        if not d:
            lines.append("    pass")
        else:
            for k, v in d.items():
                ident = _sanitize_identifier(k)
                field_type = _type_for_value(v, k)
                if isinstance(v, list):
                    lines.append(f"    {ident}: {field_type} = field(default_factory=list)")
                elif isinstance(v, dict):
                    lines.append(f"    {ident}: {field_type} = field(default_factory={field_type})")
                elif v is None:
                    lines.append(f"    {ident}: {field_type} = None")
                else:
                    lines.append(f"    {ident}: {field_type} = {repr(v)}")
        models.append("\n".join(lines))

    if isinstance(data, dict):
        _build_dataclass(data, root_name)
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        item_name = f"{root_name}Item"
        _build_dataclass(data[0], item_name)
        models.append(f"{root_name} = List[{item_name}]")
    else:
        models.append(f"@dataclass\nclass {root_name}:\n    valor: Any = None")

    header = (
        "from dataclasses import dataclass, field\n"
        "from typing import Any, List, Optional\n\n"
    )
    return header + "\n\n\n".join(models) + "\n"


def generate_typescript(data: Any, root_name: str = "RootObject") -> str:
    """
    Gera código TypeScript (interfaces) a partir de uma estrutura JSON.
    """
    interfaces: List[str] = []
    generated_names: Set[str] = set()

    def _ts_type(val: Any, field_name: str) -> str:
        if val is None:
            return "any | null"
        if isinstance(val, bool):
            return "boolean"
        if isinstance(val, (int, float)):
            return "number"
        if isinstance(val, str):
            return "string"
        if isinstance(val, list):
            if not val:
                return "any[]"
            elem_type = _ts_type(val[0], f"{field_name}_item")
            return f"{elem_type}[]"
        if isinstance(val, dict):
            sub_name = _to_pascal_case(field_name)
            if sub_name not in generated_names:
                _build_interface(val, sub_name)
            return sub_name
        return "any"

    def _build_interface(d: Dict[str, Any], iface_name: str) -> None:
        generated_names.add(iface_name)
        lines = [f"export interface {iface_name} {{"]
        for k, v in d.items():
            t = _ts_type(v, k)
            ident = k if re.match(r"^[a-zA-Z_$][a-zA-Z0-9_$]*$", k) else f'"{k}"'
            lines.append(f"  {ident}: {t};")
        lines.append("}")
        interfaces.append("\n".join(lines))

    if isinstance(data, dict):
        _build_interface(data, root_name)
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        item_name = f"{root_name}Item"
        _build_interface(data[0], item_name)
        interfaces.append(f"export type {root_name} = {item_name}[];")
    else:
        interfaces.append(f"export type {root_name} = any;")

    return "\n\n".join(interfaces) + "\n"
