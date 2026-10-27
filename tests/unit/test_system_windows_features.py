"""
Testes de validação de efeito real para system.windows_features.logic.
"""
import pytest
from wintoolbox.tools.system.windows_features.logic import (
    WindowsFeature,
    parse_features_json,
    parse_dism_text_output,
)


def test_parse_features_json_deterministic():
    sample_json = """
    [
        {
            "FeatureName": "Microsoft-Windows-Subsystem-Linux",
            "State": "Enabled",
            "DisplayName": "Subsistema do Windows para Linux",
            "Description": "Permite executar ferramentas de linha de comando do Linux."
        },
        {
            "FeatureName": "TelnetClient",
            "State": "Disabled",
            "DisplayName": "Cliente Telnet",
            "Description": "Conecta computadores remotos usando protocolo Telnet."
        }
    ]
    """
    features = parse_features_json(sample_json)
    assert len(features) == 2

    wsl = features[0]
    assert wsl.name == "Microsoft-Windows-Subsystem-Linux"
    assert wsl.state == "Enabled"
    assert wsl.is_enabled is True
    assert wsl.display_name == "Subsistema do Windows para Linux"

    telnet = features[1]
    assert telnet.name == "TelnetClient"
    assert telnet.state == "Disabled"
    assert telnet.is_enabled is False


def test_parse_features_json_edge_cases():
    assert parse_features_json("") == []
    assert parse_features_json("json invalido {") == []

    # Objeto único (sem array)
    single_obj = '{"FeatureName": "Hyper-V", "State": "Enabled"}'
    res = parse_features_json(single_obj)
    assert len(res) == 1
    assert res[0].name == "Hyper-V"
    assert res[0].is_enabled is True


def test_parse_dism_text_output_pt_and_en():
    sample_dism = """
    Nome do recurso : Containers-DisposableClientVM
    Estado : Habilitado

    Feature Name : TFTP
    State : Disabled
    """
    features = parse_dism_text_output(sample_dism)
    assert len(features) == 2

    assert features[0].name == "Containers-DisposableClientVM"
    assert features[0].state == "Enabled"
    assert features[0].is_enabled is True

    assert features[1].name == "TFTP"
    assert features[1].state == "Disabled"
    assert features[1].is_enabled is False
