"""
Testes de validação de efeito real para network.subnet_calc.logic.
"""
import pytest
from wintoolbox.tools.network.subnet_calc.logic import (
    SubnetDetails,
    calculate_subnet_details,
    determine_ip_class,
    ip_to_binary_string,
)


def test_calculate_subnet_details_class_c_private_24():
    d = calculate_subnet_details("192.168.1.50", "24")
    assert d.ip == "192.168.1.50"
    assert d.prefix == 24
    assert d.netmask == "255.255.255.0"
    assert d.wildcard == "0.0.0.255"
    assert d.network_ip == "192.168.1.0"
    assert d.broadcast_ip == "192.168.1.255"
    assert d.first_host == "192.168.1.1"
    assert d.last_host == "192.168.1.254"
    assert d.total_addresses == 256
    assert d.usable_hosts == 254
    assert d.ip_class == "Classe C"
    assert "RFC 1918" in d.scope_type


def test_calculate_subnet_details_point_to_point_30():
    # /30: 4 endereços totais, 2 utilizáveis
    d = calculate_subnet_details("10.0.0.1", "30")
    assert d.network_ip == "10.0.0.0"
    assert d.broadcast_ip == "10.0.0.3"
    assert d.first_host == "10.0.0.1"
    assert d.last_host == "10.0.0.2"
    assert d.total_addresses == 4
    assert d.usable_hosts == 2
    assert d.netmask == "255.255.255.252"
    assert d.wildcard == "0.0.0.3"


def test_calculate_subnet_details_public_ip():
    d = calculate_subnet_details("8.8.8.8", "32")
    assert d.ip == "8.8.8.8"
    assert d.prefix == 32
    assert d.usable_hosts == 1
    assert d.total_addresses == 1
    assert "Público" in d.scope_type
    assert d.ip_class == "Classe A"


def test_ip_to_binary_string_format():
    # 192.168.1.1 -> 11000000.10101000.00000001.00000001
    bin_str = ip_to_binary_string(3232235777)
    assert bin_str == "11000000.10101000.00000001.00000001"
    assert len(bin_str) == 35  # 32 bits + 3 pontos


def test_calculate_subnet_details_invalid_inputs():
    with pytest.raises(ValueError):
        calculate_subnet_details("999.999.999.999", "24")
    with pytest.raises(ValueError):
        calculate_subnet_details("192.168.1.1", "35")  # Prefixo maior que 32
    with pytest.raises(ValueError):
        calculate_subnet_details("invalido", "24")
