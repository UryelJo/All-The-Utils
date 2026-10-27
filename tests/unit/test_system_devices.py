"""
Testes de validação de efeito real para system.devices.logic.
"""
import pytest
from wintoolbox.tools.system.devices.logic import (
    PnpDevice,
    parse_pnp_devices_json,
    parse_usb_history_json,
    CONFIG_MANAGER_ERRORS,
)


def test_config_manager_error_mapping_deterministic():
    assert CONFIG_MANAGER_ERRORS[10] == "O dispositivo não pode ser iniciado (Código 10)"
    assert CONFIG_MANAGER_ERRORS[43] == "O Windows interrompeu este dispositivo por problemas relatados (Código 43)"
    assert CONFIG_MANAGER_ERRORS[28] == "Os drivers para este dispositivo não estão instalados (Código 28)"


def test_parse_pnp_devices_json_deterministic():
    sample_json = """
    [
        {
            "Name": "NVIDIA GeForce RTX 4070",
            "DeviceID": "PCI\\\\VEN_10DE&DEV_2786",
            "Status": "OK",
            "ConfigManagerErrorCode": 0,
            "PNPClass": "Display",
            "Manufacturer": "NVIDIA"
        },
        {
            "Name": "Dispositivo PCI Desconhecido",
            "DeviceID": "PCI\\\\VEN_8086&DEV_1234",
            "Status": "Error",
            "ConfigManagerErrorCode": 28,
            "PNPClass": "Other",
            "Manufacturer": "Desconhecido"
        }
    ]
    """
    devices = parse_pnp_devices_json(sample_json)
    assert len(devices) == 2

    gpu = devices[0]
    assert gpu.name == "NVIDIA GeForce RTX 4070"
    assert gpu.has_error is False
    assert gpu.error_description == "Funcionando normalmente"

    unknown = devices[1]
    assert unknown.name == "Dispositivo PCI Desconhecido"
    assert unknown.has_error is True
    assert unknown.error_code == 28
    assert "Código 28" in unknown.error_description


def test_parse_pnp_devices_json_edge_cases():
    assert parse_pnp_devices_json("") == []
    assert parse_pnp_devices_json("json invalido {") == []


def test_parse_usb_history_json_deterministic():
    sample_usb = """
    [
        {
            "FriendlyName": "Kingston DataTraveler 3.0",
            "DeviceName": "Disk&Ven_Kingston&Prod_DataTraveler_3.0",
            "SerialNumber": "00187D0A23121"
        }
    ]
    """
    res = parse_usb_history_json(sample_usb)
    assert len(res) == 1
    assert res[0]["FriendlyName"] == "Kingston DataTraveler 3.0"
    assert res[0]["SerialNumber"] == "00187D0A23121"
