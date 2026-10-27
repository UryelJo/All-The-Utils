"""
Testes unitários rigorosos para data.schema_infer.logic.
Validação determinística de geração de esquemas JSON, Pydantic, Dataclass e TypeScript.
"""
import pytest
from wintoolbox.tools.data.schema_infer.logic import (
    generate_dataclass,
    generate_pydantic_v2,
    generate_typescript,
    infer_json_schema,
)


def test_infer_json_schema():
    sample = {
        "id": 1,
        "nome": "Produto X",
        "ativo": True,
        "preco": 19.99,
        "tags": ["hardware", "usb"],
        "info": {"estoque": 50}
    }
    schema = infer_json_schema(sample, title="Produto")

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == "Produto"
    assert schema["type"] == "object"
    assert "id" in schema["properties"]
    assert schema["properties"]["id"]["type"] == "integer"
    assert schema["properties"]["nome"]["type"] == "string"
    assert schema["properties"]["ativo"]["type"] == "boolean"
    assert schema["properties"]["preco"]["type"] == "number"
    assert schema["properties"]["tags"]["type"] == "array"
    assert schema["properties"]["tags"]["items"]["type"] == "string"
    assert schema["properties"]["info"]["type"] == "object"
    assert schema["properties"]["info"]["properties"]["estoque"]["type"] == "integer"


def test_generate_pydantic_v2():
    sample = {
        "codigo": 123,
        "descricao": "Item A",
        "categorias": ["eletro", "casa"],
    }
    code = generate_pydantic_v2(sample, root_name="ItemModel")

    assert "from pydantic import BaseModel" in code
    assert "class ItemModel(BaseModel):" in code
    assert "codigo: int" in code
    assert "descricao: str" in code
    assert "categorias: List[str]" in code


def test_generate_dataclass():
    sample = {
        "id": 10,
        "itens": ["um", "dois"],
        "ativo": False,
    }
    code = generate_dataclass(sample, root_name="PedidoData")

    assert "from dataclasses import dataclass, field" in code
    assert "@dataclass" in code
    assert "class PedidoData:" in code
    assert "id: int = 10" in code
    assert "itens: List[str] = field(default_factory=list)" in code
    assert "ativo: bool = False" in code


def test_generate_typescript():
    sample = {
        "userId": 55,
        "email": "teste@dominio.com",
        "roles": ["admin"],
        "profile": {
            "avatarUrl": "https://img.com/a.png",
        }
    }
    ts_code = generate_typescript(sample, root_name="UserResponse")

    assert "export interface UserResponse {" in code_str if (code_str := ts_code) else False
    assert "userId: number;" in ts_code
    assert "email: string;" in ts_code
    assert "roles: string[];" in ts_code
    assert "profile: Profile;" in ts_code
    assert "export interface Profile {" in ts_code
    assert "avatarUrl: string;" in ts_code
