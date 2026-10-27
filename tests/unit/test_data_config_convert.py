"""
Testes unitários rigorosos para data.config_convert.logic.
Validação determinística de conversão bidirecional entre .env, .ini, .properties, TOML, YAML e JSON.
"""
import json
import pytest
from wintoolbox.tools.data.config_convert.logic import (
    flatten_dict,
    parse_config_content,
    serialize_config_content,
    unflatten_dict,
)


def test_flatten_and_unflatten_dict():
    nested = {
        "banco": {
            "host": "localhost",
            "porta": 5432,
            "credenciais": {
                "user": "root",
            }
        },
        "app": "WinToolbox"
    }

    flat = flatten_dict(nested, sep=".")
    assert flat["banco.host"] == "localhost"
    assert flat["banco.porta"] == 5432
    assert flat["banco.credenciais.user"] == "root"
    assert flat["app"] == "WinToolbox"

    restored = unflatten_dict(flat, sep=".")
    assert restored == nested


def test_parse_and_serialize_env():
    env_text = (
        "# Comentário inicial\n"
        "PORT=8000\n"
        'SECRET_KEY="super_chave_secreta"\n'
        "DEBUG=true\n"
    )
    ok, data, err = parse_config_content(env_text, "env")
    assert ok is True
    assert data["PORT"] == "8000"
    assert data["SECRET_KEY"] == "super_chave_secreta"
    assert data["DEBUG"] == "true"

    ok_ser, env_out, err_ser = serialize_config_content(data, "env")
    assert ok_ser is True
    assert "PORT=8000" in env_out
    assert "DEBUG=true" in env_out


def test_parse_and_serialize_ini():
    ini_text = (
        "[servidor]\n"
        "ip = 192.168.1.100\n"
        "porta = 80\n"
        "\n"
        "[cache]\n"
        "habilitado = true\n"
    )
    ok, data, err = parse_config_content(ini_text, "ini")
    assert ok is True
    assert data["servidor"]["ip"] == "192.168.1.100"
    assert data["servidor"]["porta"] == "80"
    assert data["cache"]["habilitado"] == "true"

    ok_ser, ini_out, _ = serialize_config_content(data, "ini")
    assert ok_ser is True
    assert "[servidor]" in ini_out
    assert "porta = 80" in ini_out


def test_parse_and_serialize_properties():
    prop_text = (
        "# Spring Boot Properties\n"
        "server.port = 8080\n"
        "spring.datasource.url: jdbc:postgresql://localhost/db\n"
    )
    ok, data, err = parse_config_content(prop_text, "properties")
    assert ok is True
    assert data["server.port"] == "8080"
    assert data["spring.datasource.url"] == "jdbc:postgresql://localhost/db"

    # Converte para JSON com expansão de chaves
    ok_json, json_out, _ = serialize_config_content(data, "json", flatten=False)
    assert ok_json is True
    parsed_json = json.loads(json_out)
    assert parsed_json["server"]["port"] == "8080"
    assert parsed_json["spring"]["datasource"]["url"] == "jdbc:postgresql://localhost/db"


def test_toml_and_json_roundtrip():
    json_str = '{"sistema": {"versao": "2.0", "ativo": true}, "limite": 100}'
    ok, data, _ = parse_config_content(json_str, "json")
    assert ok is True

    # Serializa para TOML
    ok_toml, toml_str, _ = serialize_config_content(data, "toml")
    assert ok_toml is True
    assert "[sistema]" in toml_str
    assert 'versao = "2.0"' in toml_str
    assert "limite = 100" in toml_str

    # Lê de volta TOML
    ok_back, data_back, _ = parse_config_content(toml_str, "toml")
    assert ok_back is True
    assert data_back["sistema"]["versao"] == "2.0"
    assert data_back["limite"] == 100
